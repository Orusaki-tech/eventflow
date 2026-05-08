from __future__ import annotations

from uuid import uuid4

from eventflow.service_layer import views


class _FakeRow:
    def __init__(self, mapping: dict):
        self._mapping = mapping


class _FakeResult(list):
    pass


class _CapturingSession:
    def __init__(self) -> None:
        self.last_sql: str | None = None
        self.last_params: dict | None = None

    def execute(self, stmt, params=None):
        # `stmt` is sqlalchemy.text() object; str(stmt) contains SQL.
        self.last_sql = str(stmt)
        self.last_params = dict(params or {})
        return _FakeResult([_FakeRow({"id": "x"})])


def test_get_upcoming_events_sql_includes_shared_public_and_window():
    s = _CapturingSession()
    user_id = uuid4()

    views.get_upcoming_events(user_id=user_id, session=s, days_ahead=30, limit=50)

    assert s.last_sql is not None
    sql = s.last_sql
    assert "group_memberships" in sql
    assert "event_shares" in sql
    assert "e.visibility = 'public'" in sql
    assert "CURRENT_TIMESTAMP + (:days_ahead || ' days')::interval" in sql
    assert ":priority_days" in sql
    assert s.last_params == {"user_id": str(user_id), "limit": 50, "days_ahead": 30, "priority_days": 30}

