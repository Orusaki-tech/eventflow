import React, { useCallback, useState } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { getUnifiedFeed, getWatchQuota, type UnifiedFeedItem } from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { AppText, Button } from "../design/components";
import { tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { SectionalFeed } from "../components/SectionalFeed";
import type { RootStackParamList } from "../navigation/types";

function GreetingHeader() {
  const { colors } = useTheme();
  const hour = new Date().getHours();
  let greeting = "Good evening";
  if (hour < 12) greeting = "Good morning";
  else if (hour < 17) greeting = "Good afternoon";

  return (
    <View style={styles.header}>
      <AppText variant="display" style={{ color: colors.textPrimary }}>
        {greeting}
      </AppText>
      <AppText tone="secondary" style={styles.subhead}>
        Discover events, videos, and offers
      </AppText>
    </View>
  );
}

export function DiscoverHomeScreen() {
  const { colors } = useTheme();
  const { accessToken, apiBaseUrl, refreshSession } = useAuth();
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const [items, setItems] = useState<UnifiedFeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [quota, setQuota] = useState<{
    is_premium: boolean;
    videos_watched_today: number;
    videos_remaining: number;
    daily_limit: number;
  } | null>(null);

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

  const isQuotaExhausted =
    quota && !quota.is_premium && quota.videos_remaining <= 0;

  if (loading && !refreshing && items.length === 0) {
    return (
      <View style={[styles.center, { backgroundColor: colors.bg }]}>
        <ActivityIndicator color={colors.textSecondary} size="large" />
      </View>
    );
  }

  return (
    <View style={[styles.root, { backgroundColor: colors.bg }]}>
      <SectionalFeed
        items={items}
        refreshing={refreshing}
        onRefresh={onRefresh}
        ListHeaderComponent={<GreetingHeader />}
      />

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
            onPress={() => navigation.navigate("Subscription", undefined)}
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
  header: {
    paddingHorizontal: tokens.spacing[16],
    paddingTop: tokens.spacing[8],
    gap: 4,
  },
  subhead: {
    fontSize: 15,
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
