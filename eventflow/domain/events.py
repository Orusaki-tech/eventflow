from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


class Event(Protocol):
    pass


@dataclass(frozen=True)
class EventConfirmed(Event):
    event_id: UUID
    user_id: UUID
    calendar_sync_needed: bool = True


@dataclass(frozen=True)
class AlertScheduled(Event):
    event_id: UUID
    trigger_at: datetime


@dataclass(frozen=True)
class EventCancelled(Event):
    event_id: UUID


@dataclass(frozen=True)
class CommunityEventUpserted(Event):
    community_event_id: UUID

