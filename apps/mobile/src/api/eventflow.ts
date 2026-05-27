import type { NormalizedSharePayload } from "../lib/normalizeSharePayload";

export type EventDraft = {
  draft_id: string;
  title: string;
  /** Omitted or null when the server could not infer a start instant — user must set before confirm. */
  start_time?: string | null;
  venue: string;
  confidence_score: number;
  price?: string | null;
  /** Server-persisted preview poster when link import extracted an image */
  poster_asset_id?: string | null;
};

export type SharePosterResponse = EventDraft & {
  poster_asset_id: string;
  source_url_raw?: string | null;
};

export type ShareMediaResponse = EventDraft & {
  media_kind: "image" | "video";
  /** For future: durable media id */
  media_id?: string;
};

export type EventDraftDetail = EventDraft & {
  confirmed_at: string | null;
};

export type DraftListRow = EventDraft & {
  confirmed_at?: string | null;
};

export type ResolveImageResponse = {
  image_token: string;
};

export type ShareCarouselResponse = {
  drafts: EventDraft[];
  slides_used: number[];
};

export type InstagramCarouselPreviewSlide = {
  slide_index: number;
  image_token: string;
};

export type InstagramCarouselPreviewResponse = {
  slides: InstagramCarouselPreviewSlide[];
};

export type EventConfirmed = {
  event_id: string;
  message?: string;
};

/** Matches `views.get_upcoming_events` row keys after JSON serialization. */
export type UpcomingEventRow = {
  id: string;
  user_id?: string;
  title: string;
  start_time: string;
  venue: string;
  price?: string | null;
  alert_time?: string | null;
  description?: string | null;
};

export type TodayEventRow = {
  id: string;
  user_id: string;
  title: string;
  start_time: string;
  venue: string;
  price?: string | null;
  venue_id: string | null;
  visibility: "private" | "public";
  description?: string | null;
};

export type EtaResponse = {
  distance_meters: number;
  duration_seconds: number;
  duration_in_traffic_seconds?: number | null;
};

export type Venue = {
  id: string;
  name: string;
  address?: string | null;
  lat: number;
  lng: number;
  place_id?: string | null;
};

/** `GET /feed/home` row (`community_events` with `id` as UUID string). */
export type FeedHomeRow = {
  id: string;
  title: string;
  start_time: string;
  venue: string;
  user_id: string;
  sponsored_rank?: number | null;
  poster_image_uri?: string | null;
  business_id?: string | null;
  whatsapp_e164?: string | null;
  hero_video_uri?: string | null;
};

/** `GET /discovery/feed` row. */
export type DiscoveryCommunityRow = {
  community_event_id: string;
  source?: string | null;
  title: string;
  start_time: string;
  venue: string;
  description?: string | null;
  poster_image_uri?: string | null;
  business_id?: string | null;
  whatsapp_e164?: string | null;
  hero_video_uri?: string | null;
};

export type CarouselSlide = {
  kind: "poster" | "video";
  title?: string | null;
  subtitle?: string | null;
  uri?: string | null;
  image_uri?: string | null;
};

export type ListingCarouselResponse = {
  community_event_id: string;
  slides: CarouselSlide[];
};

export type ListingAnalyticsMetric = "impression" | "save" | "whatsapp_tap";

export type BusinessResponse = {
  business_id: string;
  name: string;
  whatsapp_e164: string | null;
  verified: boolean;
};

export type BillingCheckoutStubResponse = {
  checkout_url: string;
  provider: "stripe" | "mpesa_stub";
};

/** GET /groups row */
export type GroupRow = {
  group_id: string;
  name: string;
  owner_user_id: string;
  invite_token?: string | null;
  group_type?: string | null;
  my_role?: "owner" | "member" | null;
};

/** GET /follows row */
export type FollowingRow = {
  following_user_id: string;
  created_at: string;
};

export type UserProfileRow = {
  user_id: string;
  display_name: string;
  avatar_url: string | null;
  is_public: boolean;
};

export type UserProfileSearchResponse = {
  results: UserProfileRow[];
  total: number;
};

async function readProblemDetail(res: Response): Promise<string> {
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("json")) {
    try {
      const j: unknown = await res.json();
      if (j && typeof j === "object") {
        const o = j as Record<string, unknown>;
        if (typeof o.detail === "string") return o.detail;
        if (typeof o.title === "string") return o.title;
      }
    } catch {
      /* ignore */
    }
  }
  return res.statusText || `HTTP ${res.status}`;
}

async function request<T>(
  baseUrl: string,
  path: string,
  token: string | null,
  init: RequestInit & { json?: unknown; timeoutMs?: number } = {}
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined = init.body as BodyInit | undefined;
  if (init.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.json);
  }
  const timeoutMs = init.timeoutMs ?? 20000;
  const controller = new AbortController();
  const onAbort = () => controller.abort();
  if (init.signal) {
    if (init.signal.aborted) controller.abort();
    else init.signal.addEventListener("abort", onAbort);
  }
  const t = setTimeout(() => controller.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
      ...init,
      headers,
      body,
      signal: controller.signal,
    });
  } catch (e: unknown) {
    const msg =
      e instanceof Error && (e.name === "AbortError" || /aborted|abort/i.test(e.message))
        ? `Request timed out after ${Math.round(timeoutMs / 1000)}s`
        : e instanceof Error
          ? e.message
          : String(e);
    throw new EventflowApiError(0, msg);
  } finally {
    clearTimeout(t);
    init.signal?.removeEventListener("abort", onAbort);
  }
  if (!res.ok) {
    const msg = await readProblemDetail(res);
    throw new EventflowApiError(res.status, msg);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export class EventflowApiError extends Error {
  constructor(
    public readonly status: number,
    message: string
  ) {
    super(message);
    this.name = "EventflowApiError";
  }
}

export async function postShareFromNormalized(
  baseUrl: string,
  token: string | null,
  normalized: NormalizedSharePayload
): Promise<EventDraft> {
  if (normalized.mode === "url" && normalized.url) {
    return request<EventDraft>(baseUrl, "/api/v1/share/url", token, {
      method: "POST",
      json: { url: normalized.url },
    });
  }
  const text = normalized.text ?? normalized.rawText;
  return request<EventDraft>(baseUrl, "/api/v1/share/text", token, {
    method: "POST",
    json: { text },
  });
}

export async function postInstagramCarouselDrafts(
  baseUrl: string,
  token: string | null,
  args: { url: string; carousel_slide_indices?: number[] }
): Promise<ShareCarouselResponse> {
  const json: { url: string; carousel_slide_indices?: number[] } = { url: args.url };
  if (args.carousel_slide_indices !== undefined && args.carousel_slide_indices.length > 0) {
    json.carousel_slide_indices = args.carousel_slide_indices;
  }
  return request<ShareCarouselResponse>(baseUrl, "/api/v1/share/url/instagram-carousel", token, {
    method: "POST",
    json,
  });
}

export async function postInstagramCarouselPreview(
  baseUrl: string,
  token: string | null,
  url: string
): Promise<InstagramCarouselPreviewResponse> {
  return request<InstagramCarouselPreviewResponse>(
    baseUrl,
    "/api/v1/share/url/instagram-carousel-preview",
    token,
    {
      method: "POST",
      json: { url },
    }
  );
}

export async function sharePoster(
  baseUrl: string,
  token: string | null,
  args: { uri: string; mimeType: string; sourceUrl?: string; draftId?: string }
): Promise<SharePosterResponse> {
  const base = baseUrl.replace(/\/$/, "");
  const fd = new FormData();
  fd.append("file", {
    uri: args.uri,
    name: "poster.jpg",
    type: args.mimeType,
  } as unknown as Blob);
  if (args.sourceUrl) fd.append("source_url", args.sourceUrl);
  if (args.draftId) fd.append("draft_id", args.draftId);

  const headers: Record<string, string> = { Accept: "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${base}/api/v1/share/poster`, {
    method: "POST",
    headers,
    body: fd,
  });
  if (!res.ok) {
    const msg = await readProblemDetail(res);
    throw new EventflowApiError(res.status, msg);
  }
  return (await res.json()) as SharePosterResponse;
}

export async function shareMedia(
  baseUrl: string,
  token: string | null,
  args: { uri: string; mimeType: string; filename?: string; sourceText?: string }
): Promise<ShareMediaResponse> {
  const base = baseUrl.replace(/\/$/, "");
  const fd = new FormData();
  fd.append("file", {
    uri: args.uri,
    name: args.filename ?? (args.mimeType.startsWith("video/") ? "shared.mp4" : "shared.jpg"),
    type: args.mimeType,
  } as unknown as Blob);
  if (args.sourceText) fd.append("source_text", args.sourceText);

  const headers: Record<string, string> = { Accept: "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${base}/api/v1/share/media`, { method: "POST", headers, body: fd });
  if (!res.ok) {
    const msg = await readProblemDetail(res);
    throw new EventflowApiError(res.status, msg);
  }
  return (await res.json()) as ShareMediaResponse;
}

export async function parseDraftFromImageToken(
  baseUrl: string,
  token: string | null,
  draftId: string,
  imageToken: string
): Promise<EventDraftDetail> {
  return request<EventDraftDetail>(baseUrl, "/api/v1/share/url/parse-image", token, {
    method: "POST",
    json: { draft_id: draftId, image_token: imageToken },
  });
}

export async function getDraft(
  baseUrl: string,
  token: string | null,
  draftId: string
): Promise<EventDraftDetail> {
  return request<EventDraftDetail>(
    baseUrl,
    `/api/v1/drafts/${draftId}`,
    token,
    { method: "GET" }
  );
}

export async function patchDraft(
  baseUrl: string,
  token: string | null,
  draftId: string,
  body: { title?: string; start_time?: string; venue?: string; price?: string | null }
): Promise<EventDraftDetail> {
  return request<EventDraftDetail>(
    baseUrl,
    `/api/v1/drafts/${draftId}`,
    token,
    { method: "PATCH", json: body }
  );
}

export async function confirmDraft(
  baseUrl: string,
  token: string | null,
  draftId: string
): Promise<EventConfirmed> {
  return request<EventConfirmed>(
    baseUrl,
    `/api/v1/events/confirm/${draftId}`,
    token,
    { method: "POST" }
  );
}

export async function listDrafts(
  baseUrl: string,
  token: string | null,
  args: { status?: "pending" | "confirmed"; limit?: number } = {}
): Promise<DraftListRow[]> {
  const qs: string[] = [];
  if (args.status) qs.push(`status=${encodeURIComponent(args.status)}`);
  if (args.limit) qs.push(`limit=${encodeURIComponent(String(args.limit))}`);
  const q = qs.length ? `?${qs.join("&")}` : "";
  return request<DraftListRow[]>(baseUrl, `/api/v1/drafts${q}`, token, { method: "GET" });
}

export async function listUpcoming(
  baseUrl: string,
  token: string | null,
  daysAhead: number = 30
): Promise<UpcomingEventRow[]> {
  return request<UpcomingEventRow[]>(
    baseUrl,
    `/api/v1/events/upcoming?days_ahead=${encodeURIComponent(String(daysAhead))}`,
    token,
    {
    method: "GET",
    }
  );
}

export async function listToday(
  baseUrl: string,
  token: string | null,
  tzOffsetMinutes: number
): Promise<TodayEventRow[]> {
  return request<TodayEventRow[]>(
    baseUrl,
    `/api/v1/events/today?tz_offset_minutes=${encodeURIComponent(String(tzOffsetMinutes))}`,
    token,
    { method: "GET" }
  );
}

export async function getEta(
  baseUrl: string,
  token: string | null,
  eventId: string,
  lat: number,
  lng: number
): Promise<EtaResponse> {
  return request<EtaResponse>(baseUrl, `/api/v1/events/${eventId}/eta`, token, {
    method: "POST",
    json: { lat, lng },
  });
}

export async function resolveVenueForEvent(
  baseUrl: string,
  token: string | null,
  eventId: string,
  query: string,
  nearLat?: number,
  nearLng?: number
): Promise<{ venue: Venue }> {
  return request<{ venue: Venue }>(baseUrl, `/api/v1/events/${eventId}/resolve-venue`, token, {
    method: "POST",
    json: { query, near_lat: nearLat, near_lng: nearLng },
  });
}

/** Create a venue from coordinates you provide (when Places search finds nothing). */
export async function attachManualVenueToEvent(
  baseUrl: string,
  token: string | null,
  eventId: string,
  body: { name: string; address?: string | null; lat: number; lng: number; place_id?: string | null }
): Promise<{ venue: Venue }> {
  return request<{ venue: Venue }>(baseUrl, `/api/v1/events/${eventId}/venue/manual`, token, {
    method: "POST",
    json: {
      name: body.name,
      ...(body.address != null && body.address !== "" ? { address: body.address } : {}),
      lat: body.lat,
      lng: body.lng,
      ...(body.place_id ? { place_id: body.place_id } : {}),
    },
  });
}

export async function searchVenues(
  baseUrl: string,
  token: string | null,
  q: string
): Promise<Venue[]> {
  return request<Venue[]>(
    baseUrl,
    `/api/v1/venues/search?q=${encodeURIComponent(q)}&limit=10`,
    token,
    { method: "GET" }
  );
}

/** Google Places–style suggestions (server proxies Maps key). */
export type PlaceAutocompletePrediction = {
  place_id: string;
  description: string;
  main_text: string;
  secondary_text?: string | null;
};

export type PlaceAutocompleteResponse = {
  predictions: PlaceAutocompletePrediction[];
};

export type PlaceDetailsResponse = {
  place_id: string;
  name: string;
  formatted_address?: string | null;
  lat: number;
  lng: number;
};

export async function autocompletePlaces(
  baseUrl: string,
  token: string | null,
  args: { input: string; nearLat?: number; nearLng?: number; signal?: AbortSignal }
): Promise<PlaceAutocompleteResponse> {
  const qs = new URLSearchParams();
  qs.set("input", args.input);
  if (args.nearLat != null && args.nearLng != null) {
    qs.set("near_lat", String(args.nearLat));
    qs.set("near_lng", String(args.nearLng));
  }
  return request<PlaceAutocompleteResponse>(
    baseUrl,
    `/api/v1/places/autocomplete?${qs.toString()}`,
    token,
    { method: "GET", signal: args.signal }
  );
}

export async function getPlaceDetails(
  baseUrl: string,
  token: string | null,
  placeId: string,
  signal?: AbortSignal
): Promise<PlaceDetailsResponse> {
  const qs = new URLSearchParams({ place_id: placeId });
  return request<PlaceDetailsResponse>(
    baseUrl,
    `/api/v1/places/details?${qs.toString()}`,
    token,
    { method: "GET", signal }
  );
}

export async function createVenue(
  baseUrl: string,
  token: string | null,
  body: { name: string; address?: string; lat: number; lng: number; place_id?: string }
): Promise<Venue> {
  return request<Venue>(baseUrl, "/api/v1/venues", token, {
    method: "POST",
    json: body,
  });
}

export type EventDetailResponse = {
  id: string;
  user_id: string;
  title: string;
  start_time: string;
  venue: string;
  visibility: "private" | "public";
  price?: string | null;
  description_public?: string | null;
  description_close_friends?: string | null;
  cancelled_at?: string | null;
};

export async function getEvent(
  baseUrl: string,
  token: string | null,
  eventId: string
): Promise<EventDetailResponse> {
  return request<EventDetailResponse>(
    baseUrl,
    `/api/v1/events/${eventId}`,
    token,
    { method: "GET" }
  );
}

export async function patchEventVisibility(
  baseUrl: string,
  token: string | null,
  eventId: string,
  visibility: "private" | "public"
): Promise<{ ok: true; visibility: "private" | "public" }> {
  return request(baseUrl, `/api/v1/events/${eventId}`, token, {
    method: "PATCH",
    json: { visibility },
  });
}

export async function patchEventDescription(
  baseUrl: string,
  token: string | null,
  eventId: string,
  body: { description: string | null; audience: "public" | "close_friends" }
): Promise<{ ok: true }> {
  return request(baseUrl, `/api/v1/events/${eventId}/description`, token, {
    method: "PATCH",
    json: body,
  });
}

export type UserPreferences = {
  monthly_budget_minor_units: number | null;
};

export type BudgetSummary = {
  year: number;
  month: number;
  budget_minor_units: number | null;
  spent_minor_units: number;
  priced_events_count: number;
  unpriced_events_count: number;
  events_total_count: number;
  band: "unset" | "under" | "tight" | "over";
};

export async function getUserPreferences(baseUrl: string, token: string | null): Promise<UserPreferences> {
  return request<UserPreferences>(baseUrl, "/api/v1/users/me/preferences", token, { method: "GET" });
}

export async function patchUserPreferences(
  baseUrl: string,
  token: string | null,
  body: { monthly_budget_minor_units: number | null }
): Promise<UserPreferences> {
  return request<UserPreferences>(baseUrl, "/api/v1/users/me/preferences", token, {
    method: "PATCH",
    json: body,
  });
}

export async function getBudgetSummary(
  baseUrl: string,
  token: string | null,
  args: { year: number; month: number; tzOffsetMinutes: number }
): Promise<BudgetSummary> {
  const qs = new URLSearchParams({
    year: String(args.year),
    month: String(args.month),
    tz_offset_minutes: String(args.tzOffsetMinutes),
  });
  return request<BudgetSummary>(baseUrl, `/api/v1/users/me/budget-summary?${qs.toString()}`, token, {
    method: "GET",
  });
}

export async function cancelEvent(baseUrl: string, token: string | null, eventId: string): Promise<{ status: string }> {
  return request<{ status: string }>(baseUrl, `/api/v1/events/cancel/${eventId}`, token, {
    method: "POST",
  });
}

export async function getDeviceCalendarLink(
  baseUrl: string,
  token: string | null,
  eventId: string
): Promise<{ external_event_id: string; calendar_id: string | null }> {
  return request(baseUrl, `/api/v1/events/${eventId}/device-calendar`, token, { method: "GET" });
}

export async function putDeviceCalendarLink(
  baseUrl: string,
  token: string | null,
  eventId: string,
  body: { external_event_id: string; calendar_id?: string | null }
): Promise<{ ok: boolean }> {
  return request(baseUrl, `/api/v1/events/${eventId}/device-calendar`, token, {
    method: "PUT",
    json: body,
  });
}

export async function deleteDeviceCalendarLink(
  baseUrl: string,
  token: string | null,
  eventId: string
): Promise<void> {
  await request<void>(baseUrl, `/api/v1/events/${eventId}/device-calendar`, token, {
    method: "DELETE",
  });
}

export async function postSnoozeLeaveAlert(
  baseUrl: string,
  token: string | null,
  eventId: string,
  minutes: number = 10
): Promise<{ status: string; fire_at: string }> {
  return request(baseUrl, `/api/v1/events/${eventId}/alerts/snooze`, token, {
    method: "POST",
    json: { minutes },
  });
}

export async function patchEventPrice(
  baseUrl: string,
  token: string | null,
  eventId: string,
  body: { price: string | null }
): Promise<{ ok: true; price: string | null }> {
  return request(baseUrl, `/api/v1/events/${eventId}/price`, token, {
    method: "PATCH",
    json: body,
  });
}

export async function patchEventBasics(
  baseUrl: string,
  token: string | null,
  eventId: string,
  body: { title?: string; start_time?: string; venue?: string }
): Promise<{ ok: true; title: string; start_time: string; venue: string }> {
  return request(baseUrl, `/api/v1/events/${eventId}/basics`, token, {
    method: "PATCH",
    json: body,
  });
}

export async function fetchEventIcs(
  baseUrl: string,
  token: string | null,
  eventId: string
): Promise<string> {
  const res = await fetch(
    `${baseUrl.replace(/\/$/, "")}/api/v1/events/${eventId}/ics`,
    {
      headers: {
        Accept: "text/calendar",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    }
  );
  if (!res.ok) {
    throw new EventflowApiError(res.status, await readProblemDetail(res));
  }
  return res.text();
}

export async function registerExpoPushToken(
  baseUrl: string,
  token: string | null,
  expoPushToken: string,
  platform: "ios" | "android"
): Promise<void> {
  await request(baseUrl, "/api/v1/users/me/push-tokens", token, {
    method: "POST",
    json: {
      expo_push_token: expoPushToken,
      platform,
    },
  });
}

export async function getFeedHome(
  baseUrl: string,
  token: string | null,
  args?: { limit?: number }
): Promise<FeedHomeRow[]> {
  const lim = args?.limit ?? 50;
  return request<FeedHomeRow[]>(baseUrl, `/api/v1/feed/home?limit=${encodeURIComponent(String(lim))}`, token, {
    method: "GET",
  });
}

export async function getDiscoveryFeed(
  baseUrl: string,
  token: string | null,
  args?: { limit?: number }
): Promise<DiscoveryCommunityRow[]> {
  const lim = args?.limit ?? 50;
  return request<DiscoveryCommunityRow[]>(
    baseUrl,
    `/api/v1/discovery/feed?limit=${encodeURIComponent(String(lim))}`,
    token,
    { method: "GET" }
  );
}

export async function getListingCarousel(
  baseUrl: string,
  token: string | null,
  communityEventId: string
): Promise<ListingCarouselResponse> {
  return request<ListingCarouselResponse>(
    baseUrl,
    `/api/v1/listings/${encodeURIComponent(communityEventId)}/carousel`,
    token,
    { method: "GET" }
  );
}

export async function listGroups(baseUrl: string, token: string | null): Promise<GroupRow[]> {
  return request<GroupRow[]>(baseUrl, "/api/v1/groups", token, { method: "GET" });
}

export async function listFollowing(baseUrl: string, token: string | null): Promise<FollowingRow[]> {
  return request<FollowingRow[]>(baseUrl, "/api/v1/follows", token, { method: "GET" });
}

export async function searchUsers(
  baseUrl: string,
  token: string | null,
  q: string,
  opts?: { limit?: number; offset?: number }
): Promise<UserProfileSearchResponse> {
  const lim = opts?.limit ?? 20;
  const off = opts?.offset ?? 0;
  const encoded = encodeURIComponent(q.trim());
  return request<UserProfileSearchResponse>(
    baseUrl,
    `/api/v1/users/search?q=${encoded}&limit=${lim}&offset=${off}`,
    token,
    { method: "GET" }
  );
}

export async function getMyProfile(
  baseUrl: string,
  token: string | null
): Promise<UserProfileRow> {
  return request<UserProfileRow>(baseUrl, "/api/v1/users/me/profile", token, { method: "GET" });
}

export async function upsertMyProfile(
  baseUrl: string,
  token: string | null,
  body: { display_name: string; avatar_url?: string | null; is_public?: boolean }
): Promise<UserProfileRow> {
  return request<UserProfileRow>(baseUrl, "/api/v1/users/me/profile", token, {
    method: "PUT",
    json: body,
  });
}

export async function getUserProfile(
  baseUrl: string,
  token: string | null,
  userId: string
): Promise<UserProfileRow> {
  return request<UserProfileRow>(baseUrl, `/api/v1/users/${userId}/profile`, token, {
    method: "GET",
  });
}

export async function postCreateGroup(
  baseUrl: string,
  token: string | null,
  body: { name: string }
): Promise<GroupRow> {
  return request<GroupRow>(baseUrl, "/api/v1/groups", token, {
    method: "POST",
    json: { name: body.name.trim() },
  });
}

export async function postJoinGroupByToken(
  baseUrl: string,
  token: string | null,
  inviteToken: string
): Promise<{ ok: boolean; group_id: string }> {
  return request<{ ok: boolean; group_id: string }>(baseUrl, "/api/v1/groups/join-by-token", token, {
    method: "POST",
    json: { invite_token: inviteToken.trim() },
  });
}

export async function postFollowUser(
  baseUrl: string,
  token: string | null,
  targetUserId: string
): Promise<{ ok: boolean }> {
  return request(baseUrl, `/api/v1/follows/${encodeURIComponent(targetUserId)}`, token, { method: "POST" });
}

export async function deleteFollowUser(
  baseUrl: string,
  token: string | null,
  targetUserId: string
): Promise<void> {
  await request<void>(baseUrl, `/api/v1/follows/${encodeURIComponent(targetUserId)}`, token, { method: "DELETE" });
}

export async function postListingAnalytics(
  baseUrl: string,
  token: string | null,
  body: {
    metric_type: ListingAnalyticsMetric;
    community_event_id?: string | null;
    business_id?: string | null;
    meta?: Record<string, unknown> | null;
  }
): Promise<void> {
  await request<void>(baseUrl, "/api/v1/listing-analytics", token, {
    method: "POST",
    json: body,
  });
}

export async function postBusiness(
  baseUrl: string,
  token: string | null,
  body: { name: string; whatsapp_e164?: string | null }
): Promise<BusinessResponse> {
  return request<BusinessResponse>(baseUrl, "/api/v1/businesses", token, {
    method: "POST",
    json: { name: body.name.trim(), whatsapp_e164: body.whatsapp_e164?.trim() || null },
  });
}

export async function getBusiness(
  baseUrl: string,
  token: string | null,
  businessId: string
): Promise<BusinessResponse> {
  return request<BusinessResponse>(baseUrl, `/api/v1/businesses/${encodeURIComponent(businessId)}`, token, {
    method: "GET",
  });
}

export type BusinessFollowingRow = {
  business_id: string;
  name: string;
  whatsapp_e164: string | null;
  verified: boolean;
  created_at: string;
};

export async function getFollowBusiness(
  baseUrl: string,
  token: string | null,
  businessId: string
): Promise<{ following: boolean }> {
  return request(baseUrl, `/api/v1/businesses/${encodeURIComponent(businessId)}/follow`, token, { method: "GET" });
}

export async function postFollowBusiness(
  baseUrl: string,
  token: string | null,
  businessId: string
): Promise<{ ok: boolean }> {
  return request(baseUrl, `/api/v1/businesses/${encodeURIComponent(businessId)}/follow`, token, { method: "POST" });
}

export async function deleteFollowBusiness(
  baseUrl: string,
  token: string | null,
  businessId: string
): Promise<void> {
  await request<void>(baseUrl, `/api/v1/businesses/${encodeURIComponent(businessId)}/follow`, token, { method: "DELETE" });
}

export async function listFollowedBusinesses(
  baseUrl: string,
  token: string | null
): Promise<BusinessFollowingRow[]> {
  return request<BusinessFollowingRow[]>(baseUrl, "/api/v1/businesses/following", token, { method: "GET" });
}

export type BusinessProfileResponse = {
  business_id: string;
  name: string;
  description: string | null;
  logo_url: string | null;
  website: string | null;
  contact_email: string | null;
  whatsapp_e164: string | null;
  verified: boolean;
  follower_count: number;
  listing_count: number;
  listings: BusinessProfileListingRow[];
};

export type BusinessProfileListingRow = {
  community_event_id: string;
  title: string;
  start_time: string;
  venue: string;
  poster_image_uri: string | null;
  hero_video_uri: string | null;
  whatsapp_e164: string | null;
};

export async function getBusinessProfile(
  baseUrl: string,
  businessId: string
): Promise<BusinessProfileResponse> {
  return request<BusinessProfileResponse>(
    baseUrl,
    `/api/v1/discovery/business/${encodeURIComponent(businessId)}`,
    null,
    { method: "GET" }
  );
}

export async function patchBusiness(
  baseUrl: string,
  token: string | null,
  businessId: string,
  body: { name?: string; whatsapp_e164?: string | null; description?: string | null; logo_url?: string | null; website?: string | null; contact_email?: string | null }
): Promise<BusinessResponse> {
  return request<BusinessResponse>(
    baseUrl,
    `/api/v1/businesses/${encodeURIComponent(businessId)}`,
    token,
    { method: "PATCH", json: body }
  );
}

export async function postBillingCheckoutStub(
  baseUrl: string,
  token: string | null,
  provider: "stripe" | "mpesa_stub" = "stripe"
): Promise<BillingCheckoutStubResponse> {
  const q = encodeURIComponent(provider);
  return request<BillingCheckoutStubResponse>(
    baseUrl,
    `/api/v1/billing/checkout-session?provider=${q}`,
    token,
    { method: "POST" }
  );
}

// ─── TICKETING v3 (mobile / user-facing) ─────────────────────────────────

export type TicketTypeRow = {
  ticket_type_id: string;
  name: string;
  description: string | null;
  price_minor_units: number;
  currency: string;
  quantity_available: number | null;
  quantity_sold: number;
  sale_start: string | null;
  sale_end: string | null;
  refundable_until: string | null;
  is_active: boolean;
  sort_order: number;
};

export async function listTicketTypes(
  baseUrl: string,
  token: string | null,
  communityEventId: string
): Promise<TicketTypeRow[]> {
  return request<TicketTypeRow[]>(
    baseUrl,
    `/api/v1/listings/${encodeURIComponent(communityEventId)}/ticket-types`,
    token,
    { method: "GET" }
  );
}

export type PurchaseRequest = {
  community_event_id: string;
  items: { ticket_type_id: string; quantity: number }[];
  payment_provider?: string;
};

export type PurchaseResponse = {
  order_id: string;
  receipt_number: string;
  total_minor_units: number;
  platform_fee_minor_units: number;
  payment_provider: string;
  ticket_codes: string[];
  points_earned: number;
};

export async function purchaseTickets(
  baseUrl: string,
  token: string | null,
  body: PurchaseRequest
): Promise<PurchaseResponse> {
  return request<PurchaseResponse>(baseUrl, "/api/v1/tickets/purchase", token, {
    method: "POST",
    json: body,
  });
}

export type OrderRow = {
  order_id: string;
  community_event_id: string;
  event_title: string;
  status: string;
  type: string;
  total_minor_units: number;
  platform_fee_minor_units: number;
  payment_provider: string | null;
  receipt_number: string | null;
  points_earned: number;
  paid_at: string | null;
  created_at: string;
  tickets: { ticket_id: string; short_code: string; ticket_type_name: string; status: string; checked_in_at: string | null }[];
};

export async function listMyOrders(baseUrl: string, token: string | null): Promise<OrderRow[]> {
  return request<OrderRow[]>(baseUrl, "/api/v1/tickets/orders", token, { method: "GET" });
}

export async function getOrder(baseUrl: string, token: string | null, orderId: string): Promise<OrderRow> {
  return request<OrderRow>(baseUrl, `/api/v1/tickets/orders/${encodeURIComponent(orderId)}`, token, { method: "GET" });
}

export type FeedVideoRow = {
  video_id: string;
  title: string;
  video_uri: string | null;
  thumbnail_uri: string | null;
  video_type: string;
  moderation_status: string;
  views: number;
  whatsapp_taps: number;
  created_at: string | null;
  business_name: string | null;
  event_title: string | null;
  community_event_id: string | null;
};

export async function getDiscoveryFeedV3(baseUrl: string, token: string | null): Promise<FeedVideoRow[]> {
  return request<FeedVideoRow[]>(baseUrl, "/api/v1/feed/discover", token, { method: "GET" });
}

export async function logFeedWatch(baseUrl: string, token: string | null, videoId: string): Promise<{ points_earned: number }> {
  return request<{ points_earned: number }>(
    baseUrl,
    `/api/v1/feed/watch?video_id=${encodeURIComponent(videoId)}`,
    token,
    { method: "POST" }
  );
}

export type WatchQuotaResponse = {
  is_premium: boolean;
  videos_watched_today: number;
  videos_remaining: number;
  daily_limit: number;
  premium_price_minor: number;
};

export async function getWatchQuota(baseUrl: string, token: string | null): Promise<WatchQuotaResponse> {
  return request<WatchQuotaResponse>(baseUrl, "/api/v1/feed/status", token, { method: "GET" });
}

// ─── UNIFIED FEED (Discover v2) ─────────────────────────────────────

export type UnifiedFeedVideo = {
  item_id: string;
  kind: "video";
  title: string;
  video_uri: string | null;
  thumbnail_uri: string | null;
  duration_seconds: number | null;
  views: number;
  whatsapp_taps: number;
  video_type: string;
  community_event_id: string | null;
  event_title: string | null;
  business_id: string | null;
  business_name: string | null;
  business_logo: string | null;
  whatsapp_e164: string | null;
};

export type UnifiedFeedEvent = {
  item_id: string;
  kind: "event";
  title: string;
  start_time: string;
  venue: string;
  description: string | null;
  poster_image_uri: string | null;
  organizer_user_id: string;
  business_id: string | null;
  whatsapp_e164: string | null;
  hero_video_uri: string | null;
  attending_friends_count: number;
  attending_friend_ids: string[];
  price_minor_units: number | null;
};

export type UnifiedFeedAffiliate = {
  item_id: string;
  kind: "affiliate";
  title: string;
  description: string | null;
  price_minor_units: number;
  image_uri: string | null;
  seller_business_id: string;
  seller_name: string | null;
  whatsapp_e164: string | null;
  community_event_id: string;
  event_title: string | null;
  commission_seller_percent: number | null;
};

export type UnifiedFeedItem = UnifiedFeedVideo | UnifiedFeedEvent | UnifiedFeedAffiliate;

export async function getUnifiedFeed(
  baseUrl: string,
  token: string | null,
  args?: { limit?: number }
): Promise<UnifiedFeedItem[]> {
  const lim = args?.limit ?? 50;
  return request<UnifiedFeedItem[]>(
    baseUrl,
    `/api/v1/discover/unified-feed?limit=${encodeURIComponent(String(lim))}`,
    token,
    { method: "GET" }
  );
}

export type PointsResponse = {
  balance: number;
  lifetime_earned: number;
  lifetime_redeemed: number;
  last_activity: string | null;
  discount_code: string | null;
  discount_minor: number | null;
};

export async function getPoints(baseUrl: string, token: string | null): Promise<PointsResponse> {
  return request<PointsResponse>(baseUrl, "/api/v1/points", token, { method: "GET" });
}

export async function redeemPoints(baseUrl: string, token: string | null, points: number): Promise<PointsResponse> {
  return request<PointsResponse>(baseUrl, "/api/v1/points/redeem", token, {
    method: "POST",
    json: { points },
  });
}

export type SubscriptionResponse = {
  subscription_id: string;
  plan: string;
  status: string;
  current_period_end: string | null;
  created_at: string | null;
};

export async function getSubscription(baseUrl: string, token: string | null): Promise<SubscriptionResponse | null> {
  return request<SubscriptionResponse | null>(baseUrl, "/api/v1/subscriptions", token, { method: "GET" });
}

export type CheckoutSessionResponse = {
  url: string | null;
  error: string | null;
};

export async function createCheckoutSession(
  baseUrl: string,
  token: string | null
): Promise<CheckoutSessionResponse> {
  return request<CheckoutSessionResponse>(baseUrl, "/api/v1/subscriptions/checkout", token, {
    method: "POST",
  });
}

export async function purchaseSubscription(
  baseUrl: string,
  token: string | null
): Promise<SubscriptionResponse> {
  return request<SubscriptionResponse>(baseUrl, "/api/v1/subscriptions/create", token, {
    method: "POST",
  });
}

export type ProductRow = {
  product_id: string;
  title: string;
  description: string | null;
  price_minor_units: number;
  image_uri: string | null;
  seller_business_id: string;
  seller_name: string;
};

export async function listEventProducts(baseUrl: string, token: string | null, communityEventId: string): Promise<ProductRow[]> {
  return request<ProductRow[]>(
    baseUrl,
    `/api/v1/events/${encodeURIComponent(communityEventId)}/products`,
    token,
    { method: "GET" }
  );
}

export type ClaimResponse = {
  claim_id: string;
  status: string;
  admin_notes: string | null;
  created_at: string;
  resolved_at: string | null;
};

export async function createClaim(
  baseUrl: string,
  token: string | null,
  body: { order_id: string; claim_type: string; reason?: string }
): Promise<ClaimResponse> {
  return request<ClaimResponse>(baseUrl, "/api/v1/tickets/claims", token, { method: "POST", json: body });
}

export async function listMyClaims(baseUrl: string, token: string | null): Promise<ClaimResponse[]> {
  return request<ClaimResponse[]>(baseUrl, "/api/v1/tickets/claims", token, { method: "GET" });
}

// ─── COMMUNITY EVENT SAVE / ICS / RSVP ─────────────────────────────

export async function getCommunityEventDetail(
  baseUrl: string,
  token: string | null,
  communityEventId: string
): Promise<UnifiedFeedEvent> {
  return request<UnifiedFeedEvent>(
    baseUrl,
    `/api/v1/discovery/community-events/${encodeURIComponent(communityEventId)}`,
    token,
    { method: "GET" }
  );
}

export async function saveCommunityEventToCalendar(
  baseUrl: string,
  token: string | null,
  communityEventId: string
): Promise<{ scheduled_event_id: string; ok: boolean }> {
  return request<{ scheduled_event_id: string; ok: boolean }>(
    baseUrl,
    `/api/v1/discovery/community-events/${encodeURIComponent(communityEventId)}/save-to-calendar`,
    token,
    { method: "POST" }
  );
}

export async function getSavedCommunityEvents(
  baseUrl: string,
  token: string | null
): Promise<UnifiedFeedEvent[]> {
  return request<UnifiedFeedEvent[]>(
    baseUrl,
    "/api/v1/discovery/community-events/saved",
    token,
    { method: "GET" }
  );
}

export async function fetchCommunityEventIcs(
  baseUrl: string,
  token: string | null,
  communityEventId: string
): Promise<string> {
  const res = await fetch(
    `${baseUrl.replace(/\/$/, "")}/api/v1/discovery/community-events/${encodeURIComponent(communityEventId)}/ics`,
    {
      headers: {
        Accept: "text/calendar",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    }
  );
  if (!res.ok) throw new EventflowApiError(res.status, await readProblemDetail(res));
  return res.text();
}

export async function postRsvp(
  baseUrl: string,
  token: string | null,
  communityEventId: string,
  status: "going" | "maybe" | "not_going"
): Promise<{ status: string; ok: boolean }> {
  return request<{ status: string; ok: boolean }>(
    baseUrl,
    `/api/v1/discovery/community-events/${encodeURIComponent(communityEventId)}/rsvp`,
    token,
    { method: "POST", json: { status } }
  );
}

export async function getRsvpStatus(
  baseUrl: string,
  token: string | null,
  communityEventId: string
): Promise<{ status: string | null }> {
  return request<{ status: string | null }>(
    baseUrl,
    `/api/v1/discovery/community-events/${encodeURIComponent(communityEventId)}/rsvp`,
    token,
    { method: "GET" }
  );
}

export async function getBusinessEvents(
  baseUrl: string,
  _token: string | null,
  businessId: string
): Promise<BusinessProfileListingRow[]> {
  const profile = await getBusinessProfile(baseUrl, businessId);
  return profile.listings;
}

// ─── USER PUBLIC PROFILE ────────────────────────────────────────

export type PublicProfileEventRow = {
  community_event_id: string;
  title: string;
  start_time: string;
  venue: string;
  poster_image_uri: string | null;
  role: "organizer" | "attendee";
};

export type UserPublicProfileResponse = {
  user_id: string;
  display_name: string;
  avatar_url: string | null;
  events: PublicProfileEventRow[];
};

export async function getUserPublicProfile(
  baseUrl: string,
  token: string | null,
  userId: string
): Promise<UserPublicProfileResponse> {
  return request<UserPublicProfileResponse>(
    baseUrl,
    `/api/v1/users/${encodeURIComponent(userId)}/public-profile`,
    token,
    { method: "GET" }
  );
}


