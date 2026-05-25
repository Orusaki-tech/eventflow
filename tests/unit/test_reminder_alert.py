from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from eventflow.domain import commands
from eventflow.domain.exceptions import InvariantViolation, PastEventError
from eventflow.domain.model import AlertType, ScheduledEvent
from eventflow.service_layer import messagebus
from eventflow.service_layer.unit_of_work import FakeUnitOfWork


def test_schedule_reminder_alert_replaces_existing_reminder():
    user_id = uuid4()
    event_id = uuid4()
    start_time = datetime.now(timezone.utc) + timedelta(hours=2)

    evt = ScheduledEvent(id=event_id, user_id=user_id, title="T", start_time=start_time, venue="V")
    evt.schedule_reminder_alert(minutes_before=30)
    assert len([a for a in evt.alerts if a.alert_type == AlertType.REMINDER]) == 1

    evt.schedule_reminder_alert(minutes_before=10)
    reminders = [a for a in evt.alerts if a.alert_type == AlertType.REMINDER]
    assert len(reminders) == 1
    assert abs((reminders[0].trigger_at - (start_time - timedelta(minutes=10))).total_seconds()) < 1


def test_schedule_reminder_alert_validates_minutes_before():
    user_id = uuid4()
    event_id = uuid4()
    start_time = datetime.now(timezone.utc) + timedelta(hours=2)
    evt = ScheduledEvent(id=event_id, user_id=user_id, title="T", start_time=start_time, venue="V")

    with pytest.raises(InvariantViolation):
        evt.schedule_reminder_alert(minutes_before=0)


def test_schedule_reminder_alert_rejects_past_event():
    user_id = uuid4()
    event_id = uuid4()
    start_time = datetime.now(timezone.utc) - timedelta(minutes=1)
    evt = ScheduledEvent(id=event_id, user_id=user_id, title="T", start_time=start_time, venue="V")

    with pytest.raises(PastEventError):
        evt.schedule_reminder_alert(minutes_before=10)


def test_schedule_reminder_alert_command_emits_alert_scheduled_event():
    user_id = uuid4()
    event_id = uuid4()
    start_time = datetime.now(timezone.utc) + timedelta(hours=2)

    uow = FakeUnitOfWork()
    with uow:
        uow.events.add(ScheduledEvent(id=event_id, user_id=user_id, title="T", start_time=start_time, venue="V"))
        uow.commit()

    messagebus.handle(commands.ScheduleReminderAlert(event_id=event_id, user_id=user_id, minutes_before=15), uow)

    with uow:
        evt = uow.events.get(event_id)
        assert evt is not None
        reminders = [a for a in evt.alerts if a.alert_type == AlertType.REMINDER]
        assert len(reminders) == 1
        assert abs((reminders[0].trigger_at - (start_time - timedelta(minutes=15))).total_seconds()) < 2


def test_schedule_reminder_alert_command_enqueues_outbox_message():
    user_id = uuid4()
    event_id = uuid4()
    start_time = datetime.now(timezone.utc) + timedelta(hours=2)

    uow = FakeUnitOfWork()
    with uow:
        uow.events.add(ScheduledEvent(id=event_id, user_id=user_id, title="T", start_time=start_time, venue="V"))
        uow.commit()

    messagebus.handle(commands.ScheduleReminderAlert(event_id=event_id, user_id=user_id, minutes_before=15), uow)
    assert any(m.topic == "alert.scheduled" for m in uow.outbox._messages.values())

