import React, { useState } from "react";
import { ActivityIndicator, Image, StyleSheet, Text, View } from "react-native";
import { buildPosterAssetUri } from "../lib/thumbnail";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";

type Props = {
  apiBaseUrl: string;
  posterAssetId: string;
  height?: number;
};

export function PosterAssetImage({ apiBaseUrl, posterAssetId, height = 180 }: Props) {
  const { colors } = useTheme();
  const styles = useThemedStyles((c) => ({
    wrap: {
      width: "100%",
      borderRadius: 16,
      overflow: "hidden",
      borderWidth: 1,
      borderColor: c.border,
      backgroundColor: c.bg,
    },
    img: { width: "100%", height: "100%", backgroundColor: c.bg },
    loading: {
      ...StyleSheet.absoluteFillObject,
      alignItems: "center" as const,
      justifyContent: "center" as const,
      backgroundColor: c.overlay,
    },
    placeholder: {
      width: "100%",
      borderRadius: 16,
      borderWidth: 1,
      borderColor: c.border,
      backgroundColor: c.bg,
      alignItems: "center" as const,
      justifyContent: "center" as const,
      paddingHorizontal: 16,
      gap: 6,
    },
    placeholderTitle: { color: c.textPrimary, fontWeight: "800", fontSize: 16 },
    placeholderBody: { color: c.textSecondary, textAlign: "center" as const, lineHeight: 20, fontSize: 13 },
  }));
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);

  const uri = buildPosterAssetUri(apiBaseUrl, posterAssetId);

  if (failed) {
    return (
      <View style={[styles.placeholder, { height }]}>
        <Text style={styles.placeholderTitle}>No poster</Text>
        <Text style={styles.placeholderBody}>We could not load the poster image.</Text>
      </View>
    );
  }

  return (
    <View style={[styles.wrap, { height }]}>
      <Image
        source={{ uri }}
        style={styles.img}
        resizeMode="contain"
        onLoadStart={() => setLoading(true)}
        onLoadEnd={() => setLoading(false)}
        onError={() => setFailed(true)}
      />
      {loading ? (
        <View style={styles.loading}>
          <ActivityIndicator color={colors.textSecondary} />
        </View>
      ) : null}
    </View>
  );
}

