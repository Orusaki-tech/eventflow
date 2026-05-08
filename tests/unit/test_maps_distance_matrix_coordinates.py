from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from eventflow.adapters.maps_client import GoogleMapsClient


def test_distance_matrix_strings_are_latitude_comma_longitude() -> None:
    """Google Distance Matrix expects origins/destinations as 'lat,lng' pairs (same order as WGS84 labels)."""
    matrix_payload = {
        "rows": [
            {
                "elements": [
                    {
                        "status": "OK",
                        "distance": {"value": 5000},
                        "duration": {"value": 900},
                        "duration_in_traffic": {"value": 920},
                    }
                ]
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = matrix_payload
    mock_resp.raise_for_status = MagicMock()

    with patch("eventflow.adapters.maps_client.httpx.get", return_value=mock_resp) as get:
        maps = GoogleMapsClient(api_key="k")
        dist, dur, dur_traffic = maps.estimate_distance_and_duration_seconds(
            origin_lat=1.25,
            origin_lng=-2.5,
            destination_lat=40.75,
            destination_lng=-73.99,
            depart_at=datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc),
        )

    assert dist == 5000
    assert dur == 900
    assert dur_traffic == 920

    params = get.call_args.kwargs["params"]
    assert params["origins"] == "1.25,-2.5"
    assert params["destinations"] == "40.75,-73.99"
