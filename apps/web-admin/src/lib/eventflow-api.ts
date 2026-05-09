/** Browser-safe API origin: direct URL, or same-origin proxy when NEXT_PUBLIC_EVENTFLOW_API_PROXY=1. */
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
    let detail = res.statusText?.trim() || "";
    try {
      const j = (await res.json()) as Record<string, unknown>;
      const d = j.detail;
      if (typeof d === "string" && d.trim()) detail = d;
      else if (d !== undefined) detail = JSON.stringify(d);
      else if (typeof j.title === "string" && j.title.trim())
        detail = `${j.title}${typeof j.status === "number" ? ` (${j.status})` : ""}`;
    } catch {
      /* ignore */
    }
    const err = new Error(detail || `HTTP ${res.status}`) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export type AdminMeResponse = { ok: boolean; user_id: string };

export async function getAdminMe(token: string): Promise<AdminMeResponse> {
  return efFetch("/api/v1/admin/console/me", token, { method: "GET" });
}

export type AdminSummaryResponse = {
  businesses: number;
  community_events: number;
  poster_assets: number;
  event_drafts: number;
  distinct_active_user_ids: number;
};

export async function getAdminSummary(token: string): Promise<AdminSummaryResponse> {
  return efFetch("/api/v1/admin/console/summary", token, { method: "GET" });
}

export type AdminBusinessRow = {
  business_id: string;
  name: string;
  whatsapp_e164: string | null;
  owner_user_id: string | null;
  verified: boolean;
  created_at: string;
};

export type AdminBusinessListResponse = {
  items: AdminBusinessRow[];
  total: number;
  limit: number;
  offset: number;
};

export async function listAdminBusinesses(
  token: string,
  params: { limit?: number; offset?: number; q?: string }
): Promise<AdminBusinessListResponse> {
  const q = new URLSearchParams();
  if (params.limit != null) q.set("limit", String(params.limit));
  if (params.offset != null) q.set("offset", String(params.offset));
  if (params.q?.trim()) q.set("q", params.q.trim());
  const qs = q.toString();
  return efFetch(`/api/v1/admin/console/businesses${qs ? `?${qs}` : ""}`, token, { method: "GET" });
}

export type BusinessVerifiedRow = {
  business_id: string;
  name: string;
  whatsapp_e164: string | null;
  verified: boolean;
};

export async function patchAdminBusinessVerified(
  token: string,
  businessId: string,
  body: { verified: boolean }
): Promise<BusinessVerifiedRow> {
  return efFetch(`/api/v1/admin/console/businesses/${encodeURIComponent(businessId)}/verified`, token, {
    method: "PATCH",
    json: body,
  });
}

export type AdminCommunityEventRow = {
  community_event_id: string;
  user_id: string;
  title: string;
  start_time: string;
  venue: string;
  source: string;
  poster_image_uri?: string | null;
  attached_business_id?: string | null;
};

export type AdminCommunityEventListResponse = {
  items: AdminCommunityEventRow[];
  total: number;
  limit: number;
  offset: number;
};

export async function listAdminCommunityEvents(
  token: string,
  params: { limit?: number; offset?: number; q?: string }
): Promise<AdminCommunityEventListResponse> {
  const q = new URLSearchParams();
  if (params.limit != null) q.set("limit", String(params.limit));
  if (params.offset != null) q.set("offset", String(params.offset));
  if (params.q?.trim()) q.set("q", params.q.trim());
  const qs = q.toString();
  return efFetch(`/api/v1/admin/console/community-events${qs ? `?${qs}` : ""}`, token, { method: "GET" });
}

export type AdminPosterAssetRow = {
  poster_asset_id: string;
  content_sha256: string | null;
  dhash64: string;
  created_at: string;
  content_type: string;
  event_source_links: number;
  draft_links: number;
  scheduled_event_links: number;
};

export type AdminPosterAssetListResponse = {
  items: AdminPosterAssetRow[];
  total: number;
  limit: number;
  offset: number;
};

export async function listAdminPosterAssets(
  token: string,
  params: { limit?: number; offset?: number }
): Promise<AdminPosterAssetListResponse> {
  const q = new URLSearchParams();
  if (params.limit != null) q.set("limit", String(params.limit));
  if (params.offset != null) q.set("offset", String(params.offset));
  const qs = q.toString();
  return efFetch(`/api/v1/admin/console/poster-assets${qs ? `?${qs}` : ""}`, token, { method: "GET" });
}
