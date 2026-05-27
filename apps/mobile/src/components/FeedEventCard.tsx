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
  onSaveToCalendar?: (item: UnifiedFeedEvent) => void;
};

function formatPrice(minor: number | null, currency: string = "KES"): string | null {
  if (minor === null || minor === undefined) return null;
  if (minor === 0) return "Free";
  return `${currency} ${(minor / 100).toLocaleString()}`;
}

function countdownLabel(startTime: string): string | null {
  const d = new Date(startTime);
  if (isNaN(d.getTime())) return null;
  const diff = d.getTime() - Date.now();
  if (diff < 0) return "Happening now";
  const hours = diff / 3600000;
  if (hours < 1) return "Starting soon";
  if (hours < 24) return `In ${Math.round(hours)}h`;
  if (hours < 48) return "Tomorrow";
  return null;
}

export function FeedEventCard({ item, onSaveToCalendar }: Props) {
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

  const priceLabel = formatPrice(item.price_minor_units);
  const countLabel = countdownLabel(item.start_time);

  return (
    <View style={[styles.container, { backgroundColor: colors.bg }]}>
      {item.poster_image_uri ? (
        <Image source={{ uri: item.poster_image_uri }} style={styles.poster} resizeMode="cover" />
      ) : (
        <View style={[styles.poster, { backgroundColor: colors.surface1 }]} />
      )}

      <View style={styles.overlay} />

      <View style={styles.topRight}>
        {priceLabel ? (
          <View style={[styles.pill, priceLabel === "Free" ? styles.freePill : styles.pricePill]}>
            <AppText style={styles.pillText}>{priceLabel}</AppText>
          </View>
        ) : null}
        {onSaveToCalendar ? (
          <Pressable
            style={({ pressed }) => [styles.saveBtn, pressedOpacityStyle(pressed)]}
            onPress={() => onSaveToCalendar(item)}
          >
            <AppText style={styles.saveBtnText}>+ Save</AppText>
          </Pressable>
        ) : null}
      </View>

      <View style={styles.content}>
        <View style={styles.badgeRow}>
          <View style={styles.badge}>
            <AppText style={styles.badgeText}>{dateStr}</AppText>
          </View>
          {countLabel ? (
            <View style={styles.countdownBadge}>
              <AppText style={styles.countdownText}>{countLabel}</AppText>
            </View>
          ) : null}
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
                  viewMode: "viewer",
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
  topRight: {
    position: "absolute",
    top: 60,
    right: 16,
    gap: 8,
    alignItems: "flex-end",
  },
  pill: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
  },
  pricePill: {
    backgroundColor: "#4CAF50",
  },
  freePill: {
    backgroundColor: "#FF9800",
  },
  pillText: {
    color: "#fff",
    fontSize: 13,
    fontWeight: "800",
  },
  saveBtn: {
    backgroundColor: "rgba(0,0,0,0.5)",
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.3)",
  },
  saveBtnText: {
    color: "#fff",
    fontSize: 13,
    fontWeight: "700",
  },
  content: {
    position: "absolute",
    bottom: 120,
    left: 16,
    right: 16,
    gap: 8,
  },
  badgeRow: {
    flexDirection: "row",
    gap: 8,
    alignItems: "center",
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
  countdownBadge: {
    alignSelf: "flex-start",
    backgroundColor: "#FF6B35",
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  countdownText: {
    color: "#fff",
    fontSize: 13,
    fontWeight: "700",
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
