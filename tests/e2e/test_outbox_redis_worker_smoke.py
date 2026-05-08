from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from eventflow.adapters.event_publisher import RedisEventPublisher
from eventflow.adapters.orm import metadata_obj, start_mappers
from eventflow.adapters.repository import OutboxMessage
from eventflow.config import get_settings
from eventflow.domain.model import ScheduledEvent
from eventflow.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from eventflow.workers import scheduler_sideeffects
from eventflow.workers.outbox_publisher import publish_once


E2E_DB_URL_ENV = "EVENTFLOW_E2E_DB_URL"
E2E_REDIS_URL_ENV = "EVENTFLOW_E2E_REDIS_URL"


@pytest.mark.skipif(
    not os.getenv(E2E_DB_URL_ENV) or not os.getenv(E2E_REDIS_URL_ENV),
    reason="Set EVENTFLOW_E2E_DB_URL and EVENTFLOW_E2E_REDIS_URL to run e2e outbox/redis/worker smoke test",
)
def test_confirm_and_cancel_flow_is_delivered_via_outbox_and_consumed_by_worker(monkeypatch):
    """
    Smoke test the reliability pipeline:

    DB transaction writes outbox rows -> outbox publisher publishes to Redis -> worker consumes topics -> scheduler side-effect occurs.
    """

    get_settings.cache_clear()
    monkeypatch.setenv("DB_URL", os.environ[E2E_DB_URL_ENV])
    monkeypatch.setenv("REDIS_URL", os.environ[E2E_REDIS_URL_ENV])

    start_mappers()
    engine = create_engine(os.environ[E2E_DB_URL_ENV], future=True)
    metadata_obj.drop_all(engine)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    metadata_obj.create_all(engine)

    Session = sessionmaker(bind=engine, future=True)
    uow = SqlAlchemyUnitOfWork(Session)

    r = redis.Redis.from_url(os.environ[E2E_REDIS_URL_ENV], decode_responses=True)
    r.flushdb()
    pubsub = r.pubsub()
    pubsub.subscribe("event.confirmed", "event.cancelled")

    user_id = uuid4()
    event_id = uuid4()
    start_time = datetime.now(timezone.utc) + timedelta(hours=6)

    with uow:
        uow.events.add(ScheduledEvent(id=event_id, user_id=user_id, title="T", start_time=start_time, venue="V"))
        now = datetime.now(timezone.utc)
        uow.outbox.add(
            OutboxMessage(
                topic="event.confirmed",
                payload={"event_type": "eventflow.domain.events.EventConfirmed", "event_id": str(event_id)},
                occurred_at=now,
            )
        )
        uow.outbox.add(
            OutboxMessage(
                topic="event.cancelled",
                payload={"event_type": "eventflow.domain.events.EventCancelled", "event_id": str(event_id)},
                occurred_at=now + timedelta(milliseconds=1),
            )
        )
        uow.commit()

    publisher = RedisEventPublisher(os.environ[E2E_REDIS_URL_ENV])
    published = publish_once(uow=uow, publisher=publisher, batch_size=100)
    assert published == 2

    scheduler_client = scheduler_sideeffects.build_scheduler_client()
    processed = scheduler_sideeffects.run_until_processed(
        pubsub=pubsub,
        uow=uow,
        scheduler_client=scheduler_client,
        target_messages=2,
        timeout_s=8.0,
    )
    assert processed == 2

    # The cancel should remove the traffic job if it was created by the confirm.
    job_id = f"traffic:{event_id}"
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, job_state FROM apscheduler_jobs WHERE id = :id").bindparams(id=job_id)
        ).first()
    assert row is None

