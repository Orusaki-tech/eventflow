from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from eventflow.adapters.orm import metadata_obj, start_mappers
from eventflow.domain.model import EventDraft
from eventflow.domain import commands
from eventflow.service_layer import messagebus
from eventflow.service_layer.unit_of_work import SqlAlchemyUnitOfWork


TEST_DB_URL_ENV = "EVENTFLOW_TEST_DB_URL"


@pytest.mark.skipif(not os.getenv(TEST_DB_URL_ENV), reason="Set EVENTFLOW_TEST_DB_URL to run integration tests")
def test_confirm_draft_persists_scheduled_event():
    start_mappers()
    engine = create_engine(os.environ[TEST_DB_URL_ENV], future=True)
    metadata_obj.drop_all(engine)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    metadata_obj.create_all(engine)

    session_factory = sessionmaker(bind=engine, future=True)
    uow = SqlAlchemyUnitOfWork(session_factory)

    user_id = uuid4()
    draft = EventDraft.new(
        user_id=user_id,
        title="Integration Test Event",
        start_time=datetime.now(timezone.utc),
        venue="Somewhere",
        confidence_score=0.8,
    )

    with uow:
        uow.drafts.add(draft)
        uow.commit()

    event_id = messagebus.handle(commands.ConfirmEventDraft(draft_id=draft.id, user_id=user_id), uow)
    assert event_id is not None

