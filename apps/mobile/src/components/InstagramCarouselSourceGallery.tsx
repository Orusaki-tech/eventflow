import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
  useWindowDimensions,
  Image,
  View,
} from "react-native";
import {
  EventflowApiError,
  postInstagramCarouselPreview,
  type InstagramCarouselPreviewSlide,
} from "../api/eventflow";
import { CarouselDots } from "../design/components";
import { tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";
import {
  getInstagramSlideIndexFromUrl,
  instagramPostUrlForCarouselPreview,
  isInstagramPostUrl,
} from "../lib/normalizeSharePayload";
import { buildResolvedImageUri } from "../lib/thumbnail";

const ITEM_GAP = tokens.spacing[12];

type Props = {
  apiBaseUrl: string;
  accessToken: string | null;
  sharedUrl: string;
  height?: number;
  /** Horizontal padding used by parent ScrollView (each side). Used to size slides edge-to-edge inside padded content. */
  contentPadding?: number;
  /**
   * When the post has multiple slides, call once with the short-lived image token for the slide
   * indicated by `img_index` / `carousel_index` on `sharedUrl` (slide 1 if absent).
   */
  onPosterSlideTokenReady?: (imageToken: string) => void;
  /** True once preview returns more than one slide. */
  onMultiSlideChange?: (isMulti: boolean) => void;
  renderFallback: () => React.ReactElement;
  refreshSession?: () => Promise<void>;
};

export function InstagramCarouselSourceGallery({
  apiBaseUrl,
  accessToken,
  sharedUrl,
  height = 200,
  contentPadding = tokens.spacing[20],
  onPosterSlideTokenReady,
  onMultiSlideChange,
  renderFallback,
  refreshSession,
}: Props) {
  const { width: windowWidth } = useWindowDimensions();
  const { colors } = useTheme();
  const listRef = useRef<FlatList<InstagramCarouselPreviewSlide>>(null);
  const firedPosterToken = useRef(false);
  const posterCbRef = useRef(onPosterSlideTokenReady);
  const multiCbRef = useRef(onMultiSlideChange);
  posterCbRef.current = onPosterSlideTokenReady;
  multiCbRef.current = onMultiSlideChange;
  const styles = useThemedStyles((c) => ({
    wrap: { width: "100%" as const },
    slideOuter: {
      borderRadius: 16,
      overflow: "hidden" as const,
      borderWidth: 1,
      borderColor: c.border,
      backgroundColor: c.bg,
    },
    slideImg: { width: "100%" as const, height: "100%" as const, backgroundColor: c.bg },
    loadingBox: {
      width: "100%" as const,
      height,
      borderRadius: 16,
      borderWidth: 1,
      borderColor: c.border,
      alignItems: "center" as const,
      justifyContent: "center" as const,
      backgroundColor: c.surface1,
    },
  }));

  const [slides, setSlides] = useState<InstagramCarouselPreviewSlide[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [scrollIdx, setScrollIdx] = useState(0);

  const slideWidth = Math.max(120, windowWidth - contentPadding * 2);
  const stride = slideWidth + ITEM_GAP;

  useEffect(() => {
    firedPosterToken.current = false;
    if (!isInstagramPostUrl(sharedUrl)) {
      setSlides(null);
      setLoading(false);
      multiCbRef.current?.(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setSlides(null);
    multiCbRef.current?.(false);

    void (async () => {
      try {
        const previewUrl = instagramPostUrlForCarouselPreview(sharedUrl);
        const res = await postInstagramCarouselPreview(apiBaseUrl, accessToken, previewUrl);
        if (cancelled) return;
        const list = res.slides ?? [];
        setSlides(list);
        const multi = list.length > 1;
        multiCbRef.current?.(multi);
        const posterCb = posterCbRef.current;
        // Always parse from carousel preview bytes when available — single-slide posts used to fall back to
        // LinkThumbnail (yt-dlp/OG), which often differs from the embed CDN image used for multi-slide carousels.
        if (posterCb && list.length > 0) {
          const want = getInstagramSlideIndexFromUrl(sharedUrl);
          const pick = list.find((s) => s.slide_index === want) ?? list[0];
          if (pick?.image_token) {
            firedPosterToken.current = true;
            posterCb(pick.image_token);
          }
        }
      } catch (e: unknown) {
        if (cancelled) return;
        setSlides([]);
        multiCbRef.current?.(false);
        if (e instanceof EventflowApiError && e.status === 401) {
          await refreshSession?.().catch(() => undefined);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, accessToken, sharedUrl, refreshSession]);

  useEffect(() => {
    if (!slides || slides.length <= 1) return;
    const want = getInstagramSlideIndexFromUrl(sharedUrl);
    const idx = slides.findIndex((s) => s.slide_index === want);
    const i = idx >= 0 ? idx : 0;
    setScrollIdx(i);
    const t = setTimeout(() => {
      try {
        listRef.current?.scrollToIndex({ index: i, animated: false, viewPosition: 0 });
      } catch {
        listRef.current?.scrollToOffset({ offset: i * stride, animated: false });
      }
    }, 0);
    return () => clearTimeout(t);
  }, [slides, sharedUrl, stride]);

  const onMomentumScrollEnd = useCallback(
    (e: NativeSyntheticEvent<NativeScrollEvent>) => {
      const x = e.nativeEvent.contentOffset.x;
      const idx = Math.min(slides?.length ? slides.length - 1 : 0, Math.max(0, Math.round(x / stride)));
      setScrollIdx(idx);
    },
    [slides?.length, stride]
  );

  if (!isInstagramPostUrl(sharedUrl)) {
    return renderFallback();
  }

  if (loading) {
    return (
      <View style={styles.loadingBox}>
        <ActivityIndicator color={colors.textSecondary} />
      </View>
    );
  }

  if (!slides || slides.length === 0) {
    return renderFallback();
  }

  if (slides.length === 1) {
    const want = getInstagramSlideIndexFromUrl(sharedUrl);
    const pick = slides.find((s) => s.slide_index === want) ?? slides[0];
    return (
      <View style={styles.wrap}>
        <View style={{ width: slideWidth }}>
          <View style={[styles.slideOuter, { height }]}>
            <Image
              source={{ uri: buildResolvedImageUri(apiBaseUrl, pick.image_token) }}
              style={styles.slideImg}
              resizeMode="contain"
              accessibilityLabel={`Instagram slide ${pick.slide_index}`}
            />
          </View>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.wrap}>
      <FlatList
        ref={listRef}
        horizontal
        showsHorizontalScrollIndicator={false}
        data={slides}
        keyExtractor={(s) => String(s.slide_index)}
        snapToInterval={stride}
        snapToAlignment="start"
        decelerationRate="fast"
        disableIntervalMomentum
        onMomentumScrollEnd={onMomentumScrollEnd}
        onScrollToIndexFailed={(info) => {
          listRef.current?.scrollToOffset({ offset: info.index * stride, animated: false });
        }}
        getItemLayout={(_, index) => ({
          length: stride,
          offset: stride * index,
          index,
        })}
        contentContainerStyle={{ paddingRight: ITEM_GAP }}
        renderItem={({ item }) => (
          <View style={{ width: slideWidth, marginRight: ITEM_GAP }}>
            <View style={[styles.slideOuter, { height }]}>
              <Image
                source={{ uri: buildResolvedImageUri(apiBaseUrl, item.image_token) }}
                style={styles.slideImg}
                resizeMode="contain"
                accessibilityLabel={`Carousel slide ${item.slide_index}`}
              />
            </View>
          </View>
        )}
      />
      <CarouselDots count={slides.length} activeIndex={scrollIdx} />
    </View>
  );
}
