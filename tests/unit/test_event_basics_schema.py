from __future__ import annotations

import pytest
from pydantic import ValidationError

from eventflow.entrypoints.api.schemas import EventBasicsUpdateRequest


def test_event_basics_requires_at_least_one_field() -> None:
    with pytest.raises(ValidationError):
        EventBasicsUpdateRequest.model_validate({})


def test_event_basics_accepts_single_title() -> None:
    b = EventBasicsUpdateRequest.model_validate({"title": "Hello"})
    assert b.title == "Hello"
    assert b.venue is None
    assert b.start_time is None
