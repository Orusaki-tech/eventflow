from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from eventflow.domain import commands
from eventflow.domain.exceptions import InvariantViolation, PermissionDenied
from eventflow.domain.model import EventDraft
from eventflow.service_layer import handlers
from eventflow.service_layer.unit_of_work import FakeUnitOfWork


def test_update_draft_changes_fields():
    user_id = uuid4()
    draft = EventDraft.new(
        user_id=user_id,
        title="Old",
        start_time=datetime.now(timezone.utc),
        venue="A",
        confidence_score=0.7,
    )

    uow = FakeUnitOfWork()
    uow.drafts.add(draft)

    new_time = draft.start_time + timedelta(days=1)
    out = handlers.handle_update_event_draft(
        commands.UpdateEventDraft(draft_id=draft.id, user_id=user_id, title="New", start_time=new_time),
        uow,
    )
    assert out["title"] == "New"
    assert out["start_time"] == new_time
    assert uow.committed is True


def test_update_draft_rejects_edit_after_confirm():
    user_id = uuid4()
    draft = EventDraft.new(
        user_id=user_id,
        title="T",
        start_time=datetime.now(timezone.utc),
        venue="V",
        confidence_score=0.7,
    )
    draft.confirm()

    uow = FakeUnitOfWork()
    uow.drafts.add(draft)

    with pytest.raises(InvariantViolation):
        handlers.handle_update_event_draft(commands.UpdateEventDraft(draft_id=draft.id, user_id=user_id, title="X"), uow)


def test_update_draft_rejects_wrong_user():
    owner = uuid4()
    other = uuid4()
    draft = EventDraft.new(
        user_id=owner,
        title="T",
        start_time=datetime.now(timezone.utc),
        venue="V",
        confidence_score=0.7,
    )
    uow = FakeUnitOfWork()
    uow.drafts.add(draft)

    with pytest.raises(PermissionDenied):
        handlers.handle_update_event_draft(commands.UpdateEventDraft(draft_id=draft.id, user_id=other, title="X"), uow)

