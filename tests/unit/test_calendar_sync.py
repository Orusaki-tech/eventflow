from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from eventflow.adapters.calendar_client import CalendarRef, CalendarUpsertResult
from eventflow.adapters.repository import CalendarToken, FakeCalendarTokenRepository
from eventflow.domain import events as domain_events
from eventflow.domain.model import ScheduledEvent
from eventflow.service_layer import handlers
from eventflow.service_layer.unit_of_work import FakeUnitOfWork


class FakeCalendarClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def upsert_event(
        self,
        *,
        user_id: str,
        event: ScheduledEvent,
        access_token: str,
        refresh_token=None,
        token_uri=None,
        external_id=None,
    ):
        self.calls.append(
            {
                "user_id": user_id,
                "event_id": str(event.id),
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_uri": token_uri,
                "external_id": external_id,
            }
        )
        return CalendarUpsertResult(
            ref=CalendarRef(provider="google", external_id="ext-123"),
            access_token="new-access",
            refresh_token="new-refresh",
            expiry=datetime.now(timezone.utc),
        )

    def build_ics(self, *, event: ScheduledEvent) -> str:
        return "BEGIN:VCALENDAR"


def test_sync_to_calendar_no_token_no_upsert():
    user_id = uuid4()
    event_id = uuid4()
    evt = ScheduledEvent(id=event_id, user_id=user_id, title="T", start_time=datetime.now(timezone.utc), venue="V")
    uow = FakeUnitOfWork()
    with uow:
        uow.events.add(evt)
        uow.commit()

    handlers.calendar_client = FakeCalendarClient()
    try:
        handlers.sync_to_calendar(domain_events.EventConfirmed(event_id=event_id, user_id=user_id), uow)
    finally:
        handlers.calendar_client = None

    assert uow.committed is True


def test_sync_to_calendar_with_token_upserts_and_sets_external_id():
    user_id = uuid4()
    event_id = uuid4()
    evt = ScheduledEvent(id=event_id, user_id=user_id, title="T", start_time=datetime.now(timezone.utc), venue="V")
    uow = FakeUnitOfWork(
        calendar_tokens=FakeCalendarTokenRepository(
            [
                CalendarToken(
                    user_id=user_id,
                    provider="google",
                    access_token="a",
                    refresh_token="r",
                    token_uri="https://oauth2.googleapis.com/token",
                    scopes=("https://www.googleapis.com/auth/calendar.events",),
                    expiry=None,
                )
            ]
        )
    )
    with uow:
        uow.events.add(evt)
        uow.commit()

    fake_client = FakeCalendarClient()
    handlers.calendar_client = fake_client
    try:
        handlers.sync_to_calendar(domain_events.EventConfirmed(event_id=event_id, user_id=user_id), uow)
    finally:
        handlers.calendar_client = None

    assert getattr(evt, "calendar_external_id") == "ext-123"
    assert len(fake_client.calls) == 1
    refreshed = uow.calendar_tokens.get(user_id)
    assert refreshed is not None
    assert refreshed.access_token == "new-access"
    assert refreshed.refresh_token == "new-refresh"

