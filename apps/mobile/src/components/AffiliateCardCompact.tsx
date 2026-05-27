import React from "react";
import { Image, Linking, Pressable, StyleSheet, View } from "react-native";
import type { UnifiedFeedAffiliate } from "../api/eventflow";
import { AppText } from "../design/components";
import { pressedOpacityStyle, tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { COMPACT_CARD_WIDTH } from "./EventCardCompact";

type Props = {
  item: UnifiedFeedAffiliate;
};

export function AffiliateCardCompact({ item }: Props) {
  const { colors } = useTheme();

  const price = item.price_minor_units
    ? `$${(item.price_minor_units / 100).toFixed(2)}`
    : null;

  return (
    <Pressable
      style={({ pressed }) => [styles.card, pressedOpacityStyle(pressed)]}
      onPress={() => {
        // Open WhatsApp inquiry directly
        if (item.whatsapp_e164) {
          const url = `https://wa.me/${item.whatsapp_e164.replace(/^\+/, "")}`;
          Linking.openURL(url);
        }
      }}
    >
      <View style={[styles.imageWrap, { backgroundColor: colors.surface1 }]}>
        {item.image_uri ? (
          <Image source={{ uri: item.image_uri }} style={styles.image} resizeMode="cover" />
        ) : null}
        {price ? (
          <View style={styles.priceBadge}>
            <AppText style={styles.priceText}>{price}</AppText>
          </View>
        ) : null}
      </View>

      <View style={styles.body}>
        <AppText numberOfLines={2} style={styles.title}>
          {item.title}
        </AppText>
        <AppText numberOfLines={1} style={styles.seller}>
          {item.seller_name ?? "Seller"}
        </AppText>
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
  priceBadge: {
    position: "absolute",
    bottom: 8,
    left: 8,
    backgroundColor: "#4CAF50",
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  priceText: {
    color: "#fff",
    fontSize: 12,
    fontWeight: "800",
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
  seller: {
    fontSize: 11,
    lineHeight: 14,
    color: "rgba(255,255,255,0.6)",
  },
});
