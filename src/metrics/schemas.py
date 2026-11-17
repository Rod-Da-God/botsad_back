from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


AllowedEventName = Literal[
    "item_card_open_short",
    "item_card_open_full",
    "booking_start",
    "booking_complete",
    "booking_abandon",
]


class AnalyticsEvent(BaseModel):
    # обязательные FE-поля
    event_id: UUID
    event_name: AllowedEventName
    event_ts: datetime
    client_id: UUID
    session_id: UUID

    # сущность
    entity_type: str
    entity_id: int

    # произвольные JSON
    context: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class EventsBatch(BaseModel):
    events: list[AnalyticsEvent]
