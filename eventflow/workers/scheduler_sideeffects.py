from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

import redis
from redis.client import PubSub
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from eventflow.adapters.orm import start_mappers
from eventflow.config import get_settings
from eventflow.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from eventflow.workers.scheduler import build_scheduler_client


def compute_traffic_check_run_at(*, start_time: datetime, now: datetime) -> datetime:
    return max(now + timedelta(seconds=1), start_time - timedelta(hours=3))


def handle_message(
    *,
    topic: str,
    payload: dict,
    uow: SqlAlchemyUnitOfWork,
    scheduler_client,
) -> None:
    if topic == "event.confirmed":
        event_id = UUID(payload["event_id"])
        with uow:
            evt = uow.events.get(event_id)
            if evt is None:
                uow.commit()
                return
            run_at = compute_traffic_check_run_at(start_time=evt.start_time, now=datetime.now(timezone.utc))
            scheduler_client.schedule_traffic_check(event_id=evt.id, user_id=evt.user_id, run_at=run_at)
            uow.commit()
        return

    if topic == "event.cancelled":
        event_id = UUID(payload["event_id"])
        scheduler_client.cancel_traffic_check(event_id=event_id)
        return


def run_until_processed(
    *,
    pubsub: PubSub,
    uow: SqlAlchemyUnitOfWork,
    scheduler_client,
    target_messages: int,
    timeout_s: float = 5.0,
) -> int:
    processed = 0
    deadline = datetime.now(timezone.utc).timestamp() + timeout_s
    while processed < target_messages and datetime.now(timezone.utc).timestamp() < deadline:
        msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)
        if not msg:
            continue
        topic = msg.get("channel")
        if not isinstance(topic, str):
            continue
        payload = json.loads(msg["data"])
        handle_message(topic=topic, payload=payload, uow=uow, scheduler_client=scheduler_client)
        processed += 1
    return processed


def main() -> None:
    settings = get_settings()
    if not settings.effective_db_url:
        raise RuntimeError("DB_URL is required for scheduler_sideeffects worker")
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is required for scheduler_sideeffects worker")

    start_mappers()
    engine = create_engine(settings.effective_db_url, future=True)
    session_factory = sessionmaker(bind=engine, future=True)
    uow = SqlAlchemyUnitOfWork(session_factory)

    scheduler_client = build_scheduler_client()
    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe("event.confirmed", "event.cancelled")

    for msg in pubsub.listen():
        if msg.get("type") != "message":
            continue
        topic = msg.get("channel")
        payload = json.loads(msg["data"])
        if isinstance(topic, str):
            handle_message(topic=topic, payload=payload, uow=uow, scheduler_client=scheduler_client)


if __name__ == "__main__":
    main()

