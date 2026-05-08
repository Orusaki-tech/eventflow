from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

import redis
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import and_, create_engine, select
from sqlalchemy.orm import sessionmaker

from eventflow.adapters.orm import alerts, scheduled_events, start_mappers
from eventflow.config import get_settings


def run_traffic_check(*, event_id: str, user_id: str) -> None:
    settings = get_settings()
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is required")

    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    r.publish(
        "event.due_for_traffic_check",
        json.dumps({"event_id": event_id, "user_id": user_id}),
    )


def run_push_due(*, user_id: str, title: str, body: str) -> None:
    settings = get_settings()
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is required")

    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    r.publish(
        "push.due",
        json.dumps({"user_id": user_id, "title": title, "body": body}),
    )


@dataclass(frozen=True)
class SchedulerClient:
    """
    Writes traffic-check jobs into the persistent APScheduler jobstore.

    This client starts its scheduler in paused mode so it will not execute jobs
    in the API process; execution is owned by the separate scheduler service.
    """

    scheduler: BackgroundScheduler

    def schedule_traffic_check(self, *, event_id: UUID, user_id: UUID, run_at: datetime) -> None:
        job_id = f"traffic:{event_id}"
        self.scheduler.add_job(
            func=run_traffic_check,
            trigger="date",
            run_date=run_at,
            id=job_id,
            replace_existing=True,
            kwargs={"event_id": str(event_id), "user_id": str(user_id)},
        )

    def cancel_traffic_check(self, *, event_id: UUID) -> None:
        job_id = f"traffic:{event_id}"
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            return

    def schedule_push_due(self, *, job_key: str, user_id: str, run_at: datetime, title: str, body: str) -> None:
        job_id = f"push:{job_key}"
        self.scheduler.add_job(
            func=run_push_due,
            trigger="date",
            run_date=run_at,
            id=job_id,
            replace_existing=True,
            kwargs={"user_id": user_id, "title": title, "body": body},
        )

    def cancel_push_due(self, *, job_key: str) -> None:
        job_id = f"push:{job_key}"
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            return


def build_scheduler_client() -> SchedulerClient:
    settings = get_settings()
    if not settings.effective_db_url:
        raise RuntimeError("DB_URL is required")

    jobstores = {"default": SQLAlchemyJobStore(url=settings.effective_db_url, tablename="apscheduler_jobs")}
    scheduler = BackgroundScheduler(jobstores=jobstores)
    scheduler.start(paused=True)
    return SchedulerClient(scheduler=scheduler)


def build_service_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    if not settings.effective_db_url:
        raise RuntimeError("DB_URL is required")

    jobstores = {"default": SQLAlchemyJobStore(url=settings.effective_db_url, tablename="apscheduler_jobs")}
    job_defaults = {"coalesce": True, "misfire_grace_time": 60 * 60, "max_instances": 1}
    return AsyncIOScheduler(jobstores=jobstores, job_defaults=job_defaults, timezone=timezone.utc)


def _recovery_sweep(*, schedule: AsyncIOScheduler) -> None:
    settings = get_settings()
    if not settings.effective_db_url:
        return

    start_mappers()
    engine = create_engine(settings.effective_db_url, future=True)
    Session = sessionmaker(bind=engine, future=True)

    now = datetime.now(timezone.utc)
    with Session() as session:
        stmt = (
            select(
                scheduled_events.c.id,
                scheduled_events.c.user_id,
                scheduled_events.c.start_time,
            )
            .select_from(
                scheduled_events.outerjoin(
                    alerts,
                    and_(
                        alerts.c.event_id == scheduled_events.c.id,
                        alerts.c.alert_type == "TRAFFIC_ALERT",
                    ),
                )
            )
            .where(scheduled_events.c.start_time > now)
            .where(scheduled_events.c.cancelled_at.is_(None))
            .where(alerts.c.id.is_(None))
        )
        rows = session.execute(stmt).all()

    for row in rows:
        run_at = max(now + timedelta(seconds=1), row.start_time - timedelta(hours=3))
        schedule.add_job(
            func=run_traffic_check,
            trigger="date",
            run_date=run_at,
            id=f"traffic:{row.id}",
            replace_existing=True,
            kwargs={"event_id": str(row.id), "user_id": str(row.user_id)},
        )


async def main() -> None:
    settings = get_settings()
    if not settings.effective_db_url:
        raise RuntimeError("DB_URL is required for scheduler worker")
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is required for scheduler worker")

    sched = build_service_scheduler()
    _recovery_sweep(schedule=sched)
    sched.start()

    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())

