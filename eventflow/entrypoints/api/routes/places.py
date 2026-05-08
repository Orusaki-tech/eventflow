from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eventflow.adapters.places_client import FakePlacesClient, GooglePlacesClient
from eventflow.config import get_settings
from eventflow.entrypoints.api.schemas import (
    PlaceAutocompletePrediction,
    PlaceAutocompleteResponse,
    PlaceDetailsResponse,
)
from eventflow.entrypoints.dependencies import get_current_user_id

router = APIRouter(tags=["Places"])


def _places_client():
    settings = get_settings()
    if settings.google_maps_api_key:
        return GooglePlacesClient(api_key=settings.google_maps_api_key)
    return FakePlacesClient()


@router.get("/places/autocomplete", status_code=status.HTTP_200_OK, response_model=PlaceAutocompleteResponse)
async def places_autocomplete(
    input_q: str = Query(
        ...,
        alias="input",
        min_length=2,
        max_length=200,
        description="Partial address or place name (same idea as Uber's search box).",
    ),
    near_lat: float | None = Query(default=None, ge=-90, le=90),
    near_lng: float | None = Query(default=None, ge=-180, le=180),
    _user_id=Depends(get_current_user_id),
):
    places = _places_client()
    try:
        preds = places.autocomplete(input_text=input_q.strip(), near_lat=near_lat, near_lng=near_lng)
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
    return PlaceAutocompleteResponse(
        predictions=[
            PlaceAutocompletePrediction(
                place_id=p.place_id,
                description=p.description,
                main_text=p.main_text,
                secondary_text=p.secondary_text,
            )
            for p in preds
        ]
    )


@router.get("/places/details", status_code=status.HTTP_200_OK, response_model=PlaceDetailsResponse)
async def places_details(
    place_id: str = Query(..., min_length=3, max_length=512),
    _user_id=Depends(get_current_user_id),
):
    places = _places_client()
    try:
        det = places.place_details(place_id=place_id)
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
    if det is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Place not found")
    return PlaceDetailsResponse(
        place_id=det.place_id,
        name=det.name,
        formatted_address=det.address,
        lat=det.lat,
        lng=det.lng,
    )
