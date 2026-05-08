from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from eventflow.domain import commands
from eventflow.domain.model import EventDraft, ScheduledEvent
from eventflow.service_layer import messagebus
from eventflow.service_layer.unit_of_work import FakeUnitOfWork


def test_confirm_event_enqueues_outbox_message():
    user_id = uuid4()
    draft = EventDraft.new(
        user_id=user_id,
        title="T",
        start_time=datetime.now(timezone.utc) + timedelta(hours=1),
        venue="V",
        confidence_score=0.9,
    )
    draft.confirm()

    uow = FakeUnitOfWork()
    uow.drafts.add(draft)

    messagebus.handle(commands.ConfirmEventDraft(draft_id=draft.id, user_id=user_id), uow)
    msgs = list(uow.outbox._messages.values())  # type: ignore[attr-defined]
    assert any(m.topic == "event.confirmed" for m in msgs)


def test_cancel_event_enqueues_outbox_message():
    user_id = uuid4()
    event_id = uuid4()
    start_time = datetime.now(timezone.utc) + timedelta(hours=1)
    evt = ScheduledEvent(id=event_id, user_id=user_id, title="T", start_time=start_time, venue="V")

    uow = FakeUnitOfWork()
    with uow:
        uow.events.add(evt)
        uow.commit()

    messagebus.handle(commands.CancelEvent(event_id=event_id, user_id=user_id), uow)
    msgs = list(uow.outbox._messages.values())  # type: ignore[attr-defined]
    assert any(m.topic == "event.cancelled" for m in msgs)


def test_alert_scheduled_enqueues_outbox_message():
    user_id = uuid4()
    event_id = uuid4()
    start_time = datetime.now(timezone.utc) + timedelta(hours=2)

    uow = FakeUnitOfWork()
    with uow:
        uow.events.add(ScheduledEvent(id=event_id, user_id=user_id, title="T", start_time=start_time, venue="V"))
        uow.commit()

    messagebus.handle(commands.ScheduleReminderAlert(event_id=event_id, user_id=user_id, minutes_before=15), uow)
    msgs = list(uow.outbox._messages.values())  # type: ignore[attr-defined]
    assert any(m.topic == "alert.scheduled" for m in msgs)

