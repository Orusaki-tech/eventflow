from __future__ import annotations

from uuid import uuid4

from eventflow.adapters.repository import FakeUserLocationRepository
from eventflow.domain.model import UserLocation


def test_fake_user_location_repo_round_trips():
    user_id = uuid4()
    repo = FakeUserLocationRepository()

    assert repo.get(user_id, "home") is None

    loc = UserLocation(user_id=user_id, label="home", address="1 Main St", lat=1.0, lng=2.0)
    repo.upsert(loc)

    got = repo.get(user_id, "home")
    assert got is not None
    assert got.user_id == user_id
    assert got.label == "home"
    assert got.address == "1 Main St"
    assert got.lat == 1.0
    assert got.lng == 2.0

