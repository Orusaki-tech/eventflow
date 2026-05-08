from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from eventflow.workers.scheduler_sideeffects import compute_traffic_check_run_at


def test_schedule_traffic_monitor_schedules_job():
    _ = uuid4()  # stable import shape; no longer used in worker-timing tests
    now = datetime.now(timezone.utc)
    start_time = now + timedelta(hours=10)
    run_at = compute_traffic_check_run_at(start_time=start_time, now=now)
    assert abs((run_at - (start_time - timedelta(hours=3))).total_seconds()) < 1


def test_schedule_traffic_monitor_respects_3h_rule_with_floor_of_now_plus_epsilon():
    now = datetime.now(timezone.utc)
    start_time = now + timedelta(minutes=30)
    run_at = compute_traffic_check_run_at(start_time=start_time, now=now)
    assert abs((run_at - (now + timedelta(seconds=1))).total_seconds()) < 1

