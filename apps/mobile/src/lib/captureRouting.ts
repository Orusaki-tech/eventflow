import { isInstagramPostUrl, normalizeSharePayload } from "./normalizeSharePayload";

/** Instagram photo posts that support carousel slide selection before Gemini. */
export function shouldPickInstagramCarouselSlides(rawText: string): { rawText: string; instagramUrl: string } | null {
  const n = normalizeSharePayload(rawText.trim());
  if (n.mode !== "url" || !n.url || !isInstagramPostUrl(n.url)) return null;
  return { rawText: n.rawText, instagramUrl: n.url };
}
