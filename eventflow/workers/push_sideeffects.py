from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from uuid import UUID

import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from eventflow.adapters.orm import start_mappers
from eventflow.config import get_settings
from eventflow.service_layer.unit_of_work import SqlAlchemyUnitOfWork
from eventflow.workers.scheduler import build_scheduler_client

_log = logging.getLogger(__name__)


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

    while True:
        try:
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
                    if getattr(evt, "cancelled_at", None) is not None:
                        uow.commit()
                        continue
                    venue_lat = venue_lng = None
                    vid = getattr(evt, "venue_id", None)
                    sess = getattr(uow, "session", None)
                    if sess is not None and vid is not None:
                        row = sess.execute(
                            text("SELECT lat, lng FROM venues WHERE id = :id LIMIT 1"),
                            {"id": str(vid)},
                        ).first()
                        if row is not None:
                            venue_lat, venue_lng = float(row[0]), float(row[1])
                    job_key = f"{event_id}:{int(trigger_at.timestamp())}"
                    scheduler_client.schedule_push_due(
                        job_key=job_key,
                        user_id=str(evt.user_id),
                        run_at=trigger_at,
                        title="Leave now",
                        body=f"Time to leave for {evt.title}",
                        event_id=str(event_id),
                        venue_lat=venue_lat,
                        venue_lng=venue_lng,
                        action="leave_now",
                    )
                    uow.commit()
        except Exception:
            _log.exception("push_sideeffects listener crashed, reconnecting in 5s")
            time.sleep(5)
            r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            pubsub = r.pubsub()
            pubsub.subscribe("alert.scheduled")


if __name__ == "__main__":
    main()

