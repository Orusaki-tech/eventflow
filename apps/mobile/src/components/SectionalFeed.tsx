import React, { useMemo } from "react";
import { RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import type { UnifiedFeedAffiliate, UnifiedFeedEvent, UnifiedFeedItem, UnifiedFeedVideo } from "../api/eventflow";
import { AppText } from "../design/components";
import { tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { AffiliateCardCompact } from "./AffiliateCardCompact";
import { COMPACT_CARD_WIDTH, EventCardCompact } from "./EventCardCompact";
import { VideoCardCompact } from "./VideoCardCompact";

export type Section = {
  id: string;
  title: string;
  items: UnifiedFeedItem[];
};

type Props = {
  items: UnifiedFeedItem[];
  refreshing: boolean;
  onRefresh: () => void;
  ListHeaderComponent?: React.ComponentType<any> | React.ReactElement | null;
};

function categorizeSections(items: UnifiedFeedItem[]): Section[] {
  const now = new Date();

  const events = items.filter((i): i is UnifiedFeedEvent => i.kind === "event");
  const videos = items.filter((i): i is UnifiedFeedVideo => i.kind === "video");
  const affiliates = items.filter((i): i is UnifiedFeedAffiliate => i.kind === "affiliate");

  const sections: Section[] = [];

  // 1. For You — mix of all types, up to 10
  const forYouUnshuffled = [
    ...events.slice(0, 3),
    ...videos.slice(0, 4),
    ...affiliates.slice(0, 3),
  ];
  for (let i = forYouUnshuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [forYouUnshuffled[i], forYouUnshuffled[j]] = [forYouUnshuffled[j], forYouUnshuffled[i]];
  }
  const forYou = forYouUnshuffled;
  if (forYou.length > 0) {
    sections.push({ id: "for_you", title: "For You", items: forYou.slice(0, 10) });
  }

  // 2. Upcoming Events — future events sorted by start_time
  const upcoming = events
    .filter((e) => new Date(e.start_time) > now)
    .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());
  if (upcoming.length > 0) {
    sections.push({ id: "upcoming", title: "Upcoming Events", items: upcoming });
  }

  // 3. Trending Events — sorted by attending friends count
  const trending = [...upcoming].sort((a, b) => b.attending_friends_count - a.attending_friends_count);
  if (trending.length > 0) {
    sections.push({ id: "trending", title: "Trending Events", items: trending });
  }

  // 4. Trending Videos — sorted by views
  const trendingVideos = [...videos].sort((a, b) => b.views - a.views);
  if (trendingVideos.length > 0) {
    sections.push({
      id: "trending_videos",
      title: "Trending Videos",
      items: trendingVideos,
    });
  }

  // 5. Event Videos — videos linked to a community event
  const eventVids = videos
    .filter((v) => v.community_event_id != null)
    .sort((a, b) => b.views - a.views);
  if (eventVids.length > 0) {
    sections.push({ id: "event_videos", title: "Event Videos", items: eventVids });
  }

  // 6. Business Spotlight — videos with business_name, sorted by views
  const bizVids = videos
    .filter((v) => v.business_name != null)
    .sort((a, b) => b.views - a.views);
  if (bizVids.length > 0) {
    sections.push({
      id: "business_spotlight",
      title: "Business Spotlight",
      items: bizVids,
    });
  }

  // 7. Affiliate Offers
  if (affiliates.length > 0) {
    sections.push({ id: "offers", title: "Affiliate Offers", items: affiliates });
  }

  return sections;
}

function SectionRow({ section }: { section: Section }) {
  const { colors } = useTheme();

  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <AppText variant="title" style={{ color: colors.textPrimary }}>
          {section.title}
        </AppText>
      </View>

      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
        decelerationRate="fast"
        snapToInterval={COMPACT_CARD_WIDTH + tokens.spacing[10]}
      >
        {section.items.map((item) => {
          const key = `${section.id}_${item.item_id}`;
          switch (item.kind) {
            case "event":
              return <EventCardCompact key={key} item={item} />;
            case "affiliate":
              return <AffiliateCardCompact key={key} item={item} />;
            case "video":
              return <VideoCardCompact key={key} item={item} />;
            default:
              return null;
          }
        })}
      </ScrollView>
    </View>
  );
}

export function SectionalFeed({ items, refreshing, onRefresh, ListHeaderComponent }: Props) {
  const { colors } = useTheme();
  const sections = useMemo(() => categorizeSections(items), [items]);

  if (sections.length === 0) {
    return (
      <View style={[styles.empty, { backgroundColor: colors.bg }]}>
        <AppText tone="tertiary">No content yet</AppText>
      </View>
    );
  }

  return (
    <ScrollView
      showsVerticalScrollIndicator={false}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          tintColor={colors.textSecondary}
        />
      }
    >
      {ListHeaderComponent && <View>{ListHeaderComponent as any}</View>}
      {sections.map((section) => (
        <SectionRow key={section.id} section={section} />
      ))}
      <View style={{ height: 32 }} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  section: {
    marginTop: tokens.spacing[20],
  },
  sectionHeader: {
    paddingHorizontal: tokens.spacing[16],
    marginBottom: tokens.spacing[12],
  },
  scrollContent: {
    paddingHorizontal: tokens.spacing[16],
  },
  empty: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
});
