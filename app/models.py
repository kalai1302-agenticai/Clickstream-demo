from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class EventType(str, Enum):
    page_view = "page_view"
    button_click = "button_click"
    add_to_cart = "add_to_cart"
    purchase = "purchase"
    search = "search"
    form_submit = "form_submit"
    video_play = "video_play"


class DeviceType(str, Enum):
    web = "web"
    mobile_ios = "mobile_ios"
    mobile_android = "mobile_android"


class ClickstreamEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique event identifier")
    user_id: str = Field(..., min_length=1, description="User identifier")
    session_id: str = Field(..., min_length=1, description="Session identifier")
    event_type: EventType = Field(..., description="Type of clickstream event")
    event_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Event occurrence timestamp")
    page_url: Optional[str] = Field(None, description="Page or screen URL")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional event properties")
    device_type: Optional[DeviceType] = Field(None, description="Device type")
    ip_address: Optional[str] = Field(None, description="Source IP address")

    @field_validator("event_id")
    @classmethod
    def validate_event_id(cls, value: str) -> str:
        try:
            UUID(value)
            return value
        except ValueError as exc:
            raise ValueError("event_id must be a valid UUID string") from exc

    @field_validator("event_timestamp")
    @classmethod
    def validate_event_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("event_timestamp must be timezone-aware")
        return value


class EventResponse(BaseModel):
    event_id: str
    status: str
    kafka_offset: int


class HealthResponse(BaseModel):
    status: str
    kafka_connected: bool
    kafka_topic: str
    kafka_cluster: str
