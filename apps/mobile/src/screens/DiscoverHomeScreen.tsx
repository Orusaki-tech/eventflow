import React, { useCallback, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Image,
  Linking,
  Pressable,
  RefreshControl,
  View,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import {
  EventflowApiError,
  getDiscoveryFeed,
  getFeedHome,
  postListingAnalytics,
} from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { AppText, Button, Card } from "../design/components";
import { pressedOpacityStyle, tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";
import { formatFriendlyEventDateTime } from "../lib/eventDateTime";
import { mergeDiscoverSources, type DiscoverMergedRow } from "../lib/mergeDiscoverFeed";
import { whatsAppMeUrlFromE164 } from "../lib/whatsappLink";
import { navigationRef } from "../navigation/navigationRef";

export function DiscoverHomeScreen() {
  const { colors } = useTheme();
  const styles = useThemedStyles((c) => ({
    root: { flex: 1, backgroundColor: c.bg },
    center: { flex: 1, paddingVertical: 32, alignItems: "center" as const, justifyContent: "center" as const },
    listContent: { padding: tokens.spacing[16], gap: tokens.spacing[12], flexGrow: 1 },
    empty: { paddingVertical: 24 },
    card: { padding: tokens.spacing[16], gap: tokens.spacing[8] },
    meta: {},
    venue: {},
    hero: {
      width: "100%" as const,
      height: 160,
      borderRadius: tokens.radii.sm,
      marginBottom: tokens.spacing[8],
      backgroundColor: c.surface1,
    },
  }));

  const { accessToken, apiBaseUrl, refreshSession } = useAuth();
  const [items, setItems] = useState<DiscoverMergedRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const publicFeed = await getDiscoveryFeed(apiBaseUrl, null, { limit: 50 });
      let personalized: Awaited<ReturnType<typeof getFeedHome>> = [];
      if (accessToken) {
        try {
          personalized = await getFeedHome(apiBaseUrl, accessToken, { limit: 50 });
        } catch (e: unknown) {
          if (e instanceof EventflowApiError && e.status === 401) await refreshSession().catch(() => undefined);
          personalized = [];
        }
      }
      setItems(mergeDiscoverSources(personalized, publicFeed));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setItems([]);
    }
  }, [accessToken, apiBaseUrl, refreshSession]);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      void (async () => {
        setLoading(true);
        await load();
        if (!cancelled) setLoading(false);
      })();
      return () => {
        cancelled = true;
      };
    }, [load])
  );

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    void (async () => {
      await load();
      setRefreshing(false);
    })();
  }, [load]);

  const openListing = (row: DiscoverMergedRow) => {
    if (!navigationRef.isReady()) return;
    navigationRef.navigate("CommunityListingDetail", {
      communityEventId: row.communityEventId,
      organizerUserId: row.organizerUserId,
      title: row.title,
      start_time: row.start_time,
      venue: row.venue,
      whatsapp_e164: row.whatsapp_e164 ?? null,
      business_id: row.business_id ?? null,
    });
  };

  const openListingWhatsApp = (row: DiscoverMergedRow) => {
    const raw = row.whatsapp_e164?.trim();
    if (!raw) return;
    const url = whatsAppMeUrlFromE164(raw);
    if (!url) return;
    void (async () => {
      try {
        if (accessToken) {
          await postListingAnalytics(apiBaseUrl, accessToken, {
            metric_type: "whatsapp_tap",
            community_event_id: row.communityEventId,
            business_id: row.business_id ?? null,
          });
        }
      } catch (e: unknown) {
        if (e instanceof EventflowApiError && e.status === 401) await refreshSession().catch(() => undefined);
      }
      const ok = await Linking.canOpenURL(url);
      if (ok) await Linking.openURL(url);
    })();
  };

  if (loading && !refreshing) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.textSecondary} />
      </View>
    );
  }

  return (
    <FlatList
      style={styles.root}
      contentContainerStyle={styles.listContent}
      data={items}
      keyExtractor={(item) => item.communityEventId}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      ListEmptyComponent={
        error ? (
          <AppText tone="secondary" style={styles.empty}>
            {error}
          </AppText>
        ) : (
          <AppText tone="tertiary" style={styles.empty}>
            No community listings yet. Try again after events are published to discovery.
          </AppText>
        )
      }
      renderItem={({ item }) => {
        const poster = item.poster_image_uri?.trim();
        const promoVideo = item.hero_video_uri?.trim();
        const waUrl = item.whatsapp_e164?.trim() ? whatsAppMeUrlFromE164(item.whatsapp_e164.trim()) : null;
        return (
          <Card style={styles.card}>
            <Pressable accessibilityLabel="View listing details" style={({ pressed }) => [pressedOpacityStyle(pressed)]} onPress={() => openListing(item)}>
              <View>
                {poster ? (
                  <Image source={{ uri: poster }} style={styles.hero} resizeMode="cover" />
                ) : promoVideo ? (
                  <View style={[styles.hero, { justifyContent: "center", alignItems: "center" }]}>
                    <AppText variant="labelSmall" tone="tertiary">
                      Video promo
                    </AppText>
                  </View>
                ) : null}
                <AppText variant="title">{item.title}</AppText>
                <AppText tone="secondary" style={styles.meta}>
                  {formatFriendlyEventDateTime(item.start_time)}
                </AppText>
                <AppText tone="secondary" style={styles.venue}>
                  {item.venue}
                </AppText>
                {item.organizerUserId ? (
                  <AppText variant="labelSmall" tone="tertiary">
                    From someone you follow or trending
                  </AppText>
                ) : (
                  <AppText variant="labelSmall" tone="tertiary">
                    Discovery
                  </AppText>
                )}
              </View>
            </Pressable>
            {promoVideo ? (
              <Button
                label="Open video promo"
                variant="outline"
                size="md"
                onPress={() => void Linking.openURL(promoVideo)}
                fullWidth
              />
            ) : null}
            {waUrl ? (
              <Button
                label="Chat on WhatsApp"
                variant="filled"
                size="md"
                onPress={() => openListingWhatsApp(item)}
                fullWidth
              />
            ) : null}
          </Card>
        );
      }}
    />
  );
}
