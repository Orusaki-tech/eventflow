/** Browser-safe API origin: direct URL, or same-origin proxy when NEXT_PUBLIC_EVENTFLOW_API_PROXY=1 (HTTPS sites → HTTP VM). */
function apiOrigin(): string {
  if (process.env.NEXT_PUBLIC_EVENTFLOW_API_PROXY === "1") {
    return "";
  }
  return process.env.NEXT_PUBLIC_EVENTFLOW_API_URL ?? "http://localhost:8000";
}

function apiPathPrefix(): string {
  if (process.env.NEXT_PUBLIC_EVENTFLOW_API_PROXY === "1") {
    return "/api/eventflow";
  }
  return "";
}

export async function efFetch<T>(
  path: string,
  token: string | null,
  init?: RequestInit & { json?: unknown }
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  let body = init?.body as BodyInit | undefined;
  if (init?.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.json);
  }
  const url = `${apiOrigin()}${apiPathPrefix()}${path}`;
  const res = await fetch(url, { ...init, headers, body });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = (await res.json()) as { detail?: unknown };
      if (typeof j.detail === "string") detail = j.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export type BusinessRow = {
  business_id: string;
  name: string;
  whatsapp_e164: string | null;
  verified: boolean;
};

export async function listBusinesses(token: string): Promise<BusinessRow[]> {
  return efFetch("/api/v1/businesses", token, { method: "GET" });
}

export async function patchBusiness(
  token: string,
  businessId: string,
  body: { name?: string; whatsapp_e164?: string | null }
): Promise<BusinessRow> {
  return efFetch(`/api/v1/businesses/${encodeURIComponent(businessId)}`, token, {
    method: "PATCH",
    json: body,
  });
}

export type CommunityMineRow = {
  community_event_id: string;
  source: string;
  title: string;
  start_time: string;
  venue: string;
  description?: string | null;
  poster_image_uri?: string | null;
  business_id?: string | null;
  whatsapp_e164?: string | null;
  hero_video_uri?: string | null;
};

export type CommunityMineDetail = CommunityMineRow & {
  normalized_share_aliases: string[];
};

export async function listMineCommunityEvents(token: string, limit = 50): Promise<CommunityMineRow[]> {
  const q = new URLSearchParams({ limit: String(limit) });
  return efFetch(`/api/v1/discovery/community-events/mine?${q}`, token, { method: "GET" });
}

export async function getMyCommunityEvent(token: string, communityEventId: string): Promise<CommunityMineDetail> {
  return efFetch(`/api/v1/discovery/community-events/${encodeURIComponent(communityEventId)}`, token, {
    method: "GET",
  });
}

export async function upsertCommunityListing(
  token: string,
  body: {
    source: string;
    title: string;
    start_time: string;
    venue: string;
    description?: string | null;
    poster_image_uri?: string | null;
  }
): Promise<{ community_event_id: string }> {
  return efFetch("/api/v1/discovery/community-events", token, {
    method: "POST",
    json: body,
  });
}

export async function attachListingBusiness(
  token: string,
  communityEventId: string,
  businessId: string
): Promise<void> {
  await efFetch(`/api/v1/listings/${encodeURIComponent(communityEventId)}/business`, token, {
    method: "PUT",
    json: { business_id: businessId },
  });
}

export async function putListingShareAlias(token: string, communityEventId: string, url: string): Promise<void> {
  await efFetch(`/api/v1/listings/${encodeURIComponent(communityEventId)}/share-alias`, token, {
    method: "PUT",
    json: { url },
  });
}

export async function registerEventVideo(
  token: string,
  communityEventId: string,
  storageUri: string
): Promise<{ video_id: string; moderation_status: string }> {
  return efFetch("/api/v1/event-videos", token, {
    method: "POST",
    json: { community_event_id: communityEventId, storage_uri: storageUri },
  });
}

export async function postBillingCheckout(token: string, provider: "stripe" | "mpesa_stub" = "stripe") {
  const q = encodeURIComponent(provider);
  return efFetch<{ checkout_url: string; provider: string }>(
    `/api/v1/billing/checkout-session?provider=${q}`,
    token,
    { method: "POST" }
  );
}

// --- Share / Import ---

export type ShareUrlResult = {
  draft_id: string;
  title: string;
  start_time: string | null;
  venue: string;
  confidence_score: number;
  price: string | null;
  poster_asset_id: string | null;
  source_url_raw: string;
};

export async function shareUrl(token: string, url: string): Promise<ShareUrlResult> {
  return efFetch("/api/v1/share/url", token, { method: "POST", json: { url } });
}

/** Construct a media URL that respects the API proxy prefix. */
export function mediaUrl(assetId: string, kind: "poster"): string {
  const origin = process.env.NEXT_PUBLIC_EVENTFLOW_API_PROXY === "1" ? "" : (process.env.NEXT_PUBLIC_EVENTFLOW_API_URL ?? "http://localhost:8000");
  const prefix = process.env.NEXT_PUBLIC_EVENTFLOW_API_PROXY === "1" ? "/api/eventflow" : "";
  return `${origin}${prefix}/api/v1/media/${kind}/${encodeURIComponent(assetId)}`;
}

export async function deleteListingShareAlias(token: string, communityEventId: string, url: string): Promise<void> {
  const q = encodeURIComponent(url);
  await efFetch(
    `/api/v1/listings/${encodeURIComponent(communityEventId)}/share-alias?url=${q}`,
    token,
    { method: "DELETE" }
  );
}

// --- Carousel ---

export type CarouselSlide = {
  kind: string;
  title: string | null;
  subtitle: string | null;
  uri: string | null;
  image_uri: string | null;
};

export type ListingCarouselResponse = {
  community_event_id: string;
  slides: CarouselSlide[];
};

export async function getListingCarousel(token: string, communityEventId: string): Promise<ListingCarouselResponse> {
  return efFetch(`/api/v1/listings/${encodeURIComponent(communityEventId)}/carousel`, token, { method: "GET" });
}

export async function deleteListingBusiness(token: string, communityEventId: string): Promise<void> {
  await efFetch(`/api/v1/listings/${encodeURIComponent(communityEventId)}/business`, token, { method: "DELETE" });
}

// --- Business Follows ---

export type BusinessFollowingRow = {
  business_id: string;
  name: string;
  whatsapp_e164: string | null;
  verified: boolean;
  created_at: string;
};

export async function postFollowBusiness(token: string, businessId: string): Promise<void> {
  await efFetch(`/api/v1/businesses/${encodeURIComponent(businessId)}/follow`, token, { method: "POST" });
}

export async function deleteFollowBusiness(token: string, businessId: string): Promise<void> {
  await efFetch(`/api/v1/businesses/${encodeURIComponent(businessId)}/follow`, token, { method: "DELETE" });
}

export async function listFollowedBusinesses(token: string): Promise<BusinessFollowingRow[]> {
  return efFetch("/api/v1/businesses/following", token, { method: "GET" });
}

// ─── TICKETING v3 ────────────────────────────────────────────────────────

export type DashboardResponse = {
  business_id: string;
  business_name: string;
  total_revenue_minor: number;
  total_fees_minor: number;
  net_available_minor: number;
  total_tickets_sold: number;
  tap_balance: number;
  tap_plan: string;
  affiliate_earnings_minor: number;
  listings: {
    community_event_id: string;
    title: string;
    start_time: string;
    tickets_sold: number;
    revenue_minor: number;
    fees_minor: number;
    checked_in: number;
  }[];
};

export async function getBusinessDashboard(token: string): Promise<DashboardResponse> {
  return efFetch("/api/v1/business/dashboard", token, { method: "GET" });
}

export type TicketTypeRow = {
  ticket_type_id: string;
  name: string;
  description?: string | null;
  price_minor_units: number;
  currency: string;
  quantity_available?: number | null;
  quantity_sold: number;
  is_active: boolean;
  sort_order: number;
};

export async function listTicketTypes(token: string, communityEventId: string): Promise<TicketTypeRow[]> {
  return efFetch(`/api/v1/listings/${encodeURIComponent(communityEventId)}/ticket-types`, token, { method: "GET" });
}

export async function bulkSetTicketTypes(
  token: string,
  communityEventId: string,
  types: { name: string; price_minor_units: number; quantity_available?: number | null; description?: string | null; ticket_type_id?: string | null }[]
): Promise<void> {
  await efFetch(`/api/v1/listings/${encodeURIComponent(communityEventId)}/ticket-types`, token, {
    method: "PUT",
    json: { types },
  });
}

export async function getEventSales(token: string, communityEventId: string): Promise<{ name: string; price_minor_units: number; sold: number; active: number; checked_in: number }[]> {
  return efFetch(`/api/v1/business/events/${encodeURIComponent(communityEventId)}/sales`, token, { method: "GET" });
}

export type TapPackResponse = {
  business_id: string;
  tap_balance: number;
  tap_plan: string;
  pricing: Record<string, { taps?: number | null; price_minor: number }>;
};

export async function getTapStatus(token: string): Promise<TapPackResponse> {
  return efFetch("/api/v1/business/taps", token, { method: "GET" });
}

export async function buyTapPack(token: string, plan: string): Promise<TapPackResponse> {
  return efFetch("/api/v1/business/taps/buy", token, { method: "POST", json: { plan } });
}

export type PayoutSettings = {
  payout_method: string;
  mpesa_till_number?: string | null;
  mpesa_paybill_number?: string | null;
  bank_name?: string | null;
  payout_frequency: string;
  minimum_payout_minor: number;
};

export async function getPayoutSettings(token: string): Promise<PayoutSettings> {
  return efFetch("/api/v1/business/payout-settings", token, { method: "GET" });
}

export async function updatePayoutSettings(token: string, settings: PayoutSettings): Promise<void> {
  await efFetch("/api/v1/business/payout-settings", token, { method: "PUT", json: settings });
}

export type PayoutRow = {
  payout_id: string;
  period_start: string;
  period_end: string;
  gross_minor_units: number;
  fees_minor_units: number;
  net_minor_units: number;
  status: string;
  payment_reference?: string | null;
  paid_at?: string | null;
  created_at: string;
};

export async function listPayouts(token: string): Promise<PayoutRow[]> {
  return efFetch("/api/v1/business/payouts", token, { method: "GET" });
}

export async function requestPayout(token: string): Promise<{ payout_id: string; amount_minor: number; status: string }> {
  return efFetch("/api/v1/business/payouts/request", token, { method: "POST" });
}

export type FeedVideoRow = {
  video_id: string;
  title: string;
  video_uri?: string;
  thumbnail_uri?: string;
  video_type: string;
  moderation_status: string;
  views: number;
  whatsapp_taps: number;
  created_at?: string;
};

export async function listMyFeedVideos(token: string): Promise<FeedVideoRow[]> {
  return efFetch("/api/v1/feed/videos", token, { method: "GET" });
}

export async function publishFeedVideo(token: string, body: { title: string; video_uri: string; thumbnail_uri?: string; community_event_id?: string; video_type?: string; is_paid?: boolean }): Promise<{ video_id: string; moderation_status: string }> {
  return efFetch("/api/v1/feed/videos", token, { method: "POST", json: body });
}

export type ProductRow = {
  product_id: string;
  title: string;
  description?: string | null;
  price_minor_units: number;
  image_uri?: string | null;
  is_active: boolean;
};

export async function listMyProducts(token: string): Promise<ProductRow[]> {
  return efFetch("/api/v1/business/products", token, { method: "GET" });
}

export async function createProduct(token: string, body: { title: string; description?: string; price_minor_units: number; image_uri?: string }): Promise<ProductRow> {
  return efFetch("/api/v1/business/products", token, { method: "POST", json: body });
}

export async function listAffiliateRequests(token: string): Promise<{ link_id: string; title: string; price_minor_units: number; seller_name: string; status: string }[]> {
  return efFetch("/api/v1/business/affiliate-requests", token, { method: "GET" });
}

export async function approveAffiliateRequest(token: string, linkId: string, commissions: { commission_seller_percent: number; commission_owner_percent: number; commission_platform_percent: number }): Promise<void> {
  await efFetch(`/api/v1/business/affiliate-requests/${encodeURIComponent(linkId)}/approve`, token, { method: "POST", json: commissions });
}
