"""
SCRUM-14: Event Ingestion API
Production-ready FastAPI endpoint for event ingestion with Kafka publishing simulation.
Python 3.11+ with Pydantic v2, async processing, and API key authentication.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Application metadata
SERVICE_NAME = "event-ingestion-api"
SERVICE_VERSION = "1.0.0"

# Valid API keys
VALID_API_KEYS = {"demo-api-key-123", "dell-demo-key-456"}

# Kafka topic (simulated)
KAFKA_TOPIC = "events"

app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION)


class EventType(str, Enum):
    """Enumeration of valid event types."""
    CLICK = "click"
    VIEW = "view"
    SCROLL = "scroll"
    PURCHASE = "purchase"


class ClickEvent(BaseModel):
    """Model for an individual click event in the ingestion batch."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique event identifier")
    user_id: str = Field(..., description="Required: User identifier")
    session_id: str = Field(..., description="Required: Session identifier")
    event_type: EventType = Field(..., description="Type of event (click, view, scroll, purchase)")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="ISO8601 timestamp")
    properties: Optional[dict[str, Any]] = Field(default=None, description="Optional event properties")

    @field_validator("user_id", "session_id")
    @classmethod
    def validate_required_fields(cls, v: str) -> str:
        """Validate that required fields are non-empty strings."""
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("must be a non-empty string")
        return v.strip()

    @field_validator("properties")
    @classmethod
    def validate_properties(cls, v: Optional[dict]) -> Optional[dict]:
        """Validate properties dictionary if provided."""
        if v is not None and not isinstance(v, dict):
            raise ValueError("properties must be a dictionary")
        return v


class RejectedEvent(BaseModel):
    """Model for a rejected event in the response."""
    event_id: str = Field(..., description="Event identifier")
    reason: str = Field(..., description="Reason for rejection")


class EventIngestionResponse(BaseModel):
    """Response model for event ingestion."""
    ingestion_id: str = Field(..., description="Unique ingestion batch identifier")
    accepted_count: int = Field(..., description="Number of accepted events")
    rejected_events: list[RejectedEvent] = Field(default_factory=list, description="List of rejected events with reasons")
    topic: str = Field(..., description="Kafka topic name")


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""
    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")


def validate_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    """
    Validate the API key from request header.
    
    Args:
        x_api_key: API key from x-api-key header
        
    Raises:
        HTTPException: If API key is missing or invalid
    """
    if not x_api_key or x_api_key not in VALID_API_KEYS:
        logger.warning(f"Unauthorized API key attempt: {x_api_key}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def publish_to_kafka(events: list[ClickEvent], ingestion_id: str) -> None:
    """
    Simulate publishing events to Kafka topic.
    
    In production, this would use confluent-kafka or similar library.
    
    Args:
        events: List of validated ClickEvent objects
        ingestion_id: Batch ingestion identifier
    """
    for event in events:
        message = {
            "ingestion_id": ingestion_id,
            "event": event.model_dump(mode="json"),
        }
        logger.info(f"Published to {KAFKA_TOPIC}: {json.dumps(message)}")


@app.post(
    "/v1/events",
    response_model=EventIngestionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest events",
    description="Accept a batch of events for ingestion and publishing to Kafka",
)
async def ingest_events(
    events: list[ClickEvent],
    x_api_key: str = Header(..., description="API authentication key"),
) -> EventIngestionResponse:
    """
    POST /v1/events endpoint for event ingestion.
    
    Accepts a batch of 1-1000 events, validates each event, and simulates
    publishing to Kafka. Returns 202 Accepted with ingestion details.
    
    Args:
        events: List of ClickEvent objects (1-1000 items)
        x_api_key: API key from header (validated by dependency)
        
    Returns:
        EventIngestionResponse with ingestion summary
        
    Raises:
        HTTPException: For authentication errors (401) or batch size errors (422)
    """
    # Validate API key
    validate_api_key(x_api_key)
    
    # Validate batch size
    if not events or len(events) > 1000:
        logger.warning(f"Invalid batch size: {len(events) if events else 0}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Batch size must be between 1 and 1000 events, received {len(events) if events else 0}",
        )
    
    # Process events
    ingestion_id = str(uuid.uuid4())
    accepted_events: list[ClickEvent] = []
    rejected_events_list: list[RejectedEvent] = []
    
    for idx, event in enumerate(events):
        try:
            # Pydantic v2 validation is implicit in model instantiation
            # If we reach here, the event is valid
            accepted_events.append(event)
            logger.info(
                f"Event accepted - ingestion_id: {ingestion_id}, event_id: {event.event_id}, "
                f"user_id: {event.user_id}, type: {event.event_type}"
            )
        except Exception as e:
            rejected_events_list.append(
                RejectedEvent(
                    event_id=getattr(event, "event_id", f"unknown_{idx}"),
                    reason=str(e),
                )
            )
            logger.warning(f"Event rejected - ingestion_id: {ingestion_id}, reason: {e}")
    
    # Simulate Kafka publishing for accepted events
    if accepted_events:
        await publish_to_kafka(accepted_events, ingestion_id)
    
    logger.info(
        f"Ingestion completed - ingestion_id: {ingestion_id}, "
        f"accepted: {len(accepted_events)}, rejected: {len(rejected_events_list)}"
    )
    
    return EventIngestionResponse(
        ingestion_id=ingestion_id,
        accepted_count=len(accepted_events),
        rejected_events=rejected_events_list,
        topic=KAFKA_TOPIC,
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Check the health status of the event ingestion service",
)
async def health_check() -> HealthResponse:
    """
    GET /health endpoint for service health status.
    
    Returns:
        HealthResponse with service status, name, and version
    """
    logger.info("Health check requested")
    return HealthResponse(
        status="healthy",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
    )


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting {SERVICE_NAME} v{SERVICE_VERSION}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
