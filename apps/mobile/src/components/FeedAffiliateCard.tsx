import React from "react";
import {
  Dimensions,
  Image,
  Linking,
  Pressable,
  StyleSheet,
  View,
} from "react-native";
import type { UnifiedFeedAffiliate } from "../api/eventflow";
import { AppText } from "../design/components";
import { pressedOpacityStyle, tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { navigationRef } from "../navigation/navigationRef";

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get("window");

type Props = {
  item: UnifiedFeedAffiliate;
};

export function FeedAffiliateCard({ item }: Props) {
  const { colors } = useTheme();
  const price = item.price_minor_units
    ? `$${(item.price_minor_units / 100).toFixed(2)}`
    : null;

  return (
    <View style={[styles.container, { backgroundColor: colors.bg }]}>
      {/* Product image */}
      {item.image_uri ? (
        <Image source={{ uri: item.image_uri }} style={styles.image} resizeMode="cover" />
      ) : (
        <View style={[styles.image, { backgroundColor: colors.surface1 }]} />
      )}

      {/* Overlay */}
      <View style={styles.overlay} />

      {/* Content */}
      <View style={styles.content}>
        <View style={styles.badge}>
          <AppText style={styles.badgeText}>Affiliate Offer</AppText>
        </View>

        <AppText style={styles.title} numberOfLines={2}>
          {item.title}
        </AppText>

        {item.description ? (
          <AppText style={styles.description} numberOfLines={2}>
            {item.description}
          </AppText>
        ) : null}

        {price ? <AppText style={styles.price}>{price}</AppText> : null}

        <AppText style={styles.seller}>
          by {item.seller_name ?? "Unknown seller"}
        </AppText>

        {item.event_title ? (
          <Pressable
            onPress={() => {
              if (navigationRef.isReady()) {
                navigationRef.navigate("CommunityListingDetail", {
                  communityEventId: item.community_event_id,
                  organizerUserId: "",
                  title: item.event_title!,
                  start_time: "",
                  venue: "",
                  whatsapp_e164: null,
                  business_id: item.seller_business_id,
                  viewMode: "viewer",
                });
              }
            }}
          >
            <AppText style={styles.eventLink}>
              From event: {item.event_title}
            </AppText>
          </Pressable>
        ) : null}

        {item.whatsapp_e164 ? (
          <Pressable
            style={({ pressed }) => [styles.whatsappBtn, pressedOpacityStyle(pressed)]}
            onPress={() => {
              const url = `https://wa.me/${item.whatsapp_e164?.replace(/^\+/, "")}`;
              Linking.openURL(url);
            }}
          >
            <AppText style={styles.whatsappText}>Inquire on WhatsApp</AppText>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: SCREEN_WIDTH,
    height: SCREEN_HEIGHT,
  },
  image: {
    ...StyleSheet.absoluteFillObject,
  },
  overlay: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    height: "55%",
    backgroundColor: "rgba(0,0,0,0.45)",
  },
  content: {
    position: "absolute",
    bottom: 120,
    left: 16,
    right: 16,
    gap: 6,
  },
  badge: {
    alignSelf: "flex-start",
    backgroundColor: "#FF6B35",
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  badgeText: {
    color: "#fff",
    fontSize: 12,
    fontWeight: "700",
  },
  title: {
    fontSize: 22,
    fontWeight: "900",
    color: "#fff",
    textShadowColor: "rgba(0,0,0,0.6)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 3,
  },
  description: {
    fontSize: 14,
    color: "rgba(255,255,255,0.85)",
    textShadowColor: "rgba(0,0,0,0.4)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 2,
  },
  price: {
    fontSize: 20,
    fontWeight: "800",
    color: "#4CAF50",
    textShadowColor: "rgba(0,0,0,0.4)",
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 2,
  },
  seller: {
    fontSize: 13,
    color: "rgba(255,255,255,0.6)",
  },
  eventLink: {
    fontSize: 13,
    color: "#81C784",
    textDecorationLine: "underline",
  },
  whatsappBtn: {
    alignSelf: "flex-start",
    backgroundColor: "#25D366",
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 24,
    marginTop: 4,
  },
  whatsappText: {
    color: "#fff",
    fontWeight: "700",
    fontSize: 14,
  },
});
