"""Subscribe to Redis topics from the outbox publisher and sync Google Calendar."""

from __future__ import annotations

import json
import logging
from uuid import UUID

import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from eventflow.adapters.orm import start_mappers
from eventflow.config import get_settings
from eventflow.domain import events as domain_events
from eventflow.entrypoints.dependencies import get_calendar_client
from eventflow.service_layer import handlers
from eventflow.service_layer.unit_of_work import SqlAlchemyUnitOfWork


_log = logging.getLogger(__name__)


def _handle_message(*, topic: str, payload: dict, uow: SqlAlchemyUnitOfWork) -> None:
    if topic == "event.confirmed":
        evt = domain_events.EventConfirmed(
            event_id=UUID(payload["event_id"]),
            user_id=UUID(payload["user_id"]),
            calendar_sync_needed=bool(payload.get("calendar_sync_needed", True)),
        )
        handlers.sync_to_calendar(evt, uow)
        return
    if topic == "event.cancelled":
        evt = domain_events.EventCancelled(event_id=UUID(payload["event_id"]))
        handlers.cancel_calendar_entry(evt, uow)
        return


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    if not settings.effective_db_url:
        raise RuntimeError("DB_URL is required for calendar_sideeffects worker")
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is required for calendar_sideeffects worker")

    start_mappers()
    engine = create_engine(settings.effective_db_url, future=True)
    session_factory = sessionmaker(bind=engine, future=True)

    handlers.calendar_client = get_calendar_client()

    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe("event.confirmed", "event.cancelled")

    for msg in pubsub.listen():
        if msg.get("type") != "message":
            continue
        topic = msg.get("channel")
        if not isinstance(topic, str):
            continue
        try:
            payload = json.loads(msg["data"])
        except Exception:
            _log.exception("calendar_sideeffects.invalid_payload topic=%s", topic)
            continue

        uow = SqlAlchemyUnitOfWork(session_factory)
        with uow:
            try:
                _handle_message(topic=topic, payload=payload, uow=uow)
            except Exception:
                _log.exception("calendar_sideeffects.failed topic=%s", topic)
                uow.rollback()


if __name__ == "__main__":
    main()
