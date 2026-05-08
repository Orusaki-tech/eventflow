from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from eventflow.adapters.orm import start_mappers
from eventflow.config import get_settings
from eventflow.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from eventflow.workers.scheduler import build_scheduler_client


def main() -> None:
    settings = get_settings()
    if not settings.effective_db_url:
        raise RuntimeError("DB_URL is required for push_sideeffects worker")
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is required for push_sideeffects worker")

    start_mappers()
    engine = create_engine(settings.effective_db_url, future=True)
    session_factory = sessionmaker(bind=engine, future=True)
    uow = SqlAlchemyUnitOfWork(session_factory)

    scheduler_client = build_scheduler_client()
    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe("alert.scheduled")

    for msg in pubsub.listen():
        if msg.get("type") != "message":
            continue
        payload = json.loads(msg["data"])
        event_id = UUID(payload["event_id"])
        trigger_at_iso = payload["trigger_at"]
        trigger_at = datetime.fromisoformat(trigger_at_iso)
        if trigger_at.tzinfo is None:
            trigger_at = trigger_at.replace(tzinfo=timezone.utc)

        with uow:
            evt = uow.events.get(event_id)
            if evt is None:
                uow.commit()
                continue
            job_key = f"{event_id}:{int(trigger_at.timestamp())}"
            scheduler_client.schedule_push_due(
                job_key=job_key,
                user_id=str(evt.user_id),
                run_at=trigger_at,
                title="EventFlow alert",
                body="Leave now",
            )
            uow.commit()


if __name__ == "__main__":
    main()

