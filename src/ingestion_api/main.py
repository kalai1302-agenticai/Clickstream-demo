"""
Clickstream Data Product — Event Ingestion API
FastAPI application for receiving and publishing clickstream events.
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
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

VALID_API_KEYS = {
    key.strip()
    for key in os.getenv("VALID_API_KEYS", "demo-api-key-123,dell-demo-key-456").split(",")
    if key.strip()
}
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
    logger.info(
        "Simulated Kafka publish: topic=%s event_id=%s user_id=%s session_id=%s event_type=%s",
        KAFKA_TOPIC,
        event.event_id,
        event.user_id,
        event.session_id,
        event.event_type,
    )
    await asyncio.sleep(0)
    return True


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
        topic=KAFKA_TOPIC,
    )
