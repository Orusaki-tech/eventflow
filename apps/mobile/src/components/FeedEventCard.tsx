import React from "react";
import {
  Dimensions,
  Image,
  Linking,
  Pressable,
  StyleSheet,
  View,
} from "react-native";
import type { UnifiedFeedEvent } from "../api/eventflow";
import { AppText } from "../design/components";
import { pressedOpacityStyle, tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { navigationRef } from "../navigation/navigationRef";

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get("window");

type Props = {
  item: UnifiedFeedEvent;
};

export function FeedEventCard({ item }: Props) {
  const { colors } = useTheme();

  const attendingText =
    item.attending_friends_count > 0
      ? `${item.attending_friends_count} friend${item.attending_friends_count !== 1 ? "s" : ""} going`
      : null;

  const startDate = new Date(item.start_time);
  const dateStr = startDate.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });

  return (
    <View style={[styles.container, { backgroundColor: colors.bg }]}>
      {/* Background poster */}
      {item.poster_image_uri ? (
        <Image source={{ uri: item.poster_image_uri }} style={styles.poster} resizeMode="cover" />
      ) : (
        <View style={[styles.poster, { backgroundColor: colors.surface1 }]} />
      )}

      {/* Overlay gradient effect via semi-transparent bottom */}
      <View style={styles.overlay} />

      {/* Content */}
      <View style={styles.content}>
        <View style={styles.badge}>
          <AppText style={styles.badgeText}>{dateStr}</AppText>
        </View>

        <AppText style={styles.title} numberOfLines={2}>
          {item.title}
        </AppText>

        <AppText style={styles.venue} numberOfLines={1}>
          {item.venue}
        </AppText>

        {attendingText ? (
          <AppText style={styles.attending}>{attendingText}</AppText>
        ) : null}

        <View style={styles.actions}>
          {item.whatsapp_e164 ? (
            <Pressable
              style={({ pressed }) => [styles.whatsappBtn, pressedOpacityStyle(pressed)]}
              onPress={() => {
                const url = `https://wa.me/${item.whatsapp_e164?.replace(/^\+/, "")}`;
                Linking.openURL(url);
              }}
            >
              <AppText style={styles.whatsappText}>Chat</AppText>
            </Pressable>
          ) : null}

          <Pressable
            style={({ pressed }) => [styles.detailBtn, pressedOpacityStyle(pressed)]}
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
                });
              }
            }}
          >
            <AppText style={styles.detailText}>View Details</AppText>
          </Pressable>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: SCREEN_WIDTH,
    height: SCREEN_HEIGHT,
  },
  poster: {
    ...StyleSheet.absoluteFillObject,
  },
  overlay: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    height: "50%",
    backgroundColor: "rgba(0,0,0,0.4)",
  },
  content: {
    position: "absolute",
    bottom: 120,
    left: 16,
    right: 16,
    gap: 8,
  },
  badge: {
    alignSelf: "flex-start",
    backgroundColor: "rgba(255,255,255,0.2)",
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  badgeText: {
    color: "#fff",
    fontSize: 13,
    fontWeight: "600",
  },
  title: {
    fontSize: 24,
    fontWeight: "900",
    color: "#fff",
    textShadowColor: "rgba(0,0,0,0.6)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 3,
  },
  venue: {
    fontSize: 16,
    color: "rgba(255,255,255,0.8)",
    textShadowColor: "rgba(0,0,0,0.4)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 2,
  },
  attending: {
    fontSize: 14,
    fontWeight: "700",
    color: "#4CAF50",
    textShadowColor: "rgba(0,0,0,0.4)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 2,
  },
  actions: {
    flexDirection: "row",
    gap: 12,
    marginTop: 8,
  },
  whatsappBtn: {
    backgroundColor: "#25D366",
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 24,
  },
  whatsappText: {
    color: "#fff",
    fontWeight: "700",
    fontSize: 14,
  },
  detailBtn: {
    backgroundColor: "rgba(255,255,255,0.2)",
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 24,
  },
  detailText: {
    color: "#fff",
    fontWeight: "600",
    fontSize: 14,
  },
});
