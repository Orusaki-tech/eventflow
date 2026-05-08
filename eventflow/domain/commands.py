from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


class Command(Protocol):
    pass


@dataclass(frozen=True)
class CaptureEventImage(Command):
    user_id: UUID
    image_bytes: bytes


@dataclass(frozen=True)
class CaptureEventText(Command):
    user_id: UUID
    text: str


@dataclass(frozen=True)
class CaptureEventUrl(Command):
    user_id: UUID
    url: str


@dataclass(frozen=True)
class CaptureEventUploadImage(Command):
    user_id: UUID
    image_bytes: bytes


@dataclass(frozen=True)
class CaptureEventIcs(Command):
    user_id: UUID
    ics_bytes: bytes


@dataclass(frozen=True)
class UpsertCommunityEvent(Command):
    user_id: UUID
    source: str
    title: str
    start_time: datetime
    venue: str
    description: str | None = None


@dataclass(frozen=True)
class ConfirmEventDraft(Command):
    draft_id: UUID
    user_id: UUID


@dataclass(frozen=True)
class UpdateEventDraft(Command):
    draft_id: UUID
    user_id: UUID
    title: str | None = None
    start_time: datetime | None = None
    venue: str | None = None


@dataclass(frozen=True)
class CancelEvent(Command):
    event_id: UUID
    user_id: UUID


@dataclass(frozen=True)
class ScheduleTrafficAlert(Command):
    event_id: UUID
    user_id: UUID
    travel_seconds: int


@dataclass(frozen=True)
class ScheduleReminderAlert(Command):
    event_id: UUID
    user_id: UUID
    minutes_before: int
