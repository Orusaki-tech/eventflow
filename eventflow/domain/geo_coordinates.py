"""Validate geographic coordinates used for venue pins and ETA (WGS84)."""

from __future__ import annotations

import math


class InvalidCoordinatesError(ValueError):
    """Raised when lat/lng are out of range or unusable for routing."""


def validate_wgs84_coordinates(
    lat: float,
    lng: float,
    *,
    reject_null_island: bool = True,
) -> None:
    """
    Ensure coordinates are finite and within WGS84 bounds so Distance Matrix / ETA behave correctly.

    Google Maps expects latitude first, then longitude. We validate both ranges explicitly so
    swapped or corrupted values from upstream APIs fail fast instead of producing nonsense ETAs.
    """
    if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
        raise InvalidCoordinatesError("latitude and longitude must be numbers")
    lat_f = float(lat)
    lng_f = float(lng)
    if math.isnan(lat_f) or math.isnan(lng_f) or math.isinf(lat_f) or math.isinf(lng_f):
        raise InvalidCoordinatesError("coordinates must be finite numbers")
    if lat_f < -90.0 or lat_f > 90.0:
        raise InvalidCoordinatesError("latitude must be between -90 and 90")
    if lng_f < -180.0 or lng_f > 180.0:
        raise InvalidCoordinatesError("longitude must be between -180 and 180")
    if reject_null_island and abs(lat_f) < 1e-9 and abs(lng_f) < 1e-9:
        raise InvalidCoordinatesError("coordinates (0, 0) are not accepted; choose a real location")


def assert_lat_lng_order_label() -> str:
    """Human-readable reminder for API docs (latitude, longitude)."""
    return "Always store and transmit latitude (φ) then longitude (λ); Maps URLs use the same order in comma-separated pairs."
