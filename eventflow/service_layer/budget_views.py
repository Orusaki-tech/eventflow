from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text

from eventflow.domain.price_budget import budget_band, parse_price_to_minor_units


def utc_bounds_for_calendar_month(*, year: int, month: int, tz_offset_minutes: int) -> tuple[datetime, datetime]:
    """
    Month boundaries in the user's local calendar, converted to UTC for comparing timestamptz start_time.

    tz_offset_minutes follows the same convention as /events/today (east-positive offset from UTC).
    """
    delta_minutes = -tz_offset_minutes
    local_start = datetime(year, month, 1, 0, 0, 0)
    if month == 12:
        local_end = datetime(year + 1, 1, 1, 0, 0, 0)
    else:
        local_end = datetime(year, month + 1, 1, 0, 0, 0)

    utc_start = (local_start + timedelta(minutes=delta_minutes)).replace(tzinfo=timezone.utc)
    utc_end = (local_end + timedelta(minutes=delta_minutes)).replace(tzinfo=timezone.utc)
    return utc_start, utc_end


def month_budget_summary(
    *,
    session: Any,
    user_id: UUID,
    year: int,
    month: int,
    tz_offset_minutes: int,
    budget_minor_units: int | None,
) -> dict[str, Any]:
    start_utc, end_utc = utc_bounds_for_calendar_month(
        year=year, month=month, tz_offset_minutes=tz_offset_minutes
    )
    rows = session.execute(
        text(
            """
            SELECT e.price
            FROM scheduled_events e
            WHERE e.user_id = :user_id
              AND e.cancelled_at IS NULL
              AND e.start_time >= :start_utc
              AND e.start_time < :end_utc
            """
        ),
        {
            "user_id": str(user_id),
            "start_utc": start_utc,
            "end_utc": end_utc,
        },
    ).fetchall()

    spent_minor = 0
    priced_events = 0
    unpriced_events = 0
    for (p,) in rows:
        minor = parse_price_to_minor_units(p)
        if minor is None:
            unpriced_events += 1
            continue
        spent_minor += minor
        priced_events += 1

    band = budget_band(spent_minor=spent_minor, budget_minor=budget_minor_units)

    return {
        "year": year,
        "month": month,
        "budget_minor_units": budget_minor_units,
        "spent_minor_units": spent_minor,
        "priced_events_count": priced_events,
        "unpriced_events_count": unpriced_events,
        "events_total_count": len(rows),
        "band": band,
    }
