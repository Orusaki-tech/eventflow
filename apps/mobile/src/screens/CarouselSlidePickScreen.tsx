import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Dimensions,
  FlatList,
  Image,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
  Pressable,
  View,
} from "react-native";
import {
  EventflowApiError,
  postInstagramCarouselPreview,
  type InstagramCarouselPreviewSlide,
} from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { AppText, Button, CarouselDots } from "../design/components";
import { pressedOpacityStyle, tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";
import { CAROUSEL_SIDE_PAD, carouselPickMetrics, scrollXToActiveIndex } from "../lib/carouselSlidePickLayout";
import { buildResolvedImageUri } from "../lib/thumbnail";
import type { RootStackParamList } from "../navigation/types";

type Props = NativeStackScreenProps<RootStackParamList, "CarouselSlidePick">;

export function CarouselSlidePickScreen({ navigation, route }: Props) {
  const { colors } = useTheme();
  const { apiBaseUrl, accessToken, refreshSession } = useAuth();
  const { rawText, instagramUrl } = route.params;

  const metrics = useMemo(() => carouselPickMetrics(Dimensions.get("window").width), []);

  const styles = useThemedStyles((c) => ({
    root: { flex: 1, backgroundColor: c.bg },
    scrollPad: {
      paddingHorizontal: CAROUSEL_SIDE_PAD,
      paddingBottom: tokens.spacing[20],
      gap: tokens.spacing[12],
      flexGrow: 1,
    },
    lead: { lineHeight: 22 },
    center: { paddingVertical: 32, alignItems: "center" as const, gap: 12 },
    slideWrap: {
      width: metrics.cardWidth,
      height: metrics.cardHeight,
      borderRadius: tokens.radii.md,
      overflow: "hidden" as const,
      borderWidth: 3,
      backgroundColor: c.surface1,
    },
    slideImg: { width: "100%", height: "100%" },
    badge: {
      position: "absolute" as const,
      top: 10,
      right: 10,
      minWidth: 28,
      height: 28,
      borderRadius: 14,
      paddingHorizontal: 8,
      alignItems: "center" as const,
      justifyContent: "center" as const,
      backgroundColor: c.textPrimary,
    },
    badgeText: { color: c.bg, fontSize: 13, fontWeight: "600" as const },
    meta: { lineHeight: 20 },
    actions: { gap: tokens.spacing[12], paddingHorizontal: CAROUSEL_SIDE_PAD, paddingBottom: tokens.spacing[24] },
  }));

  const [slides, setSlides] = useState<InstagramCarouselPreviewSlide[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [scrollIdx, setScrollIdx] = useState(0);
  /** Sorted unique slide indices (max 2 when multi-slide). */
  const [selectedIndices, setSelectedIndices] = useState<number[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const res = await postInstagramCarouselPreview(apiBaseUrl, accessToken, instagramUrl);
      setSlides(res.slides);
      if (res.slides.length === 1) {
        setSelectedIndices([res.slides[0]!.slide_index]);
      } else {
        setSelectedIndices([]);
      }
    } catch (e: unknown) {
      if (e instanceof EventflowApiError && e.status === 401) {
        await refreshSession().catch(() => undefined);
      }
      const msg = e instanceof EventflowApiError ? e.message : e instanceof Error ? e.message : String(e);
      setFetchError(msg);
      setSlides([]);
      setSelectedIndices([]);
    } finally {
      setLoading(false);
    }
  }, [accessToken, apiBaseUrl, instagramUrl, refreshSession]);

  useEffect(() => {
    void load();
  }, [load]);

  const snapToOffsets = useMemo(
    () => slides.map((_, i) => i * metrics.stride),
    [slides, metrics.stride]
  );

  const getItemLayout = useCallback(
    (_data: ArrayLike<InstagramCarouselPreviewSlide> | null | undefined, index: number) => ({
      length: metrics.stride,
      offset: index * metrics.stride,
      index,
    }),
    [metrics.stride]
  );

  const toggleSlide = useCallback((slideIndex: number) => {
    setSelectedIndices((prev) => {
      const set = new Set(prev);
      if (set.has(slideIndex)) {
        set.delete(slideIndex);
        return Array.from(set).sort((a, b) => a - b);
      }
      if (set.size >= 2) return prev;
      set.add(slideIndex);
      return Array.from(set).sort((a, b) => a - b);
    });
  }, []);

  const selectionLabel =
    slides.length <= 1 ? "This post has one image." : `${selectedIndices.length} of 2 selected · swipe to browse`;

  const canContinue =
    slides.length === 0
      ? false
      : slides.length === 1
        ? selectedIndices.length === 1
        : selectedIndices.length === 2;

  const syncScrollIndex = useCallback(
    (x: number) => {
      const n = slides.length;
      if (n <= 1) return;
      setScrollIdx(scrollXToActiveIndex(x, n, metrics.stride));
    },
    [metrics.stride, slides.length]
  );

  const onScroll = useCallback(
    (e: NativeSyntheticEvent<NativeScrollEvent>) => {
      syncScrollIndex(e.nativeEvent.contentOffset.x);
    },
    [syncScrollIndex]
  );

  const onMomentumScrollEnd = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    syncScrollIndex(e.nativeEvent.contentOffset.x);
  };

  const renderItem = useCallback(
    ({ item }: { item: InstagramCarouselPreviewSlide }) => {
      const sel = selectedIndices.includes(item.slide_index);
      const uri = buildResolvedImageUri(apiBaseUrl, item.image_token);
      return (
        <View style={{ width: metrics.stride }}>
          <Pressable onPress={() => toggleSlide(item.slide_index)} style={({ pressed }) => pressedOpacityStyle(pressed)}>
            <View style={[styles.slideWrap, { borderColor: sel ? colors.textPrimary : colors.border }]}>
              <Image
                source={{ uri }}
                style={styles.slideImg}
                resizeMode="cover"
                accessibilityLabel={`Slide ${item.slide_index}`}
              />
              {sel ? (
                <View style={styles.badge} accessibilityLabel="Selected">
                  <AppText style={styles.badgeText}>✓</AppText>
                </View>
              ) : null}
              <View
                style={{
                  position: "absolute",
                  bottom: 10,
                  left: 10,
                  paddingHorizontal: 10,
                  paddingVertical: 4,
                  borderRadius: tokens.radii.sm,
                  backgroundColor: colors.overlay,
                }}
              >
                <AppText variant="labelSmall" style={{ color: colors.bg }}>
                  {item.slide_index}
                </AppText>
              </View>
            </View>
          </Pressable>
        </View>
      );
    },
    [apiBaseUrl, colors.bg, colors.border, colors.overlay, colors.textPrimary, metrics.stride, selectedIndices, styles, toggleSlide]
  );

  if (loading) {
    return (
      <View style={[styles.root, styles.center]}>
        <ActivityIndicator color={colors.textSecondary} />
        <AppText tone="secondary">Loading carousel…</AppText>
      </View>
    );
  }

  if (fetchError || slides.length === 0) {
    const redisHint =
      fetchError &&
      (/redis/i.test(fetchError) || /REDIS_URL/i.test(fetchError))
        ? "If the API runs on your machine without Redis, set ENV=local in the server env (or start Redis). Env dev/prod requires REDIS_URL."
        : null;
    return (
      <View style={[styles.root, styles.scrollPad]}>
        <AppText variant="title">Couldn't load carousel</AppText>
        <AppText tone="secondary" style={styles.lead}>
          {fetchError ?? "No slides returned."}
        </AppText>
        {redisHint ? (
          <AppText tone="tertiary" style={styles.meta}>
            {redisHint}
          </AppText>
        ) : null}
        <Button label="Try again" onPress={() => void load()} fullWidth />
        <Button
          label="Continue without slide picker"
          variant="outline"
          onPress={() => navigation.replace("Processing", { rawText })}
          fullWidth
        />
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <View style={{ paddingHorizontal: CAROUSEL_SIDE_PAD }}>
        <FlatList
          data={slides}
          keyExtractor={(s) => String(s.slide_index)}
          horizontal
          showsHorizontalScrollIndicator={false}
          snapToOffsets={snapToOffsets}
          snapToEnd={false}
          decelerationRate="fast"
          contentContainerStyle={{ paddingTop: tokens.spacing[16], paddingBottom: 8 }}
          getItemLayout={getItemLayout}
          initialNumToRender={Math.min(slides.length, 8)}
          maxToRenderPerBatch={6}
          windowSize={7}
          scrollEventThrottle={16}
          onScroll={onScroll}
          renderItem={renderItem}
          onMomentumScrollEnd={onMomentumScrollEnd}
        />
      </View>

      <CarouselDots count={slides.length} activeIndex={scrollIdx} />

      <View style={styles.scrollPad}>
        <AppText tone="secondary" style={styles.lead}>
          Tap two slides with the event details. We'll run Gemini on only those images.
        </AppText>
        <AppText tone="secondary" style={styles.meta}>
          {selectionLabel}
        </AppText>
      </View>

      <View style={styles.actions}>
        <Button
          label="Continue"
          disabled={!canContinue}
          onPress={() =>
            navigation.replace("Processing", {
              rawText,
              ...(slides.length >= 2 ? { carouselSlideIndices: selectedIndices } : {}),
            })
          }
          fullWidth
        />
      </View>
    </View>
  );
}
