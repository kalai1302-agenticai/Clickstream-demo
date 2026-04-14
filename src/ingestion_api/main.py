"""
Clickstream Data Product — Event Ingestion API
FastAPI application for receiving and publishing clickstream events.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError, field_validator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("clickstream.ingestion")

VALID_API_KEYS = set(os.getenv("VALID_API_KEYS", "demo-api-key-123,dell-demo-key-456").split(","))
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "clickstream.raw.events")

app = FastAPI(
    title="Clickstream Ingestion API",
    description="Real-time event ingestion for the Clickstream Data Product",
    version="1.0.0",
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
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: str) -> str:
        try:
            datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("Invalid ISO 8601 timestamp") from exc
        return value


class EventBatch(BaseModel):
    events: list[dict[str, Any]] = Field(..., min_length=1, max_length=1000)


class RejectedEvent(BaseModel):
    index: int
    reason: str


class IngestionResponse(BaseModel):
    ingestion_id: str
    accepted_count: int
    rejected_events: list[RejectedEvent]
    topic: str


async def _authenticate(api_key: str | None) -> None:
    if api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")


async def _publish_to_kafka(event: ClickEvent) -> bool:
    logger.info(
        "Simulated Kafka publish: topic=%s event_id=%s user_id=%s session_id=%s event_type=%s",
        KAFKA_TOPIC,
        event.event_id,
        event.user_id,
        event.session_id,
        event.event_type,
    )
    return True


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
    x_api_key: str | None = Header(default=None),
) -> IngestionResponse:
    await _authenticate(x_api_key)

    ingestion_id = str(uuid.uuid4())
    accepted_count = 0
    rejected_events: list[RejectedEvent] = []

    for index, event_dict in enumerate(batch.events):
        try:
            event = ClickEvent(**event_dict)
            published = await _publish_to_kafka(event)
            if published:
                accepted_count += 1
        except ValidationError as exc:
            rejected_events.append(
                RejectedEvent(index=index, reason="; ".join(err["msg"] for err in exc.errors()))
            )
        except Exception as exc:
            logger.error("Failed to publish event at index %d: %s", index, exc)
            rejected_events.append(RejectedEvent(index=index, reason=str(exc)))

    if rejected_events:
        raise HTTPException(
            status_code=422,
            detail={
                "ingestion_id": ingestion_id,
                "accepted_count": accepted_count,
                "rejected_events": [rej.model_dump() for rej in rejected_events],
                "topic": KAFKA_TOPIC,
            },
        )

    return IngestionResponse(
        ingestion_id=ingestion_id,
        accepted_count=accepted_count,
        rejected_events=rejected_events,
        topic=KAFKA_TOPIC,
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception while processing request")
    return JSONResponse(status_code=500, content={"detail": "Server error"})
