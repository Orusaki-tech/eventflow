from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from eventflow.domain import commands
from eventflow.service_layer import messagebus
from eventflow.service_layer.unit_of_work import FakeUnitOfWork


def test_upsert_community_event_enqueues_outbox_message():
    user_id = uuid4()
    uow = FakeUnitOfWork()

    out = messagebus.handle(
        commands.UpsertCommunityEvent(
            user_id=user_id,
            source="manual",
            title="Community",
            start_time=datetime.now(timezone.utc),
            venue="Town",
            description="Desc",
        ),
        uow,
    )
    assert out["community_event_id"] is not None
    # FakeOutboxRepository stores messages in _messages
    assert any(m.topic == "community_event.upserted" for m in uow.outbox._messages.values())

