import React from "react";
import { Image, Pressable, StyleSheet, View } from "react-native";
import type { UnifiedFeedEvent } from "../api/eventflow";
import { AppText } from "../design/components";
import { pressedOpacityStyle, tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { navigationRef } from "../navigation/navigationRef";

export const COMPACT_CARD_WIDTH = 150;
export const COMPACT_CARD_HEIGHT = 220;

type Props = {
  item: UnifiedFeedEvent;
};

export function EventCardCompact({ item }: Props) {
  const { colors } = useTheme();

  const startDate = new Date(item.start_time);
  const month = startDate.toLocaleDateString(undefined, { month: "short" });
  const day = startDate.getDate();

  const attendingText =
    item.attending_friends_count > 0
      ? `${item.attending_friends_count} going`
      : null;

  return (
    <Pressable
      style={({ pressed }) => [styles.card, pressedOpacityStyle(pressed)]}
      onPress={() => {
        if (navigationRef.isReady()) {
          navigationRef.navigate("CommunityListingDetail", {
            communityEventId: item.item_id,
            organizerUserId: item.organizer_user_id,
            title: item.title,
            start_time: item.start_time,
            venue: item.venue,
            whatsapp_e164: item.whatsapp_e164 ?? null,
            business_id: item.business_id ?? null,
            viewMode: "viewer",
          });
        }
      }}
    >
      <View style={[styles.imageWrap, { backgroundColor: colors.surface1 }]}>
        {item.poster_image_uri ? (
          <Image source={{ uri: item.poster_image_uri }} style={styles.image} resizeMode="cover" />
        ) : null}
        <View style={styles.dateBadge}>
          <AppText style={styles.dateMonth}>{month}</AppText>
          <AppText style={styles.dateDay}>{day}</AppText>
        </View>
      </View>

      <View style={styles.body}>
        <AppText numberOfLines={2} style={styles.title}>
          {item.title}
        </AppText>
        <AppText numberOfLines={1} style={styles.venue}>
          {item.venue}
        </AppText>
        {attendingText ? (
          <AppText style={styles.attending}>{attendingText}</AppText>
        ) : null}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    width: COMPACT_CARD_WIDTH,
    marginRight: tokens.spacing[10],
  },
  imageWrap: {
    width: COMPACT_CARD_WIDTH,
    height: COMPACT_CARD_WIDTH,
    borderRadius: tokens.radii.sm,
    overflow: "hidden",
    position: "relative",
  },
  image: {
    width: "100%",
    height: "100%",
  },
  dateBadge: {
    position: "absolute",
    top: 8,
    left: 8,
    backgroundColor: "rgba(0,0,0,0.75)",
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
    alignItems: "center",
  },
  dateMonth: {
    color: "#fff",
    fontSize: 10,
    fontWeight: "700",
    textTransform: "uppercase",
  },
  dateDay: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "900",
  },
  body: {
    paddingTop: 8,
    gap: 2,
  },
  title: {
    fontSize: 13,
    fontWeight: "800",
    lineHeight: 16,
  },
  venue: {
    fontSize: 11,
    lineHeight: 14,
    color: "rgba(255,255,255,0.6)",
  },
  attending: {
    fontSize: 11,
    fontWeight: "700",
    color: "#4CAF50",
  },
});
