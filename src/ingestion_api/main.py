"""
Clickstream Data Product — Event Ingestion API
FastAPI application for receiving and publishing clickstream events.
"""

import uuid
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Clickstream Ingestion API",
    description="Real-time event ingestion for the Clickstream Data Product",
    version="1.0.0",
)

VALID_API_KEYS = {"demo-api-key-123", "dell-demo-key-456"}
KAFKA_TOPIC = "clickstream.raw.events"


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
            raise ValueError("timestamp must be a valid ISO 8601 string") from exc
        return value


class EventBatch(BaseModel):
    events: list[ClickEvent] = Field(..., min_length=1, max_length=1000)


class RejectedEvent(BaseModel):
    index: int
    reason: str


class IngestionResponse(BaseModel):
    ingestion_id: str
    accepted_count: int
    rejected_events: list[RejectedEvent]
    topic: str


def _authenticate(api_key: str | None) -> None:
    if api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def _publish_to_kafka(event: ClickEvent) -> bool:
    logger.info("Published event %s to topic %s", event.event_id, KAFKA_TOPIC)
    return True


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    rejected_events = [
        {"index": i, "reason": f"{e['msg']}: {' -> '.join(str(loc) for loc in e['loc'])}"}
        for i, e in enumerate(errors)
    ]
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
def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "clickstream-ingestion-api", "version": "1.0.0"}


@app.post("/v1/events", response_model=IngestionResponse, status_code=202)
def ingest_events(
    batch: EventBatch,
    x_api_key: str | None = Header(default=None),
) -> IngestionResponse:
    _authenticate(x_api_key)

    ingestion_id = str(uuid.uuid4())
    accepted_count = 0
    rejected_events: list[RejectedEvent] = []

    for index, event in enumerate(batch.events):
        try:
            if _publish_to_kafka(event):
                accepted_count += 1
        except Exception as exc:
            logger.error("Failed to publish event at index %d: %s", index, exc)
            rejected_events.append(RejectedEvent(index=index, reason=str(exc)))

    return IngestionResponse(
        ingestion_id=ingestion_id,
        accepted_count=accepted_count,
        rejected_events=rejected_events,
        topic=KAFKA_TOPIC,
    )
