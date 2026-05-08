from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from eventflow.domain.geo_coordinates import InvalidCoordinatesError, validate_wgs84_coordinates
from eventflow.entrypoints.api.schemas import EtaRequest, ResolveVenueRequest, VenueCreateRequest


def test_accepts_typical_us_city() -> None:
    validate_wgs84_coordinates(40.748817, -73.985428)


def test_rejects_null_island_by_default() -> None:
    with pytest.raises(InvalidCoordinatesError):
        validate_wgs84_coordinates(0.0, 0.0)


def test_accepts_null_island_when_opted_in() -> None:
    validate_wgs84_coordinates(0.0, 0.0, reject_null_island=False)


def test_rejects_latitude_out_of_range() -> None:
    with pytest.raises(InvalidCoordinatesError):
        validate_wgs84_coordinates(91.0, 10.0)


def test_rejects_longitude_out_of_range() -> None:
    with pytest.raises(InvalidCoordinatesError):
        validate_wgs84_coordinates(10.0, 181.0)


def test_rejects_nan() -> None:
    with pytest.raises(InvalidCoordinatesError):
        validate_wgs84_coordinates(float("nan"), 0.1)


def test_rejects_inf() -> None:
    with pytest.raises(InvalidCoordinatesError):
        validate_wgs84_coordinates(math.inf, 0.1)


def test_venue_create_request_model_rejects_null_island() -> None:
    with pytest.raises(ValidationError):
        VenueCreateRequest(name="V", lat=0.0, lng=0.0, address=None, place_id=None)


def test_eta_request_model_rejects_invalid_origin() -> None:
    with pytest.raises(ValidationError):
        EtaRequest(lat=200.0, lng=0.0)


def test_resolve_venue_request_near_coordinates_must_be_paired() -> None:
    with pytest.raises(ValidationError):
        ResolveVenueRequest(query="coffee", near_lat=40.0, near_lng=None)


def test_resolve_venue_request_accepts_valid_near_bias() -> None:
    r = ResolveVenueRequest(query="coffee", near_lat=40.7128, near_lng=-74.006)
    assert r.near_lat == pytest.approx(40.7128)
