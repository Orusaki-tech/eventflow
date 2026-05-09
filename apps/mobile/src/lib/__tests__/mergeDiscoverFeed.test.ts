/**
 * Manual QA (Discover / listings):
 * - Signed-in: personalized rows precede discovery-only rows; no duplicate community_event ids.
 * - Tap row opens CommunityListingDetail; impression analytics when authenticated.
 * - Snooze: future EventDetail shows presets; 409 when event already started.
 */
import type { DiscoveryCommunityRow, FeedHomeRow } from "../../api/eventflow";
import { mergeDiscoverSources } from "../mergeDiscoverFeed";

describe("mergeDiscoverSources", () => {
  const feed: FeedHomeRow[] = [
    {
      id: "aaa",
      title: "A",
      start_time: "2026-06-01T12:00:00Z",
      venue: "V1",
      user_id: "user-1",
      sponsored_rank: 2,
    },
  ];
  const discovery: DiscoveryCommunityRow[] = [
    {
      community_event_id: "aaa",
      title: "Dup",
      start_time: "2026-06-01T12:00:00Z",
      venue: "V",
    },
    {
      community_event_id: "bbb",
      title: "B",
      start_time: "2026-07-01T12:00:00Z",
      venue: "V2",
    },
  ];

  it("dedupes by id preferring feed row order", () => {
    const merged = mergeDiscoverSources(feed, discovery);
    expect(merged.map((m) => m.communityEventId)).toEqual(["aaa", "bbb"]);
    expect(merged[0].organizerUserId).toBe("user-1");
    expect(merged[1].organizerUserId).toBeNull();
  });
});
