import React, { useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Image, StyleSheet, Text, View } from "react-native";
import { buildResolvedImageUri, buildThumbnailUri } from "../lib/thumbnail";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";

type Props = {
  apiBaseUrl: string;
  sharedUrl: string;
  height?: number;
  onImageTokenReady?: (imageToken: string) => void;
  /** Rendered inside the bordered placeholder when the link thumbnail fails to load. */
  placeholderAccessory?: React.ReactNode;
  /** Rendered below the preview once an image has loaded successfully (e.g. add screenshot). */
  successAccessory?: React.ReactNode;
};

export function LinkThumbnail({
  apiBaseUrl,
  sharedUrl,
  height = 180,
  onImageTokenReady,
  placeholderAccessory,
  successAccessory,
}: Props) {
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
    placeholderAccessory: { alignSelf: "stretch" as const, marginTop: 8 },
    successAccessory: { marginTop: 10 },
  }));
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showSuccessAccessory, setShowSuccessAccessory] = useState(false);
  const [imageToken, setImageToken] = useState<string | null>(null);
  const firedTokenCb = useRef(false);

  const fallbackUri = useMemo(() => buildThumbnailUri(apiBaseUrl, sharedUrl), [apiBaseUrl, sharedUrl]);
  const resolvedUri = useMemo(
    () => (imageToken ? buildResolvedImageUri(apiBaseUrl, imageToken) : null),
    [apiBaseUrl, imageToken]
  );
  const uri = resolvedUri ?? fallbackUri;

  useEffect(() => {
    let cancelled = false;
    firedTokenCb.current = false;
    setImageToken(null);
    setFailed(false);
    setLoading(true);
    setShowSuccessAccessory(false);
    void (async () => {
      try {
        const base = apiBaseUrl.replace(/\/$/, "");
        const res = await fetch(`${base}/api/v1/media/resolve-image`, {
          method: "POST",
          headers: { Accept: "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ url: sharedUrl }),
        });
        if (!res.ok) return;
        const j = (await res.json()) as { image_token?: string };
        if (!cancelled && j.image_token) setImageToken(j.image_token);
      } catch {
        // best-effort; fallback to old thumbnail endpoint
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, sharedUrl]);

  if (failed) {
    return (
      <View style={[styles.placeholder, { height }]}>
        <Text style={styles.placeholderTitle}>No preview</Text>
        <Text style={styles.placeholderBody}>This link does not provide a public thumbnail.</Text>
        {placeholderAccessory ? <View style={styles.placeholderAccessory}>{placeholderAccessory}</View> : null}
      </View>
    );
  }

  return (
    <>
      <View style={[styles.wrap, { height }]}>
        <Image
          source={{ uri }}
          style={styles.img}
          // Always show the full image (no cropping).
          // This may letterbox when aspect ratios differ.
          resizeMode="contain"
          onLoadStart={() => setLoading(true)}
          onLoadEnd={() => {
            setLoading(false);
            setShowSuccessAccessory(true);
            if (imageToken && onImageTokenReady && !firedTokenCb.current) {
              firedTokenCb.current = true;
              onImageTokenReady(imageToken);
            }
          }}
          onError={() => {
            if (__DEV__) {
              // eslint-disable-next-line no-console
              console.log("thumbnail_load_failed", { sharedUrl, uri });
            }
            setShowSuccessAccessory(false);
            setFailed(true);
          }}
        />
        {loading ? (
          <View style={styles.loading}>
            <ActivityIndicator color={colors.textSecondary} />
          </View>
        ) : null}
      </View>
      {successAccessory && showSuccessAccessory && !loading ? (
        <View style={styles.successAccessory}>{successAccessory}</View>
      ) : null}
    </>
  );
}

