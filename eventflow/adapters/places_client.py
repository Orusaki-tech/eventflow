from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any

import httpx

from eventflow.domain.geo_coordinates import InvalidCoordinatesError, validate_wgs84_coordinates


@dataclass(frozen=True)
class PlaceCandidate:
    place_id: str
    name: str
    address: str | None
    lat: float
    lng: float


@dataclass(frozen=True)
class PlacePrediction:
    """Single Google Places Autocomplete suggestion."""

    place_id: str
    description: str
    main_text: str
    secondary_text: str | None


class AbstractPlacesClient(abc.ABC):
    @abc.abstractmethod
    def text_search(
        self,
        *,
        query: str,
        near_lat: float | None = None,
        near_lng: float | None = None,
    ) -> list[PlaceCandidate]:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def autocomplete(
        self,
        *,
        input_text: str,
        near_lat: float | None = None,
        near_lng: float | None = None,
    ) -> list[PlacePrediction]:  # pragma: no cover
        raise NotImplementedError

    @abc.abstractmethod
    def place_details(self, *, place_id: str) -> PlaceCandidate | None:  # pragma: no cover
        raise NotImplementedError


class GooglePlacesClient(AbstractPlacesClient):
    """
    Uses the Places Text Search API to resolve a venue name into a place_id + coordinates.
    """

    def __init__(self, *, api_key: str, base_url: str = "https://maps.googleapis.com") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def text_search(
        self,
        *,
        query: str,
        near_lat: float | None = None,
        near_lng: float | None = None,
    ) -> list[PlaceCandidate]:
        url = f"{self.base_url}/maps/api/place/textsearch/json"
        params: dict[str, Any] = {"query": query, "key": self.api_key}
        if near_lat is not None and near_lng is not None:
            params["location"] = f"{near_lat},{near_lng}"
            params["radius"] = 50000

        resp = httpx.get(url, params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()

        status = data.get("status")
        if status not in {"OK", "ZERO_RESULTS"}:
            raise RuntimeError(f"Places status {status}")
        results = data.get("results") or []
        out: list[PlaceCandidate] = []
        for r in results:
            if not isinstance(r, dict):
                continue
            place_id = r.get("place_id")
            name = r.get("name")
            geom = (r.get("geometry") or {}).get("location") if isinstance(r.get("geometry"), dict) else None
            if not isinstance(place_id, str) or not place_id:
                continue
            if not isinstance(name, str) or not name:
                continue
            if not isinstance(geom, dict):
                continue
            lat = geom.get("lat")
            lng = geom.get("lng")
            if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
                continue
            lat_f, lng_f = float(lat), float(lng)
            try:
                validate_wgs84_coordinates(lat_f, lng_f)
            except InvalidCoordinatesError:
                continue
            address = r.get("formatted_address") if isinstance(r.get("formatted_address"), str) else None
            out.append(PlaceCandidate(place_id=place_id, name=name, address=address, lat=lat_f, lng=lng_f))
        return out

    def autocomplete(
        self,
        *,
        input_text: str,
        near_lat: float | None = None,
        near_lng: float | None = None,
    ) -> list[PlacePrediction]:
        url = f"{self.base_url}/maps/api/place/autocomplete/json"
        q = input_text.strip()
        if len(q) < 2:
            return []
        params: dict[str, Any] = {"input": q, "key": self.api_key}
        # Biasing improves relevance (Uber-style “near me” suggestions).
        if near_lat is not None and near_lng is not None:
            params["location"] = f"{near_lat},{near_lng}"
            params["radius"] = 50000

        resp = httpx.get(url, params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status not in {"OK", "ZERO_RESULTS"}:
            raise RuntimeError(f"Places Autocomplete status {status}")
        raw = data.get("predictions") or []
        out: list[PlacePrediction] = []
        for p in raw:
            if not isinstance(p, dict):
                continue
            pid = p.get("place_id")
            desc = p.get("description")
            if not isinstance(pid, str) or not pid:
                continue
            if not isinstance(desc, str) or not desc:
                continue
            sf = p.get("structured_formatting") if isinstance(p.get("structured_formatting"), dict) else {}
            main_text = sf.get("main_text") if isinstance(sf.get("main_text"), str) else desc
            secondary = sf.get("secondary_text") if isinstance(sf.get("secondary_text"), str) else None
            out.append(
                PlacePrediction(
                    place_id=pid,
                    description=desc,
                    main_text=main_text,
                    secondary_text=secondary,
                )
            )
        return out

    def place_details(self, *, place_id: str) -> PlaceCandidate | None:
        url = f"{self.base_url}/maps/api/place/details/json"
        params: dict[str, Any] = {
            "place_id": place_id,
            "fields": "place_id,name,geometry,formatted_address",
            "key": self.api_key,
        }
        resp = httpx.get(url, params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status == "ZERO_RESULTS":
            return None
        if status != "OK":
            raise RuntimeError(f"Places Details status {status}")
        r = data.get("result")
        if not isinstance(r, dict):
            return None
        pid = r.get("place_id")
        name = r.get("name")
        geom = (r.get("geometry") or {}).get("location") if isinstance(r.get("geometry"), dict) else None
        if not isinstance(pid, str) or not pid:
            return None
        if not isinstance(name, str) or not name:
            return None
        if not isinstance(geom, dict):
            return None
        lat = geom.get("lat")
        lng = geom.get("lng")
        if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
            return None
        lat_f, lng_f = float(lat), float(lng)
        try:
            validate_wgs84_coordinates(lat_f, lng_f)
        except InvalidCoordinatesError:
            return None
        address = r.get("formatted_address") if isinstance(r.get("formatted_address"), str) else None
        return PlaceCandidate(place_id=pid, name=name, address=address, lat=lat_f, lng=lng_f)


@dataclass(frozen=True)
class FakePlacesClient(AbstractPlacesClient):
    candidates: list[PlaceCandidate] = ()

    def text_search(
        self,
        *,
        query: str,
        near_lat: float | None = None,
        near_lng: float | None = None,
    ) -> list[PlaceCandidate]:
        return list(self.candidates)

    def autocomplete(
        self,
        *,
        input_text: str,
        near_lat: float | None = None,
        near_lng: float | None = None,
    ) -> list[PlacePrediction]:
        return []

    def place_details(self, *, place_id: str) -> PlaceCandidate | None:
        return None

