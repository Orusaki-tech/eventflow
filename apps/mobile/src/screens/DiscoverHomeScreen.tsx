import React, { useCallback, useRef, useState } from "react";
import {
  ActivityIndicator,
  Dimensions,
  FlatList,
  RefreshControl,
  StyleSheet,
  View,
  type ViewToken,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { getUnifiedFeed, logFeedWatch, getWatchQuota, type UnifiedFeedItem } from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { AppText, Button } from "../design/components";
import { tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { FeedVideoCard } from "../components/FeedVideoCard";
import { FeedEventCard } from "../components/FeedEventCard";
import { FeedAffiliateCard } from "../components/FeedAffiliateCard";

const { height: SCREEN_HEIGHT } = Dimensions.get("window");

export function DiscoverHomeScreen() {
  const { colors } = useTheme();
  const { accessToken, apiBaseUrl, refreshSession } = useAuth();
  const [items, setItems] = useState<UnifiedFeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [quota, setQuota] = useState<{
    is_premium: boolean;
    videos_watched_today: number;
    videos_remaining: number;
    daily_limit: number;
  } | null>(null);
  const activeIndexRef = useRef(0);
  const flatListRef = useRef<FlatList>(null);

  const loadQuota = useCallback(async () => {
    if (!accessToken) return;
    try {
      const q = await getWatchQuota(apiBaseUrl, accessToken);
      setQuota(q);
    } catch {
      // quota unavailable — skip overlay
    }
  }, [apiBaseUrl, accessToken]);

  const load = useCallback(async () => {
    try {
      const feed = await getUnifiedFeed(apiBaseUrl, accessToken, { limit: 50 });
      setItems(feed);
    } catch (e: unknown) {
      if (e instanceof Error && "status" in e && (e as { status: number }).status === 401) {
        await refreshSession().catch(() => undefined);
      }
      setItems([]);
    }
  }, [apiBaseUrl, accessToken, refreshSession]);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      void (async () => {
        setLoading(true);
        await Promise.all([load(), loadQuota()]);
        if (!cancelled) setLoading(false);
      })();
      return () => { cancelled = true; };
    }, [load, loadQuota])
  );

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    void (async () => {
      await Promise.all([load(), loadQuota()]);
      setRefreshing(false);
    })();
  }, [load, loadQuota]);

  const handleViewableItemsChanged = useCallback(
    ({ viewableItems }: { viewableItems: ViewToken[] }) => {
      if (viewableItems.length > 0) {
        const idx = viewableItems[0].index ?? 0;
        activeIndexRef.current = idx;
      }
    },
    []
  );

  const handleWatch = useCallback(
    async (itemId: string) => {
      if (!accessToken) return;
      try {
        await logFeedWatch(apiBaseUrl, accessToken, itemId);
        loadQuota();
      } catch {
        // silently fail; watch is best-effort
      }
    },
    [apiBaseUrl, accessToken, loadQuota]
  );

  const viewabilityConfig = useRef({
    itemVisiblePercentThreshold: 50,
  }).current;

  const isQuotaExhausted =
    quota && !quota.is_premium && quota.videos_remaining <= 0;

  const renderItem = useCallback(
    ({ item, index }: { item: UnifiedFeedItem; index: number }) => {
      const isActive = index === activeIndexRef.current;
      switch (item.kind) {
        case "video":
          return (
            <FeedVideoCard
              item={item}
              isActive={isActive}
              onWatch={handleWatch}
            />
          );
        case "event":
          return <FeedEventCard item={item} />;
        case "affiliate":
          return <FeedAffiliateCard item={item} />;
        default:
          return null;
      }
    },
    [handleWatch]
  );

  if (loading && !refreshing && items.length === 0) {
    return (
      <View style={[styles.center, { backgroundColor: colors.bg }]}>
        <ActivityIndicator color={colors.textSecondary} size="large" />
      </View>
    );
  }

  return (
    <View style={[styles.root, { backgroundColor: colors.bg }]}>
      <FlatList
        ref={flatListRef}
        data={items}
        keyExtractor={(item) => item.item_id}
        renderItem={renderItem}
        pagingEnabled
        showsVerticalScrollIndicator={false}
        snapToAlignment="start"
        snapToInterval={SCREEN_HEIGHT}
        decelerationRate="fast"
        onViewableItemsChanged={handleViewableItemsChanged}
        viewabilityConfig={viewabilityConfig}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={colors.textSecondary}
          />
        }
        removeClippedSubviews
        maxToRenderPerBatch={3}
        windowSize={3}
      />

      {/* Quota enforcement overlay */}
      {isQuotaExhausted && (
        <View style={[styles.overlay, { backgroundColor: "rgba(0,0,0,0.85)" }]}>
          <AppText style={styles.overlayTitle}>Daily limit reached</AppText>
          <AppText style={styles.overlaySub}>
            You've watched all {quota!.daily_limit} free videos today.
            {"\n"}Subscribe for unlimited access or come back tomorrow.
          </AppText>
          <Button
            label="Subscribe"
            variant="filled"
            size="md"
            onPress={() => {
              // Navigate to subscription screen in future
            }}
          />
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: "center",
    alignItems: "center",
    padding: 32,
    gap: 16,
  },
  overlayTitle: {
    fontSize: 24,
    fontWeight: "900",
    color: "#fff",
    textAlign: "center",
  },
  overlaySub: {
    fontSize: 16,
    color: "rgba(255,255,255,0.7)",
    textAlign: "center",
    lineHeight: 22,
  },
});
