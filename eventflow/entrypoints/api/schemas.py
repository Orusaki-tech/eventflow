from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from eventflow.domain.geo_coordinates import validate_wgs84_coordinates


class CaptureRequest(BaseModel):
    image_base64: str


class EventDraftResponse(BaseModel):
    draft_id: UUID
    title: str
    """None when the importer could not infer a start instant (user must edit)."""
    start_time: datetime | None = None
    venue: str
    confidence_score: float
    price: str | None = None
    poster_asset_id: UUID | None = None


class EventDraftDetailResponse(BaseModel):
    draft_id: UUID
    title: str
    start_time: datetime | None = None
    venue: str
    confidence_score: float
    confirmed_at: datetime | None = None
    price: str | None = None
    poster_asset_id: UUID | None = None


class DraftUpdateRequest(BaseModel):
    title: str | None = None
    start_time: datetime | None = None
    venue: str | None = None
    price: str | None = None


class ShareUrlRequest(BaseModel):
    url: str


class ShareUrlCarouselResponse(BaseModel):
    drafts: list[EventDraftResponse]
    """1-based carousel indices aligned with drafts (same length)."""

    slides_used: list[int] = Field(default_factory=list)


class ShareInstagramCarouselRequest(BaseModel):
    url: str
    carousel_slide_indices: list[int] | None = None

    @field_validator("carousel_slide_indices")
    @classmethod
    def _limit_slide_indices(cls, v: list[int] | None) -> list[int] | None:
        if not v:
            return None
        if len(v) > 2:
            raise ValueError("At most 2 carousel_slide_indices are allowed")
        for i in v:
            if i < 1:
                raise ValueError("carousel_slide_indices must be >= 1")
        return v


class InstagramCarouselPreviewSlide(BaseModel):
    slide_index: int
    image_token: str


class InstagramCarouselPreviewResponse(BaseModel):
    slides: list[InstagramCarouselPreviewSlide]


class ShareTextRequest(BaseModel):
    text: str


class SharePosterResponse(BaseModel):
    draft_id: UUID
    title: str
    start_time: datetime | None = None
    venue: str
    confidence_score: float
    poster_asset_id: UUID
    source_url_raw: str | None = None
    price: str | None = None


class ShareMediaResponse(EventDraftResponse):
    media_kind: Literal["image", "video"]
    media_id: UUID | None = None


class EventPriceUpdateRequest(BaseModel):
    """Ticket/admission line shown to users; null clears stored price."""

    price: str | None = None


class EventBasicsUpdateRequest(BaseModel):
    """Owner patch for title, start time, and/or venue on a confirmed event."""

    title: str | None = None
    start_time: datetime | None = None
    venue: str | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> EventBasicsUpdateRequest:
        if self.title is None and self.start_time is None and self.venue is None:
            raise ValueError("Provide at least one of title, start_time, venue")
        return self


class ResolveImageRequest(BaseModel):
    url: str


class ResolveImageResponse(BaseModel):
    image_token: str


class ParseDraftFromImageRequest(BaseModel):
    draft_id: UUID
    image_token: str


class EventConfirmedResponse(BaseModel):
    event_id: UUID
    message: str = "Event scheduled successfully"


class UserLocationUpsertRequest(BaseModel):
    address: str
    lat: float | None = None
    lng: float | None = None


class UserLocationResponse(BaseModel):
    label: str
    address: str
    lat: float | None = None
    lng: float | None = None


class ReminderAlertRequest(BaseModel):
    minutes_before: int


class PushTokenUpsertRequest(BaseModel):
    expo_push_token: str
    platform: str | None = None  # "ios" | "android"
    device_id: str | None = None


class PushTokenResponse(BaseModel):
    token_id: UUID
    expo_push_token: str
    platform: str | None = None
    device_id: str | None = None


class UserPreferencesResponse(BaseModel):
    monthly_budget_minor_units: int | None = None


class UserPreferencesPatchRequest(BaseModel):
    """Whole-number minor units (e.g. cents). Null clears the monthly budget cap."""

    monthly_budget_minor_units: int | None = None


class BudgetSummaryResponse(BaseModel):
    year: int
    month: int
    budget_minor_units: int | None = None
    spent_minor_units: int
    priced_events_count: int
    unpriced_events_count: int
    events_total_count: int
    band: Literal["unset", "under", "tight", "over"]


class CommunityEventUpsertRequest(BaseModel):
    source: str
    title: str
    start_time: datetime
    venue: str
    description: str | None = None
    poster_image_uri: str | None = Field(default=None, max_length=4096)


class CommunityEventResponse(BaseModel):
    community_event_id: UUID
    source: str
    title: str
    start_time: datetime
    venue: str
    description: str | None = None
    poster_image_uri: str | None = None


class CommunityEventMineListRowResponse(BaseModel):
    """Owned community listing row (portal / mobile discovery-compatible shape)."""

    community_event_id: UUID
    source: str
    title: str
    start_time: datetime
    venue: str
    description: str | None = None
    poster_image_uri: str | None = None
    business_id: UUID | None = None
    whatsapp_e164: str | None = None
    hero_video_uri: str | None = None


class CommunityEventMineDetailResponse(CommunityEventMineListRowResponse):
    normalized_share_aliases: list[str] = Field(default_factory=list)


class VenueResponse(BaseModel):
    id: UUID
    name: str
    address: str | None = None
    lat: float
    lng: float
    place_id: str | None = None


class VenueCreateRequest(BaseModel):
    name: str
    address: str | None = None
    lat: float
    lng: float
    place_id: str | None = None

    @model_validator(mode="after")
    def _validate_coordinates(self) -> VenueCreateRequest:
        validate_wgs84_coordinates(self.lat, self.lng)
        return self


class VenueUpdateRequest(BaseModel):
    name: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None


class ResolveVenueRequest(BaseModel):
    query: str
    near_lat: float | None = None
    near_lng: float | None = None

    @model_validator(mode="after")
    def _validate_near_optional(self) -> ResolveVenueRequest:
        if (self.near_lat is None) ^ (self.near_lng is None):
            raise ValueError("near_lat and near_lng must both be set or both omitted")
        if self.near_lat is not None and self.near_lng is not None:
            validate_wgs84_coordinates(self.near_lat, self.near_lng)
        return self


class ResolveVenueResponse(BaseModel):
    venue: VenueResponse


class EtaRequest(BaseModel):
    lat: float
    lng: float

    @model_validator(mode="after")
    def _validate_origin(self) -> EtaRequest:
        validate_wgs84_coordinates(self.lat, self.lng)
        return self


class EtaResponse(BaseModel):
    distance_meters: int
    duration_seconds: int
    duration_in_traffic_seconds: int | None = None


class EventVisibilityUpdateRequest(BaseModel):
    visibility: str  # "private" | "public"


class EventDescriptionUpdateRequest(BaseModel):
    description: str | None = None
    audience: str  # "public" | "close_friends"


class GroupCreateRequest(BaseModel):
    name: str


class GroupResponse(BaseModel):
    group_id: UUID
    name: str
    owner_user_id: UUID
    invite_token: str | None = None
    group_type: str | None = None


class GroupMemberAddRequest(BaseModel):
    user_id: UUID
    role: str = "member"


class GroupEventShareRequest(BaseModel):
    event_id: UUID


class PlaceAutocompletePrediction(BaseModel):
    place_id: str
    description: str
    main_text: str
    secondary_text: str | None = None


class PlaceAutocompleteResponse(BaseModel):
    predictions: list[PlaceAutocompletePrediction]


class PlaceDetailsResponse(BaseModel):
    place_id: str
    name: str
    formatted_address: str | None = None
    lat: float
    lng: float


class SnoozeAlertRequest(BaseModel):
    minutes: int = Field(default=10, ge=1, le=180)


class DeviceCalendarPutRequest(BaseModel):
    external_event_id: str = Field(min_length=1, max_length=512)
    calendar_id: str | None = Field(default=None, max_length=512)


class SharedLinkListingStatusResponse(BaseModel):
    normalized_url: str
    status: str | None = None


class BusinessCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=512)
    whatsapp_e164: str | None = Field(default=None, max_length=32)


class BusinessResponse(BaseModel):
    business_id: UUID
    name: str
    whatsapp_e164: str | None = None
    verified: bool = False


class BusinessPatchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=512)
    whatsapp_e164: str | None = Field(default=None, max_length=32)


class ListingBusinessAttachRequest(BaseModel):
    business_id: UUID


class ListingShareAliasPutRequest(BaseModel):
    url: str = Field(min_length=8, max_length=4096)


class AdminBusinessVerifiedPatchRequest(BaseModel):
    verified: bool


class EventVideoModerationPatchRequest(BaseModel):
    moderation_status: Literal["pending", "approved", "rejected"]


class ListingAnalyticsRequest(BaseModel):
    metric_type: Literal["impression", "save", "whatsapp_tap"]
    community_event_id: UUID | None = None
    business_id: UUID | None = None
    meta: dict | None = None


class CarouselSlide(BaseModel):
    kind: Literal["poster", "video"]
    title: str | None = None
    subtitle: str | None = None
    uri: str | None = None
    image_uri: str | None = None


class ListingCarouselResponse(BaseModel):
    community_event_id: UUID
    slides: list[CarouselSlide]


class BillingCheckoutStubResponse(BaseModel):
    checkout_url: str
    provider: Literal["stripe", "mpesa_stub"] = "stripe"


class GroupJoinByTokenRequest(BaseModel):
    invite_token: str = Field(min_length=4, max_length=128)


class GroupRsvpRequest(BaseModel):
    event_id: UUID
    status: Literal["going", "maybe", "declined"]


class GroupPinRequest(BaseModel):
    event_id: UUID | None = None

