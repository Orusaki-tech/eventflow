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
