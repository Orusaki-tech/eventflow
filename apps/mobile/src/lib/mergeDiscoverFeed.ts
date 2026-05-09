import type { DiscoveryCommunityRow, FeedHomeRow } from "../api/eventflow";

export type DiscoverMergedRow = {
  communityEventId: string;
  title: string;
  start_time: string;
  venue: string;
  organizerUserId: string | null;
  sponsored_rank?: number | null;
  poster_image_uri?: string | null;
  business_id?: string | null;
  whatsapp_e164?: string | null;
  hero_video_uri?: string | null;
};

/** Personalized feed rows first (stable order), then discovery-only rows without duplicate ids. */
export function mergeDiscoverSources(feedRows: FeedHomeRow[], discoveryRows: DiscoveryCommunityRow[]): DiscoverMergedRow[] {
  const seen = new Set<string>();
  const out: DiscoverMergedRow[] = [];
  for (const r of feedRows) {
    const id = r.id;
    if (seen.has(id)) continue;
    seen.add(id);
    out.push({
      communityEventId: id,
      title: r.title,
      start_time: r.start_time,
      venue: r.venue,
      organizerUserId: r.user_id,
      sponsored_rank: r.sponsored_rank ?? undefined,
      poster_image_uri: r.poster_image_uri ?? null,
      business_id: r.business_id ?? null,
      whatsapp_e164: r.whatsapp_e164 ?? null,
      hero_video_uri: r.hero_video_uri ?? null,
    });
  }
  for (const r of discoveryRows) {
    const id = r.community_event_id;
    if (seen.has(id)) continue;
    seen.add(id);
    out.push({
      communityEventId: id,
      title: r.title,
      start_time: r.start_time,
      venue: r.venue,
      organizerUserId: null,
      sponsored_rank: null,
      poster_image_uri: r.poster_image_uri ?? null,
      business_id: r.business_id ?? null,
      whatsapp_e164: r.whatsapp_e164 ?? null,
      hero_video_uri: r.hero_video_uri ?? null,
    });
  }
  return out;
}
