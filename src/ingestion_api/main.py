"""
Clickstream Data Product — Event Ingestion API
FastAPI application for receiving and publishing clickstream events.
"""

import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from src.ingestion_api.config import KafkaConfig
from src.ingestion_api.kafka_producer import KafkaProducerClient, KafkaProducerError
from src.ingestion_api.models import KafkaHealthResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VALID_API_KEYS = {
    key.strip()
    for key in os.getenv("VALID_API_KEYS", "demo-api-key-123,dell-demo-key-456").split(",")
    if key.strip()
}
KAFKA_TOPIC = "clickstream.raw.events"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        kafka_config = KafkaConfig.load()
    except ValueError as exc:
        logger.warning(
            "Kafka configuration not found; falling back to simulated publish: %s",
            exc,
        )
        app.state.kafka_client = None
        app.state.kafka_topic = KAFKA_TOPIC
        app.state.kafka_cluster = "unknown"
        yield
        return

    app.state.kafka_client = KafkaProducerClient(
        bootstrap_servers=kafka_config.bootstrap_servers,
        api_key=kafka_config.api_key,
        api_secret=kafka_config.api_secret,
        topic=kafka_config.topic,
    )
    app.state.kafka_topic = kafka_config.topic
    app.state.kafka_cluster = kafka_config.cluster

    try:
        if not app.state.kafka_client.validate_connection():
            raise RuntimeError("Kafka connectivity validation failed")
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Kafka startup connectivity validation failed; continuing in fallback mode: %s",
            exc,
        )
        app.state.kafka_client = None

    yield

    # Shutdown
    kafka_client = getattr(app.state, "kafka_client", None)
    if kafka_client is not None:
        kafka_client.close()


app = FastAPI(
    title="Clickstream Ingestion API",
    description="Real-time event ingestion for the Clickstream Data Product",
    version="1.0.0",
    lifespan=lifespan,
)


class EventType(str, Enum):
    click = "click"
    view = "view"
    scroll = "scroll"
    purchase = "purchase"


class ClickEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(..., min_length=1, max_length=128)
    session_id: str = Field(..., min_length=1, max_length=128)
    event_type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp", mode="before")
    @classmethod
    def validate_timestamp(cls, value: Any) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError as exc:
                raise ValueError("timestamp must be a valid ISO 8601 string") from exc
            return parsed.astimezone(timezone.utc)
        raise ValueError("timestamp must be an ISO 8601 formatted string")


class EventBatch(BaseModel):
    events: list[ClickEvent] = Field(..., min_length=1, max_length=1000)


class RejectedEvent(BaseModel):
    index: int
    reason: str


class IngestionResponse(BaseModel):
    ingestion_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    accepted_count: int
    rejected_events: list[RejectedEvent]
    topic: str


def _authenticate(api_key: str | None) -> None:
    if not api_key or api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


async def _publish_to_kafka(event: ClickEvent) -> bool:
    kafka_client: KafkaProducerClient = getattr(app.state, "kafka_client", None)
    if kafka_client is None:
        logger.info(
            "Kafka client not configured; simulating publish for event_id=%s",
            event.event_id,
        )
        await asyncio.sleep(0)
        return True

    try:
        metadata = await kafka_client.publish_event(event.model_dump())
        logger.info(
            "Published event to Kafka: topic=%s event_id=%s partition=%s offset=%s",
            app.state.kafka_topic,
            metadata.get("event_id"),
            metadata.get("kafka_partition"),
            metadata.get("kafka_offset"),
        )
        return True
    except KafkaProducerError as exc:
        logger.error("Kafka publish failed for event_id=%s: %s", event.event_id, exc)
        return False


@app.get("/health/kafka", response_model=KafkaHealthResponse)
async def kafka_health() -> KafkaHealthResponse:
    kafka_client: KafkaProducerClient = getattr(app.state, "kafka_client", None)
    if kafka_client is None:
        return KafkaHealthResponse(
            kafka_connected=False,
            kafka_topic=getattr(app.state, "kafka_topic", KAFKA_TOPIC),
            kafka_cluster=getattr(app.state, "kafka_cluster", "unknown"),
        )

    connected = kafka_client.validate_connection()
    return KafkaHealthResponse(
        kafka_connected=connected,
        kafka_topic=app.state.kafka_topic,
        kafka_cluster=app.state.kafka_cluster,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    rejected_events = []
    for error in exc.errors():
        location = " -> ".join(str(part) for part in error.get("loc", []))
        rejected_events.append(
            {"index": -1, "reason": f"{error.get('msg')} (location: {location})"}
        )

    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "accepted_count": 0,
                "rejected_events": rejected_events,
            }
        },
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": "clickstream-ingestion-api",
        "version": "1.0.0",
    }


@app.post("/v1/events", response_model=IngestionResponse, status_code=202)
async def ingest_events(
    batch: EventBatch,
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
) -> IngestionResponse:
    _authenticate(x_api_key)

    ingestion_id = uuid.uuid4()
    accepted_count = 0
    rejected_events: list[RejectedEvent] = []

    for index, event in enumerate(batch.events):
        try:
            if await _publish_to_kafka(event):
                accepted_count += 1
            else:
                rejected_events.append(
                    RejectedEvent(index=index, reason="failed to publish event")
                )
        except Exception as exc:
            logger.error("Failed to publish event at index %d: %s", index, exc)
            rejected_events.append(RejectedEvent(index=index, reason=str(exc)))

    return IngestionResponse(
        ingestion_id=ingestion_id,
        accepted_count=accepted_count,
        rejected_events=rejected_events,
        topic=getattr(app.state, "kafka_topic", KAFKA_TOPIC),
    )
