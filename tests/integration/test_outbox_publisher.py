from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from eventflow.adapters.event_publisher import AbstractEventPublisher
from eventflow.adapters.orm import metadata_obj, outbox_messages, start_mappers
from eventflow.adapters.repository import OutboxMessage
from eventflow.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from eventflow.workers.outbox_publisher import compute_backoff_s, publish_once


TEST_DB_URL_ENV = "EVENTFLOW_TEST_DB_URL"


class FakePublisher(AbstractEventPublisher):
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []
        self.fail_first: bool = False

    def publish(self, *, topic: str, payload: dict) -> None:
        if self.fail_first:
            self.fail_first = False
            raise RuntimeError("boom")
        self.published.append((topic, payload))


@pytest.mark.skipif(not os.getenv(TEST_DB_URL_ENV), reason="Set EVENTFLOW_TEST_DB_URL to run integration tests")
def test_outbox_publisher_publishes_and_marks_published():
    start_mappers()
    engine = create_engine(os.environ[TEST_DB_URL_ENV], future=True)
    metadata_obj.drop_all(engine)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    metadata_obj.create_all(engine)

    session_factory = sessionmaker(bind=engine, future=True)
    uow = SqlAlchemyUnitOfWork(session_factory)

    msg = OutboxMessage(topic="event.confirmed", payload={"event_type": "x", "event_id": str(uuid4())}, occurred_at=datetime.now(timezone.utc))
    with uow:
        uow.outbox.add(msg)
        uow.commit()

    pub = FakePublisher()
    published = publish_once(uow=uow, publisher=pub, batch_size=100)
    assert published == 1
    assert len(pub.published) == 1
    assert pub.published[0][0] == "event.confirmed"

    with session_factory() as session:
        row = session.execute(select(outbox_messages.c.published_at).where(outbox_messages.c.id == msg.id)).first()
        assert row is not None
        assert row.published_at is not None


@pytest.mark.skipif(not os.getenv(TEST_DB_URL_ENV), reason="Set EVENTFLOW_TEST_DB_URL to run integration tests")
def test_outbox_publisher_retries_with_backoff_on_failure():
    start_mappers()
    engine = create_engine(os.environ[TEST_DB_URL_ENV], future=True)
    metadata_obj.drop_all(engine)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    metadata_obj.create_all(engine)

    session_factory = sessionmaker(bind=engine, future=True)
    uow = SqlAlchemyUnitOfWork(session_factory)

    msg = OutboxMessage(topic="event.confirmed", payload={"event_type": "x", "event_id": str(uuid4())}, occurred_at=datetime.now(timezone.utc))
    with uow:
        uow.outbox.add(msg)
        uow.commit()

    pub = FakePublisher()
    pub.fail_first = True

    published = publish_once(uow=uow, publisher=pub, batch_size=100)
    assert published == 0

    with session_factory() as session:
        row = session.execute(
            select(
                outbox_messages.c.attempts,
                outbox_messages.c.last_error,
                outbox_messages.c.next_attempt_at,
                outbox_messages.c.published_at,
            ).where(outbox_messages.c.id == msg.id)
        ).first()
        assert row is not None
        assert row.attempts == 1
        assert row.published_at is None
        assert row.last_error is not None
        assert row.next_attempt_at is not None

    # Fast-forward by setting next_attempt_at in the past and ensure publish succeeds.
    with session_factory() as session:
        session.execute(
            sa.update(outbox_messages)
            .where(outbox_messages.c.id == msg.id)
            .values(next_attempt_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )
        session.commit()

    published2 = publish_once(uow=uow, publisher=pub, batch_size=100)
    assert published2 == 1


def test_compute_backoff_s_exponential_cap():
    assert compute_backoff_s(attempts=1, base=1.0, maximum=60.0) == 1.0
    assert compute_backoff_s(attempts=2, base=1.0, maximum=60.0) == 2.0
    assert compute_backoff_s(attempts=10, base=1.0, maximum=60.0) == 60.0

