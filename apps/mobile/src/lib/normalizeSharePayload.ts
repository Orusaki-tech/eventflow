/** Hosts where fetching the URL usually beats caption-only parsing. */
const PREFERRED_HOST_SUBSTRINGS = [
  "tiktok.com",
  "instagram.com",
  "facebook.com",
  "fb.me",
  "eventbrite.com",
  "meetup.com",
  "luma.co",
  "t.co",
  "youtube.com",
  "youtu.be",
];

const URL_REGEX = /\bhttps?:\/\/[^\s<>"{}|\\^`[\]]+/gi;

export type ShareCaptureMode = "url" | "text";

export type NormalizedSharePayload = {
  mode: ShareCaptureMode;
  url?: string;
  text?: string;
  urlsFound: string[];
  rawText: string;
};

export function extractUrls(raw: string): string[] {
  const matches = raw.match(URL_REGEX) ?? [];
  const seen = new Set<string>();
  const ordered: string[] = [];
  for (const u of matches) {
    const trimmed = u.replace(/[),.;]+$/, "");
    if (!seen.has(trimmed)) {
      seen.add(trimmed);
      ordered.push(trimmed);
    }
  }
  return ordered;
}

function scoreUrl(url: string): number {
  const lower = url.toLowerCase();
  let score = 0;
  for (const h of PREFERRED_HOST_SUBSTRINGS) {
    if (lower.includes(h)) score += 10;
  }
  return score;
}

/** Pick primary URL: highest host score, then first in document order. */
/** Instagram photo posts only (`/p/<shortcode>/`); reels and stories use different paths. */
/** Legacy helper: typed slide numbers (max 2). Instagram imports now use the carousel picker UI instead. */
export function parseCarouselSlideIndicesInput(raw: string): number[] | undefined {
  const s = raw.trim();
  if (!s) return undefined;
  const parts = s.split(/[\s,]+/).filter(Boolean);
  const nums = parts
    .map((p) => parseInt(p, 10))
    .filter((n) => Number.isFinite(n) && n >= 1);
  const uniq = Array.from(new Set(nums)).sort((a, b) => a - b);
  return uniq.slice(0, 2);
}

export function isInstagramPostUrl(url: string): boolean {
  try {
    const u = new URL(url);
    const host = u.hostname.replace(/^www\./i, "").toLowerCase();
    if (host !== "instagram.com" && !host.endsWith(".instagram.com")) return false;
    return /^\/p\/[^/]+\/?/.test(u.pathname);
  } catch {
    return false;
  }
}

/** Strip slide-specific query params so `/instagram-carousel-preview` returns every slide. */
export function instagramPostUrlForCarouselPreview(url: string): string {
  try {
    const u = new URL(url);
    u.searchParams.delete("img_index");
    u.searchParams.delete("carousel_index");
    return u.toString();
  } catch {
    return url;
  }
}

/** Instagram `img_index` / `carousel_index` from the shared URL (1-based). Defaults to 1. */
export function getInstagramSlideIndexFromUrl(url: string): number {
  try {
    const u = new URL(url);
    for (const key of ["img_index", "carousel_index"]) {
      const v = u.searchParams.get(key);
      if (v == null) continue;
      const n = parseInt(v, 10);
      if (Number.isFinite(n) && n >= 1) return n;
    }
  } catch {
    /* ignore */
  }
  return 1;
}

export function pickPrimaryUrl(urls: string[]): string | undefined {
  if (urls.length === 0) return undefined;
  if (urls.length === 1) return urls[0];
  let best = urls[0];
  let bestScore = scoreUrl(best);
  for (const u of urls.slice(1)) {
    const s = scoreUrl(u);
    if (s > bestScore || (s === bestScore && u.length > best.length)) {
      best = u;
      bestScore = s;
    }
  }
  return best;
}

/**
 * Decide whether to call POST /share/url or /share/text.
 * Prefer URL fetch when a link is present (richer page text on server).
 */
export function normalizeSharePayload(rawText: string): NormalizedSharePayload {
  const raw = rawText.trim();
  const urlsFound = extractUrls(raw);
  const primary = pickPrimaryUrl(urlsFound);

  if (primary) {
    return {
      mode: "url",
      url: primary,
      urlsFound,
      rawText: raw,
    };
  }

  return {
    mode: "text",
    text: raw,
    urlsFound,
    rawText: raw,
  };
}
