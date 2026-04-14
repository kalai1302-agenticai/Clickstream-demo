"""
Clickstream Ingestion API — FastAPI service for real-time event ingestion.

This module implements the POST /v1/events endpoint with API key authentication,
batch processing, and simulated Kafka publishing.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Valid API keys (in production, load from secure config)
VALID_API_KEYS = {"demo-api-key-123", "dell-demo-key-456"}

# Kafka topic (simulated)
KAFKA_TOPIC = "clickstream.raw.events"


class EventType(str, Enum):
    """Enumeration of supported event types."""
    CLICK = "click"
    VIEW = "view"
    SCROLL = "scroll"
    PURCHASE = "purchase"


class ClickEvent(BaseModel):
    """Pydantic model for a single clickstream event."""
    event_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique event identifier (auto-generated)")
    user_id: str = Field(..., description="Authenticated user identifier")
    session_id: str = Field(..., description="Browser/app session identifier")
    event_type: EventType = Field(..., description="Type of event")
    timestamp: Optional[str] = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="Event occurrence time (ISO 8601, auto-generated)")
    properties: Optional[Dict[str, str]] = Field(default_factory=dict, description="Arbitrary event metadata")

    @validator('event_id', pre=True, always=True)
    def generate_event_id(cls, v):
        return v or str(uuid.uuid4())

    @validator('timestamp', pre=True, always=True)
    def generate_timestamp(cls, v):
        return v or datetime.now(timezone.utc).isoformat()


class EventBatchRequest(BaseModel):
    """Request model for batch event ingestion."""
    events: List[ClickEvent] = Field(..., min_items=1, max_items=1000, description="List of events to ingest (1-1000)")


class IngestionResponse(BaseModel):
    """Response model for successful ingestion."""
    ingestion_id: str = Field(..., description="Unique ingestion batch identifier")
    accepted_count: int = Field(..., description="Number of events accepted")
    rejected_events: List[Dict[str, str]] = Field(default_factory=list, description="List of rejected events with error details")
    topic: str = Field(..., description="Kafka topic where events were published")


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str = Field(..., description="Service health status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")


def authenticate_api_key(request: Request) -> None:
    """Dependency to authenticate requests using x-api-key header."""
    api_key = request.headers.get("x-api-key")
    if not api_key or api_key not in VALID_API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )


app = FastAPI(
    title="Clickstream Ingestion API",
    description="Real-time event ingestion service for clickstream analytics",
    version="1.0.0",
    dependencies=[Depends(authenticate_api_key)]
)


@app.post(
    "/v1/events",
    response_model=IngestionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest batch of clickstream events",
    description="Accepts a batch of 1-1000 clickstream events, validates them, and publishes to Kafka topic."
)
async def ingest_events(request: EventBatchRequest) -> IngestionResponse:
    """Ingest a batch of clickstream events."""
    ingestion_id = str(uuid.uuid4())
    accepted_count = 0
    rejected_events = []

    # Validate batch size (though Pydantic handles min/max, we can customize)
    if len(request.events) > 1000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Batch size exceeds maximum of 1000 events"
        )

    # Process each event (in production, validate more thoroughly)
    for event in request.events:
        try:
            # Simulate validation (Pydantic already validates structure)
            # In a real scenario, add business logic validation here
            accepted_count += 1
        except Exception as e:
            rejected_events.append({
                "event_id": event.event_id,
                "error": str(e)
            })

    # Simulate Kafka publish by logging
    logger.info(f"Publishing {accepted_count} events to topic '{KAFKA_TOPIC}' with ingestion_id '{ingestion_id}'")
    for event in request.events:
        logger.info(f"Event: {event.json()}")

    return IngestionResponse(
        ingestion_id=ingestion_id,
        accepted_count=accepted_count,
        rejected_events=rejected_events,
        topic=KAFKA_TOPIC
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check endpoint",
    description="Returns the health status of the service."
)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service="clickstream-ingestion-api",
        version="1.0.0"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
