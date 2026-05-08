from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from eventflow.domain import commands
from eventflow.domain.exceptions import InvariantViolation
from eventflow.domain.model import EventDraft
from eventflow.service_layer import messagebus
from eventflow.service_layer.unit_of_work import FakeUnitOfWork


def test_confirm_draft_requires_start_time():
    user_id = uuid4()
    draft = EventDraft.new(
        user_id=user_id,
        title="No time yet",
        start_time=None,
        venue="Nairobi",
        confidence_score=0.4,
    )
    uow = FakeUnitOfWork()
    uow.drafts.add(draft)
    with pytest.raises(InvariantViolation, match="date and time"):
        messagebus.handle(commands.ConfirmEventDraft(draft_id=draft.id, user_id=user_id), uow)


def test_confirm_draft_creates_scheduled_event():
    user_id = uuid4()
    draft = EventDraft.new(
        user_id=user_id,
        title="PyConKE 2026",
        start_time=datetime.now(timezone.utc),
        venue="Nairobi",
        confidence_score=0.9,
    )

    uow = FakeUnitOfWork()
    uow.drafts.add(draft)

    event_id = messagebus.handle(commands.ConfirmEventDraft(draft_id=draft.id, user_id=user_id), uow)
    assert event_id is not None
    assert uow.committed is True

