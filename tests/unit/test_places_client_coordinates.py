from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from eventflow.adapters.places_client import GooglePlacesClient


def test_place_details_reads_geometry_latitude_then_longitude() -> None:
    """Google Places Details uses geometry.location.lat / .lng — ETA expects the same WGS84 order."""
    payload = {
        "status": "OK",
        "result": {
            "place_id": "ChIJMock",
            "name": "Empire State Building",
            "geometry": {"location": {"lat": 40.748817, "lng": -73.985428}},
            "formatted_address": "20 W 34th St, New York, NY",
        },
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status = MagicMock()
    with patch("eventflow.adapters.places_client.httpx.get", return_value=mock_resp) as get:
        client = GooglePlacesClient(api_key="test-key")
        out = client.place_details(place_id="ChIJMock")

    assert out is not None
    assert out.lat == pytest.approx(40.748817)
    assert out.lng == pytest.approx(-73.985428)
    params = get.call_args.kwargs["params"]
    assert params["fields"] == "place_id,name,geometry,formatted_address"


def test_place_details_rejects_invalid_coordinates_returns_none() -> None:
    payload = {
        "status": "OK",
        "result": {
            "place_id": "x",
            "name": "Broken",
            "geometry": {"location": {"lat": 0.0, "lng": 0.0}},
            "formatted_address": None,
        },
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status = MagicMock()
    with patch("eventflow.adapters.places_client.httpx.get", return_value=mock_resp):
        client = GooglePlacesClient(api_key="test-key")
        assert client.place_details(place_id="x") is None


def test_text_search_skips_rows_with_invalid_coordinates() -> None:
    payload = {
        "status": "OK",
        "results": [
            {
                "place_id": "bad",
                "name": "Null island",
                "geometry": {"location": {"lat": 0.0, "lng": 0.0}},
                "formatted_address": "Nowhere",
            },
            {
                "place_id": "good",
                "name": "Ok venue",
                "geometry": {"location": {"lat": 51.5, "lng": -0.12}},
                "formatted_address": "London",
            },
        ],
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status = MagicMock()
    with patch("eventflow.adapters.places_client.httpx.get", return_value=mock_resp):
        client = GooglePlacesClient(api_key="test-key")
        rows = client.text_search(query="test")

    assert len(rows) == 1
    assert rows[0].place_id == "good"
    assert rows[0].lat == pytest.approx(51.5)
    assert rows[0].lng == pytest.approx(-0.12)
