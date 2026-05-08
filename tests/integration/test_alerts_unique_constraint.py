from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from eventflow.adapters.orm import metadata_obj, start_mappers
from eventflow.domain.model import Alert, AlertType, ScheduledEvent


TEST_DB_URL_ENV = "EVENTFLOW_TEST_DB_URL"


@pytest.mark.skipif(not os.getenv(TEST_DB_URL_ENV), reason="Set EVENTFLOW_TEST_DB_URL to run integration tests")
def test_alerts_unique_constraint_one_per_event_and_type():
    start_mappers()
    engine = create_engine(os.environ[TEST_DB_URL_ENV], future=True)
    metadata_obj.drop_all(engine)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    metadata_obj.create_all(engine)

    Session = sessionmaker(bind=engine, future=True)
    session = Session()
    try:
        user_id = uuid4()
        event_id = uuid4()
        start_time = datetime.now(timezone.utc) + timedelta(hours=2)
        evt = ScheduledEvent(id=event_id, user_id=user_id, title="T", start_time=start_time, venue="V")
        session.add(evt)
        session.commit()

        a1 = Alert(alert_type=AlertType.REMINDER, trigger_at=start_time - timedelta(minutes=30), message="m1")
        a2 = Alert(alert_type=AlertType.REMINDER, trigger_at=start_time - timedelta(minutes=10), message="m2")

        evt.alerts.append(a1)
        session.commit()

        evt.alerts.append(a2)
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.close()

