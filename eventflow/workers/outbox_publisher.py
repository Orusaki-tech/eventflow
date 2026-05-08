from __future__ import annotations

import asyncio
import os
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from eventflow.adapters.event_publisher import AbstractEventPublisher, RedisEventPublisher
from eventflow.adapters.orm import start_mappers
from eventflow.config import get_settings
from eventflow.service_layer.unit_of_work import SqlAlchemyUnitOfWork


@dataclass(frozen=True)
class PublisherConfig:
    poll_interval_s: float = 0.5
    batch_size: int = 100
    lock_ttl_seconds: int = 60
    max_attempts: int = 20
    base_backoff_s: float = 1.0
    max_backoff_s: float = 60.0


def _locked_by() -> str:
    host = socket.gethostname()
    pid = os.getpid()
    return f"{host}:{pid}"


def compute_backoff_s(*, attempts: int, base: float, maximum: float) -> float:
    # attempts is 1-based for failures (1 => base, 2 => 2*base, ...)
    return min(maximum, base * (2 ** max(0, attempts - 1)))


def publish_once(*, uow: SqlAlchemyUnitOfWork, publisher: AbstractEventPublisher, batch_size: int) -> int:
    cfg = PublisherConfig(batch_size=batch_size)
    now = datetime.now(timezone.utc)
    published = 0
    locker = _locked_by()

    with uow:
        msgs = uow.outbox.claim_batch(
            limit=cfg.batch_size,
            locked_by=locker,
            now=now,
            lock_ttl_seconds=cfg.lock_ttl_seconds,
            max_attempts=cfg.max_attempts,
        )
        for msg in msgs:
            try:
                publisher.publish(topic=msg.topic, payload=msg.payload)
            except Exception as e:
                next_attempts = int(getattr(msg, "attempts", 0)) + 1
                backoff = compute_backoff_s(
                    attempts=next_attempts, base=cfg.base_backoff_s, maximum=cfg.max_backoff_s
                )
                uow.outbox.mark_failed(
                    message_id=msg.id,
                    now=now,
                    attempts=next_attempts,
                    next_attempt_at=now + timedelta(seconds=backoff),
                    last_error=repr(e),
                )
                continue

            uow.outbox.mark_published(message_id=msg.id, published_at=now)
            published += 1
        uow.commit()

    return published


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    if not settings.effective_db_url:
        raise RuntimeError("DB_URL is required for outbox_publisher worker")
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is required for outbox_publisher worker")

    start_mappers()
    engine = create_engine(settings.effective_db_url, future=True)
    session_factory = sessionmaker(bind=engine, future=True)
    uow = SqlAlchemyUnitOfWork(session_factory)

    publisher = RedisEventPublisher(settings.redis_url)
    cfg = PublisherConfig()

    while True:
        published = publish_once(uow=uow, publisher=publisher, batch_size=cfg.batch_size)
        if published:
            logging.info("outbox_publisher.published", extra={"count": published})
        if published == 0:
            await asyncio.sleep(cfg.poll_interval_s)


if __name__ == "__main__":
    asyncio.run(main())

