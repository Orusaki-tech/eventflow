from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from eventflow.domain import commands
from eventflow.domain.exceptions import PermissionDenied
from eventflow.domain.model import EventDraft
from eventflow.service_layer import messagebus
from eventflow.service_layer.unit_of_work import FakeUnitOfWork


def test_confirm_draft_denies_wrong_user():
    owner_id = uuid4()
    attacker_id = uuid4()
    draft = EventDraft.new(
        user_id=owner_id,
        title="Secret Event",
        start_time=datetime.now(timezone.utc),
        venue="Somewhere",
        confidence_score=0.7,
    )

    uow = FakeUnitOfWork()
    uow.drafts.add(draft)

    with pytest.raises(PermissionDenied):
        messagebus.handle(commands.ConfirmEventDraft(draft_id=draft.id, user_id=attacker_id), uow)

