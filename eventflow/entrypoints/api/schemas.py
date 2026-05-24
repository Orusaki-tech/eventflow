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
    """Membership role for the requesting user when listing ``GET /groups``."""
    my_role: Literal["owner", "member"] | None = None


class FollowingRow(BaseModel):
    following_user_id: UUID
    created_at: datetime


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
    description: str | None = None
    logo_url: str | None = None
    website: str | None = None
    contact_email: str | None = None


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


class BusinessFollowingRow(BaseModel):
    business_id: UUID
    name: str
    whatsapp_e164: str | None = None
    verified: bool = False
    created_at: datetime


class BillingCheckoutStubResponse(BaseModel):
    checkout_url: str
    provider: Literal["stripe", "mpesa_stub"] = "stripe"


class RegisterEventVideoRequest(BaseModel):
    community_event_id: UUID
    storage_uri: str = Field(..., min_length=8, max_length=4096)


class GroupJoinByTokenRequest(BaseModel):
    invite_token: str = Field(min_length=4, max_length=128)


class GroupRsvpRequest(BaseModel):
    event_id: UUID
    status: Literal["going", "maybe", "declined"]


class GroupPinRequest(BaseModel):
    event_id: UUID | None = None


# --- Admin console (JWT + ADMIN_USER_IDS) ---


class AdminConsoleMeResponse(BaseModel):
    ok: bool = True
    user_id: UUID


class AdminConsoleSummaryResponse(BaseModel):
    businesses: int
    community_events: int
    poster_assets: int
    event_drafts: int
    distinct_active_user_ids: int = Field(
        ...,
        description=(
            "Count of distinct user ids seen across community_events, event_drafts, and business owners — "
            "not a full user directory."
        ),
    )


class AdminConsoleSummaryV3Response(AdminConsoleSummaryResponse):
    total_orders: int = 0
    total_revenue_minor: int = 0
    pending_claims: int = 0
    pending_payouts: int = 0
    pending_videos: int = 0


class AdminConsoleBusinessRow(BaseModel):
    business_id: UUID
    name: str
    whatsapp_e164: str | None
    owner_user_id: UUID | None = None
    verified: bool
    created_at: datetime


class AdminConsoleBusinessListResponse(BaseModel):
    items: list[AdminConsoleBusinessRow]
    total: int
    limit: int
    offset: int


class AdminConsoleCommunityEventRow(BaseModel):
    community_event_id: UUID
    user_id: UUID
    title: str
    start_time: datetime
    venue: str
    source: str
    poster_image_uri: str | None = None
    attached_business_id: UUID | None = None


class AdminConsoleCommunityEventListResponse(BaseModel):
    items: list[AdminConsoleCommunityEventRow]
    total: int
    limit: int
    offset: int


class AdminConsolePosterAssetRow(BaseModel):
    poster_asset_id: UUID
    content_sha256: str | None = None
    dhash64: str
    created_at: datetime
    content_type: str
    event_source_links: int = Field(..., description="Rows in event_sources referencing this poster_asset_id.")
    draft_links: int = Field(..., description="event_sources rows with non-null draft_id.")
    scheduled_event_links: int = Field(..., description="event_sources rows with non-null event_id.")


class AdminConsolePosterAssetListResponse(BaseModel):
    items: list[AdminConsolePosterAssetRow]
    total: int
    limit: int
    offset: int


class AdminConsoleSharedLinkListingRow(BaseModel):
    normalized_url: str
    source_url_raw: str | None = None
    status: str
    cached_payload: dict | None = None
    created_at: datetime
    updated_at: datetime


class AdminConsoleSharedLinkListingListResponse(BaseModel):
    items: list[AdminConsoleSharedLinkListingRow]
    total: int
    limit: int
    offset: int


class AdminSharedLinkListingUpdateRequest(BaseModel):
    url: str = Field(..., min_length=4, max_length=4096)
    title: str | None = None
    venue: str | None = None
    start_time: str | None = Field(None, description="ISO 8601, empty string to clear")
    price: str | None = None
    status: str | None = Field(None, pattern="^(pending|approved|rejected)$")


class BusinessProfileListingRow(BaseModel):
    community_event_id: UUID
    title: str
    start_time: datetime
    venue: str
    poster_image_uri: str | None = None
    hero_video_uri: str | None = None
    whatsapp_e164: str | None = None


class BusinessProfileResponse(BaseModel):
    business_id: UUID
    name: str
    description: str | None = None
    logo_url: str | None = None
    website: str | None = None
    contact_email: str | None = None
    whatsapp_e164: str | None = None
    verified: bool = False
    follower_count: int = 0
    listing_count: int = 0
    listings: list[BusinessProfileListingRow] = []


class BusinessProfileUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    logo_url: str | None = None
    website: str | None = None
    contact_email: str | None = None
    whatsapp_e164: str | None = None


# ─── Ticketing v3 ────────────────────────────────────────────────────────


class TicketTypeBulkRow(BaseModel):
    ticket_type_id: UUID | None = None
    name: str
    description: str | None = None
    price_minor_units: int = Field(ge=0)
    quantity_available: int | None = Field(default=None, ge=1)
    sale_start: datetime | None = None
    sale_end: datetime | None = None
    refundable_until: datetime | None = None


class TicketTypeBulkRequest(BaseModel):
    types: list[TicketTypeBulkRow]


class TicketTypeResponse(BaseModel):
    ticket_type_id: UUID
    name: str
    description: str | None = None
    price_minor_units: int
    currency: str = "KES"
    quantity_available: int | None = None
    quantity_sold: int = 0
    sale_start: datetime | None = None
    sale_end: datetime | None = None
    refundable_until: datetime | None = None
    is_active: bool = True
    sort_order: int = 0


class PurchaseItem(BaseModel):
    ticket_type_id: UUID
    quantity: int = Field(default=1, ge=1)


class PurchaseRequest(BaseModel):
    community_event_id: UUID
    items: list[PurchaseItem]
    payment_provider: str = Field(default="stripe", pattern="^(stripe|mpesa)$")


class PurchaseResponse(BaseModel):
    order_id: UUID
    receipt_number: str
    total_minor_units: int
    platform_fee_minor_units: int
    payment_provider: str
    ticket_codes: list[str]
    points_earned: int = 0


class OrderTicketRow(BaseModel):
    ticket_id: UUID
    short_code: str
    ticket_type_name: str
    status: str
    checked_in_at: datetime | None = None


class OrderResponse(BaseModel):
    order_id: UUID
    community_event_id: UUID
    event_title: str
    status: str
    type: str = "ticket"
    total_minor_units: int
    platform_fee_minor_units: int = 0
    business_net_minor_units: int = 0
    currency: str = "KES"
    payment_provider: str | None = None
    receipt_number: str | None = None
    points_earned: int = 0
    paid_at: datetime | None = None
    created_at: datetime
    tickets: list[OrderTicketRow] = []


class DashboardListingRow(BaseModel):
    community_event_id: UUID
    title: str
    start_time: datetime
    tickets_sold: int = 0
    revenue_minor: int = 0
    fees_minor: int = 0
    checked_in: int = 0


class DashboardResponse(BaseModel):
    business_id: UUID
    business_name: str
    total_revenue_minor: int
    total_fees_minor: int
    net_available_minor: int
    total_tickets_sold: int
    tap_balance: int = 0
    tap_plan: str = "none"
    affiliate_earnings_minor: int = 0
    listings: list[DashboardListingRow] = []


class TapPackBuyRequest(BaseModel):
    plan: str = Field(..., pattern="^(starter|growth|pro|unlimited)$")


class TapPackResponse(BaseModel):
    business_id: UUID
    tap_balance: int
    tap_plan: str
    pricing: dict


class FeedVideoPublishRequest(BaseModel):
    title: str
    video_uri: str
    thumbnail_uri: str | None = None
    community_event_id: UUID | None = None
    video_type: str = Field(default="promo", pattern="^(promo|countdown|highlights)$")
    countdown_target: datetime | None = None
    is_paid: bool = False
    sort_order: int = Field(default=0, ge=0)


class VideoModerationRequest(BaseModel):
    moderation_status: str = Field(..., pattern="^(approved|rejected)$")


class FeedVideoResponse(BaseModel):
    video_id: UUID
    title: str
    video_uri: str | None = None
    thumbnail_uri: str | None = None
    video_type: str = "promo"
    moderation_status: str = "pending"
    views: int = 0
    whatsapp_taps: int = 0
    created_at: datetime | None = None
    business_name: str | None = None
    event_title: str | None = None
    community_event_id: UUID | None = None


class FeedWatchResponse(BaseModel):
    points_earned: int = 0


class WatchQuotaResponse(BaseModel):
    is_premium: bool = False
    videos_watched_today: int = 0
    videos_remaining: int = 0
    daily_limit: int = 10
    premium_price_minor: int = 30000


class ProductCreateRequest(BaseModel):
    title: str
    description: str | None = None
    price_minor_units: int = Field(ge=0)
    image_uri: str | None = None


class ProductResponse(BaseModel):
    product_id: UUID
    title: str
    description: str | None = None
    price_minor_units: int
    image_uri: str | None = None
    is_active: bool = True


class ProductEventLinkRequest(BaseModel):
    product_id: UUID
    commission_seller_percent: int | None = Field(default=80, ge=0, le=100)
    commission_owner_percent: int | None = Field(default=10, ge=0, le=100)
    commission_platform_percent: int | None = Field(default=10, ge=0, le=100)


class ProductEventLinkApproveRequest(BaseModel):
    commission_seller_percent: int = Field(default=80, ge=0, le=100)
    commission_owner_percent: int = Field(default=10, ge=0, le=100)
    commission_platform_percent: int = Field(default=10, ge=0, le=100)


class ProductEventLinkResponse(BaseModel):
    link_id: UUID | None = None
    product_id: UUID | None = None
    title: str | None = None
    description: str | None = None
    price_minor_units: int | None = None
    image_uri: str | None = None
    seller_name: str | None = None
    status: str = "pending"
    commission_seller_percent: int | None = None
    commission_owner_percent: int | None = None
    commission_platform_percent: int | None = None


class PayoutRequest(BaseModel):
    payout_method: str = Field(default="mpesa_till", pattern="^(mpesa_till|mpesa_paybill|bank|stripe)$")
    mpesa_till_number: str | None = None
    mpesa_paybill_number: str | None = None
    mpesa_account_ref: str | None = None
    bank_name: str | None = None
    bank_account_name: str | None = None
    bank_account_number: str | None = None
    bank_branch_code: str | None = None
    payout_frequency: str = Field(default="manual", pattern="^(manual|weekly|monthly)$")
    minimum_payout_minor: int = Field(default=50000, ge=0)


class PayoutResponse(BaseModel):
    payout_id: UUID
    period_start: datetime
    period_end: datetime
    gross_minor_units: int
    fees_minor_units: int = 0
    net_minor_units: int
    status: str = "pending"
    payment_reference: str | None = None
    paid_at: datetime | None = None
    created_at: datetime


class ClaimCreateRequest(BaseModel):
    order_id: UUID
    claim_type: str = Field(..., pattern="^(ticket_not_received|event_cancelled|refund|other)$")
    reason: str | None = None


class AdminClaimResolveRequest(BaseModel):
    claim_type: str = Field(..., pattern="^(resolved_approved|resolved_denied)$")
    admin_notes: str | None = None


class ClaimResponse(BaseModel):
    claim_id: UUID
    order_id: UUID | None = None
    claim_type: str | None = None
    reason: str | None = None
    status: str = "open"
    admin_notes: str | None = None
    created_at: datetime | None = None
    resolved_at: datetime | None = None


class PointsResponse(BaseModel):
    balance: int = 0
    lifetime_earned: int = 0
    lifetime_redeemed: int = 0
    last_activity: datetime | None = None
    discount_code: str | None = None
    discount_minor: int | None = None


class RedeemPointsRequest(BaseModel):
    points: int = Field(default=10, ge=10, multiple_of=10)


class SubscriptionResponse(BaseModel):
    subscription_id: UUID
    plan: str = "premium"
    status: str = "active"
    current_period_end: datetime | None = None
    created_at: datetime | None = None


class ReferralLinkResponse(BaseModel):
    link_id: UUID
    code: str
    community_event_id: UUID
    event_title: str | None = None
    commission_percent: int = 30
    total_clicks: int = 0
    total_taps: int = 0
    total_earned_minor: int = 0


class PlatformSettingsResponse(BaseModel):
    key: str
    value: dict
    updated_at: datetime


class PlatformSettingsUpdateRequest(BaseModel):
    key: str
    value: dict


# ─── Admin / internal response models ─────────────────────────────────────


class TicketResendResponse(BaseModel):
    tickets: list[str]


class TicketLookupResponse(BaseModel):
    ticket_id: UUID
    short_code: str
    ticket_type: str
    event_title: str
    start_time: datetime
    venue: str
    status: str
    checked_in_at: datetime | None = None


class CheckInResponse(BaseModel):
    ok: bool
    checked_in_at: datetime


class SalesDetailRow(BaseModel):
    name: str
    price_minor_units: int
    sold: int
    active: int
    checked_in: int


class PayoutSettingsResponse(BaseModel):
    payout_method: str = "mpesa_till"
    mpesa_till_number: str | None = None
    mpesa_paybill_number: str | None = None
    mpesa_account_ref: str | None = None
    bank_name: str | None = None
    bank_account_name: str | None = None
    bank_account_number: str | None = None
    bank_branch_code: str | None = None
    payout_frequency: str = "manual"
    minimum_payout_minor: int = 50000


class PayoutRequestResponse(BaseModel):
    payout_id: UUID
    amount_minor: int
    status: str


class AdminOrderRow(BaseModel):
    order_id: UUID
    user_id: UUID
    event_title: str
    status: str
    total_minor: int
    fee_minor: int
    payment_provider: str | None = None
    created_at: datetime


class AdminClaimRow(BaseModel):
    claim_id: UUID
    order_id: UUID | None = None
    user_id: UUID
    claim_type: str
    reason: str | None = None
    status: str
    admin_notes: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class AdminResolveResponse(BaseModel):
    ok: bool
    status: str


class AdminPayoutRow(BaseModel):
    payout_id: UUID
    business_name: str
    gross_minor: int
    fees_minor: int
    net_minor: int
    status: str
    reference: str | None = None
    created_at: datetime


class AdminProcessPayoutResponse(BaseModel):
    ok: bool


class AdminVideoRow(BaseModel):
    video_id: UUID
    title: str
    business_name: str | None = None
    moderation_status: str
    views: int
    created_at: datetime


class AdminModerateResponse(BaseModel):
    ok: bool
    status: str

