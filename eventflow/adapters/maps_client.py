from __future__ import annotations

import abc
from dataclasses import dataclass
from datetime import datetime

import httpx


class AbstractMapsClient(abc.ABC):
    @abc.abstractmethod
    def estimate_travel_seconds(
        self,
        *,
        origin: str,
        destination: str,
        depart_at: datetime,
    ) -> int:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def estimate_distance_and_duration_seconds(
        self,
        *,
        origin_lat: float,
        origin_lng: float,
        destination_lat: float,
        destination_lng: float,
        depart_at: datetime,
    ) -> tuple[int, int, int | None]:  # (distance_m, duration_s, duration_in_traffic_s)
        raise NotImplementedError


@dataclass(frozen=True)
class FakeMapsClient(AbstractMapsClient):
    travel_seconds: int = 1800

    def estimate_travel_seconds(self, *, origin: str, destination: str, depart_at: datetime) -> int:
        return int(self.travel_seconds)

    def estimate_distance_and_duration_seconds(
        self,
        *,
        origin_lat: float,
        origin_lng: float,
        destination_lat: float,
        destination_lng: float,
        depart_at: datetime,
    ) -> tuple[int, int, int | None]:
        return (1000, int(self.travel_seconds), int(self.travel_seconds))


class GoogleMapsClient(AbstractMapsClient):
    def __init__(self, *, api_key: str, base_url: str = "https://maps.googleapis.com"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def estimate_travel_seconds(self, *, origin: str, destination: str, depart_at: datetime) -> int:
        # Distance Matrix API expects depart_at in seconds since epoch.
        depart_ts = int(depart_at.timestamp())
        url = f"{self.base_url}/maps/api/distancematrix/json"
        params = {
            "origins": origin,
            "destinations": destination,
            "departure_time": depart_ts,
            "key": self.api_key,
        }
        resp = httpx.get(url, params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()

        rows = data.get("rows") or []
        if not rows:
            raise RuntimeError("Maps response missing rows")
        elements = rows[0].get("elements") or []
        if not elements:
            raise RuntimeError("Maps response missing elements")
        element = elements[0]
        status = element.get("status")
        if status != "OK":
            raise RuntimeError(f"Maps route status {status}")

        duration = element.get("duration_in_traffic") or element.get("duration")
        if not duration or "value" not in duration:
            raise RuntimeError("Maps response missing duration value")
        return int(duration["value"])

    def estimate_distance_and_duration_seconds(
        self,
        *,
        origin_lat: float,
        origin_lng: float,
        destination_lat: float,
        destination_lng: float,
        depart_at: datetime,
    ) -> tuple[int, int, int | None]:
        depart_ts = int(depart_at.timestamp())
        url = f"{self.base_url}/maps/api/distancematrix/json"
        params = {
            "origins": f"{origin_lat},{origin_lng}",
            "destinations": f"{destination_lat},{destination_lng}",
            "departure_time": depart_ts,
            "key": self.api_key,
        }
        resp = httpx.get(url, params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()

        rows = data.get("rows") or []
        if not rows:
            raise RuntimeError("Maps response missing rows")
        elements = rows[0].get("elements") or []
        if not elements:
            raise RuntimeError("Maps response missing elements")
        element = elements[0]
        status = element.get("status")
        if status != "OK":
            raise RuntimeError(f"Maps route status {status}")

        dist = element.get("distance")
        if not dist or "value" not in dist:
            raise RuntimeError("Maps response missing distance value")

        duration = element.get("duration") or {}
        dur_traffic = element.get("duration_in_traffic") or None
        if "value" not in duration:
            raise RuntimeError("Maps response missing duration value")
        dur_s = int(duration["value"])
        dur_traffic_s = int(dur_traffic["value"]) if isinstance(dur_traffic, dict) and "value" in dur_traffic else None

        return (int(dist["value"]), dur_s, dur_traffic_s)

