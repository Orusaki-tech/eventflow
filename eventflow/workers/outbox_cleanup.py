from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from eventflow.adapters.orm import outbox_messages, start_mappers
from eventflow.config import get_settings


def main() -> None:
    settings = get_settings()
    if not settings.effective_db_url:
        raise RuntimeError("DB_URL is required for outbox_cleanup")

    start_mappers()
    engine = create_engine(settings.effective_db_url, future=True)
    Session = sessionmaker(bind=engine, future=True)

    # Default retention: keep published outbox rows for 7 days.
    retention_days = 7
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    with Session() as session:
        session.execute(
            delete(outbox_messages).where(
                (outbox_messages.c.published_at.is_not(None)) & (outbox_messages.c.published_at < cutoff)
            )
        )
        session.commit()


if __name__ == "__main__":
    main()

