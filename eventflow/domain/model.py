from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from eventflow.domain import events
from eventflow.domain.exceptions import InvariantViolation, PastEventError


class AlertType(str, Enum):
    TRAFFIC_ALERT = "TRAFFIC_ALERT"
    REMINDER = "REMINDER"


class EventVisibility(str, Enum):
    PRIVATE = "private"
    PUBLIC = "public"


@dataclass(frozen=True)
class Alert:
    alert_type: AlertType
    trigger_at: datetime
    message: str
    event_id: UUID
    id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class TrafficCondition:
    travel_seconds: int


@dataclass(frozen=True)
class UserLocation:
    user_id: UUID
    label: str  # "home" | "work"
    address: str
    lat: float | None = None
    lng: float | None = None


class EventDraft:
    def __init__(
        self,
        id: UUID,
        user_id: UUID,
        title: str,
        start_time: Optional[datetime],
        venue: str,
        confidence_score: float,
        confirmed_at: Optional[datetime] = None,
        price: Optional[str] = None,
    ):
        self.id = id
        self.user_id = user_id
        self.title = title
        self.start_time = start_time
        self.venue = venue
        self.confidence_score = confidence_score
        self.confirmed_at = confirmed_at
        self.price = price

    @classmethod
    def new(
        cls,
        *,
        user_id: UUID,
        title: str,
        start_time: Optional[datetime],
        venue: str,
        confidence_score: float,
        price: Optional[str] = None,
    ) -> "EventDraft":
        return cls(
            id=uuid4(),
            user_id=user_id,
            title=title,
            start_time=start_time,
            venue=venue,
            confidence_score=confidence_score,
            confirmed_at=None,
            price=price,
        )

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at is not None

    def confirm(self, *, at: Optional[datetime] = None) -> None:
        if self.confirmed_at is not None:
            return
        self.confirmed_at = at or datetime.now(timezone.utc)


class ScheduledEvent:
    def __init__(
        self,
        id: UUID,
        user_id: UUID,
        title: str,
        start_time: datetime,
        venue: str,
        *,
        venue_id: UUID | None = None,
        raw_venue_text: str | None = None,
        visibility: EventVisibility = EventVisibility.PRIVATE,
        description_public: str | None = None,
        description_close_friends: str | None = None,
        price: Optional[str] = None,
        cancelled_at: datetime | None = None,
    ):
        self.id = id
        self.user_id = user_id
        self.title = title
        self.start_time = start_time
        self.venue = venue
        self.venue_id = venue_id
        self.raw_venue_text = raw_venue_text
        self.visibility = visibility
        self.description_public = description_public
        self.description_close_friends = description_close_friends
        self.price = price
        self.cancelled_at = cancelled_at
        self.alerts: List[Alert] = []
        self.events: List[events.Event] = []

    @classmethod
    def from_confirmed_draft(cls, draft: EventDraft) -> "ScheduledEvent":
        if not draft.is_confirmed:
            raise InvariantViolation("Cannot create ScheduledEvent from unconfirmed draft")
        if draft.start_time is None:
            raise InvariantViolation("Draft must have a start time before scheduling")
        evt = cls(
            id=uuid4(),
            user_id=draft.user_id,
            title=draft.title,
            start_time=draft.start_time,
            venue=draft.venue,
            raw_venue_text=draft.venue,
            visibility=EventVisibility.PRIVATE,
            price=draft.price,
        )
        evt.events.append(events.EventConfirmed(event_id=evt.id, user_id=evt.user_id))
        return evt

    def schedule_traffic_alert(self, *, traffic: TrafficCondition) -> None:
        now = datetime.now(timezone.utc)
        if self.start_time <= now:
            raise PastEventError("Cannot alert on a past event")

        depart_at = self.start_time - timedelta(seconds=int(traffic.travel_seconds))
        alert = Alert(
            alert_type=AlertType.TRAFFIC_ALERT,
            trigger_at=depart_at,
            message=f"Leave now for {self.title}",
        )
        self.alerts = [a for a in self.alerts if a.alert_type != AlertType.TRAFFIC_ALERT]
        self.alerts.append(alert)
        self.events.append(events.AlertScheduled(event_id=self.id, trigger_at=alert.trigger_at))

    def schedule_reminder_alert(self, *, minutes_before: int) -> None:
        now = datetime.now(timezone.utc)
        if self.start_time <= now:
            raise PastEventError("Cannot alert on a past event")
        if minutes_before <= 0:
            raise InvariantViolation("minutes_before must be positive")

        trigger_at = self.start_time - timedelta(minutes=int(minutes_before))
        if trigger_at <= now:
            raise InvariantViolation("Reminder trigger must be in the future")

        alert = Alert(
            alert_type=AlertType.REMINDER,
            trigger_at=trigger_at,
            message=f"Reminder: {self.title} starts soon",
        )
        self.alerts = [a for a in self.alerts if a.alert_type != AlertType.REMINDER]
        self.alerts.append(alert)
        self.events.append(events.AlertScheduled(event_id=self.id, trigger_at=alert.trigger_at))

    def cancel(self) -> None:
        if self.cancelled_at is not None:
            return
        self.cancelled_at = datetime.now(timezone.utc)
        self.alerts.clear()
        self.events.append(events.EventCancelled(event_id=self.id))

