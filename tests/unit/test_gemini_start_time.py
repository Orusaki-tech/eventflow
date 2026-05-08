"""Event timing from LLM JSON: unknown times stay null; structured fields assemble ISO."""

from datetime import datetime, timezone

import pytest

from eventflow.adapters.gemini import (
    damp_confidence_for_timing,
    interpret_event_timing_from_llm_dict,
)


def test_interpret_missing_returns_none() -> None:
    dt, unreliable = interpret_event_timing_from_llm_dict({})
    assert dt is None
    assert unreliable is True


def test_interpret_iso_start_time() -> None:
    dt, unreliable = interpret_event_timing_from_llm_dict({"start_time": "2026-05-10T18:00:00+00:00"})
    assert unreliable is False
    assert dt == datetime(2026, 5, 10, 18, 0, tzinfo=timezone.utc)


def test_am_pm_event_time_prefers_structured_over_wrong_iso() -> None:
    """Poster-style 10AM must not lose to an ISO field that incorrectly uses hour 22."""
    dt, unreliable = interpret_event_timing_from_llm_dict(
        {
            "start_time": "2026-05-10T22:00:00+03:00",
            "event_date": "2026-05-10",
            "event_time": "10AM",
            "timezone": "+03:00",
        }
    )
    assert dt is not None
    assert dt.year == 2026 and dt.month == 5 and dt.day == 10
    assert dt.hour == 10 and dt.minute == 0


def test_numeric_ten_with_iso_twenty_two_detects_am_pm_confusion() -> None:
    """LLM often outputs event_time 10:00 (from 10AM) but start_time with hour 22 — trust structured fields."""
    dt, unreliable = interpret_event_timing_from_llm_dict(
        {
            "start_time": "2026-05-10T22:00:00+03:00",
            "event_date": "2026-05-10",
            "event_time": "10:00",
            "timezone": "+03:00",
        }
    )
    assert dt is not None
    assert dt.hour == 10 and dt.minute == 0
    assert unreliable is True


def test_iso_start_time_wrong_day_prefers_structured_fields() -> None:
    """Poster date in event_date must win over an ISO start_time that echoes capture day."""
    dt, unreliable = interpret_event_timing_from_llm_dict(
        {
            "start_time": "2026-05-07T18:00:00+00:00",
            "event_date": "2026-05-10",
            "event_time": "18:00",
            "timezone": "+00:00",
        }
    )
    assert unreliable is False
    assert dt == datetime(2026, 5, 10, 18, 0, tzinfo=timezone.utc)


def test_iso_start_time_wrong_day_merge_wall_clock_when_no_event_time() -> None:
    dt, unreliable = interpret_event_timing_from_llm_dict(
        {
            "start_time": "2026-05-07T18:00:00+03:00",
            "event_date": "2026-05-10",
            "event_time": None,
            "timezone": None,
        }
    )
    assert dt is not None
    assert dt.year == 2026 and dt.month == 5 and dt.day == 10
    assert dt.hour == 18 and dt.minute == 0
    assert unreliable is True


def test_interpret_z_suffix() -> None:
    dt, unreliable = interpret_event_timing_from_llm_dict({"start_time": "2026-05-10T18:00:00Z"})
    assert dt == datetime(2026, 5, 10, 18, 0, tzinfo=timezone.utc)
    assert unreliable is False


def test_structured_fields_used_when_start_time_string_not_iso() -> None:
    dt, unreliable = interpret_event_timing_from_llm_dict(
        {
            "start_time": "Sunday flyer text only",
            "event_date": "2026-05-10",
            "event_time": "10:00",
            "timezone": "Africa/Nairobi",
        }
    )
    assert dt is not None
    assert dt.hour == 10 and dt.minute == 0
    assert unreliable is False


def test_event_time_accepts_am_pm_in_structured_fields() -> None:
    dt, unreliable = interpret_event_timing_from_llm_dict(
        {
            "event_date": "2026-05-10",
            "event_time": "10:00 AM",
            "timezone": "Africa/Nairobi",
        }
    )
    assert dt is not None
    assert dt.hour == 10 and dt.minute == 0


def test_event_time_pm() -> None:
    dt, _ = interpret_event_timing_from_llm_dict(
        {
            "event_date": "2026-05-10",
            "event_time": "7:30 PM",
            "timezone": "+03:00",
        }
    )
    assert dt is not None
    assert dt.hour == 19 and dt.minute == 30


def test_interpret_structured_date_time_timezone() -> None:
    dt, unreliable = interpret_event_timing_from_llm_dict(
        {
            "start_time": None,
            "event_date": "2026-05-10",
            "event_time": "10:00",
            "timezone": "Africa/Nairobi",
        }
    )
    assert dt is not None
    assert dt.year == 2026 and dt.month == 5 and dt.day == 10
    assert dt.hour == 10 and dt.minute == 0
    assert unreliable is False


def test_interpret_date_only_defaults_noon_unreliable() -> None:
    dt, unreliable = interpret_event_timing_from_llm_dict(
        {
            "event_date": "2026-05-10",
            "event_time": None,
            "timezone": "+03:00",
        }
    )
    assert dt is not None
    assert dt.hour == 12
    assert unreliable is True


def test_interpret_unix_numeric() -> None:
    dt, unreliable = interpret_event_timing_from_llm_dict({"start_time": 1_717_200_000})
    assert unreliable is False
    assert dt == datetime.fromtimestamp(1_717_200_000.0, tz=timezone.utc)


def test_interpret_loose_string_is_unreliable() -> None:
    dt, unreliable = interpret_event_timing_from_llm_dict({"start_time": "May 10, 2026 7:30 PM"})
    assert dt is not None
    assert unreliable is True


def test_damp_when_unknown_time() -> None:
    assert damp_confidence_for_timing(confidence=0.95, start_time=None, unreliable_time=True) == pytest.approx(0.35)


def test_damp_when_unreliable_but_known() -> None:
    dt = datetime(2026, 5, 10, tzinfo=timezone.utc)
    assert damp_confidence_for_timing(confidence=0.95, start_time=dt, unreliable_time=True) == pytest.approx(0.48)


def test_damp_when_reliable() -> None:
    dt = datetime(2026, 5, 10, tzinfo=timezone.utc)
    assert damp_confidence_for_timing(confidence=0.82, start_time=dt, unreliable_time=False) == pytest.approx(0.82)
