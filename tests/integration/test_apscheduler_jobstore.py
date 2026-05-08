from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta, timezone

import pytest
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler


TEST_DB_URL_ENV = "EVENTFLOW_TEST_DB_URL"


@pytest.mark.skipif(not os.getenv(TEST_DB_URL_ENV), reason="Set EVENTFLOW_TEST_DB_URL to run integration tests")
def test_apscheduler_jobstore_persists_across_restart():
    url = os.environ[TEST_DB_URL_ENV]

    fired = threading.Event()

    def job():  # noqa: ANN001
        fired.set()

    jobstores = {"default": SQLAlchemyJobStore(url=url, tablename="apscheduler_jobs")}
    s1 = BackgroundScheduler(jobstores=jobstores, timezone=timezone.utc)
    s1.start(paused=True)
    s1.add_job(job, trigger="date", run_date=datetime.now(timezone.utc) + timedelta(milliseconds=200), id="t1")
    s1.shutdown(wait=False)

    # A fresh scheduler instance should be able to read the same job from the DB.
    s2 = BackgroundScheduler(jobstores=jobstores, timezone=timezone.utc)
    s2.start()
    try:
        assert s2.get_job("t1") is not None
        fired.wait(timeout=5)
        assert fired.is_set() is True
    finally:
        s2.shutdown(wait=False)

