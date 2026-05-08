import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  NativeScrollEvent,
  NativeSyntheticEvent,
  Pressable,
  ScrollView,
  View,
} from "react-native";
import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";
import { fetchEventIcs, listToday, listUpcoming, type TodayEventRow, type UpcomingEventRow, EventflowApiError } from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { LinkThumbnail } from "../components/LinkThumbnail";
import { PosterAssetImage } from "../components/PosterAssetImage";
import { UpcomingEventCard } from "../components/UpcomingEventCard";
import { getEventPosterAssetId } from "../lib/thumbnail";
import { dedupeByEventFingerprint } from "../lib/dedupeEvents";
import { formatFriendlyEventDateTime } from "../lib/eventDateTime";
import type { RootStackParamList } from "../navigation/types";
import { navigationRef } from "../navigation/navigationRef";
import { AppText, Button, Card, CarouselDots, CAROUSEL_EVENT_CARD_STRIDE, SectionHeader } from "../design/components";
import { tokens, pressedOpacityStyle } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";

type Props = NativeStackScreenProps<RootStackParamList, "Confirmed">;

function useConfirmedStyles() {
  return useThemedStyles((c) => ({
    root: { flex: 1, backgroundColor: c.bg },
    container: { padding: tokens.spacing[16], gap: tokens.spacing[16] },
    title: {},
    body: {},
    actionsRow: { flexDirection: "row" as const, gap: 10, flexWrap: "wrap" as const },
    heroCard: {
      padding: tokens.spacing[16],
      gap: tokens.spacing[8],
    },
    heroKicker: { letterSpacing: 0.2 },
    heroTitle: {},
    meta: {},
    venueText: {},
    empty: { paddingVertical: 6 },
    carousel: { paddingTop: 6, paddingBottom: 2 },
    carouselGap: { width: 10 },
    carouselItem: { width: 320 },
    footerBtn: { paddingVertical: 14 },
    footerLabel: { textAlign: "center" as const, fontWeight: "700" },
    center: { paddingVertical: 16, alignItems: "center" as const, justifyContent: "center" as const },
  }));
}

export function ConfirmedScreen({ navigation, route }: Props) {
  const { colors } = useTheme();
  const styles = useConfirmedStyles();
  const { eventId } = route.params;
  const sharedUrl = route.params.sharedUrl;
  const { accessToken, apiBaseUrl, refreshSession } = useAuth();
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [today, setToday] = useState<TodayEventRow[]>([]);
  const [upcoming, setUpcoming] = useState<UpcomingEventRow[]>([]);
  const [posterAssetId, setPosterAssetId] = useState<string | null>(null);
  const [todayCarouselIndex, setTodayCarouselIndex] = useState(0);
  const [upcomingCarouselIndex, setUpcomingCarouselIndex] = useState(0);

  const tzOffsetMinutes = useMemo(() => -new Date().getTimezoneOffset(), []);

  const shareIcs = async () => {
    if (!FileSystem.cacheDirectory) {
      Alert.alert("Unavailable", "Cache directory is not available on this device.");
      return;
    }
    setBusy(true);
    try {
      const ics = await fetchEventIcs(apiBaseUrl, accessToken, eventId);
      const path = `${FileSystem.cacheDirectory}eventflow-${eventId}.ics`;
      await FileSystem.writeAsStringAsync(path, ics, { encoding: "utf8" });
      const can = await Sharing.isAvailableAsync();
      if (!can) {
        Alert.alert("Sharing unavailable", "Open the event from the API or add to Google Calendar from the web.");
        return;
      }
      await Sharing.shareAsync(path, { mimeType: "text/calendar", dialogTitle: "Add to calendar" });
    } catch (e: unknown) {
      if (e instanceof EventflowApiError && e.status === 401) await refreshSession();
      Alert.alert("Export failed", e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      try {
        const [t, u] = await Promise.all([
          listToday(apiBaseUrl, accessToken, tzOffsetMinutes),
          listUpcoming(apiBaseUrl, accessToken, 30),
        ]);
        if (cancelled) return;
        setToday(t);
        setUpcoming(u);
      } catch (e: unknown) {
        if (e instanceof EventflowApiError && e.status === 401) await refreshSession().catch(() => undefined);
        if (!cancelled) {
          setToday([]);
          setUpcoming([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [accessToken, apiBaseUrl, refreshSession, tzOffsetMinutes]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const pid = await getEventPosterAssetId(eventId);
      if (!cancelled) setPosterAssetId(pid);
    })();
    return () => {
      cancelled = true;
    };
  }, [eventId]);

  const newlyScheduled =
    today.find((e) => e.id === eventId) ?? upcoming.find((e) => e.id === eventId) ?? null;

  const uniqueToday = useMemo(() => {
    return dedupeByEventFingerprint<TodayEventRow>(today);
  }, [today]);

  const uniqueUpcoming = useMemo(() => {
    return dedupeByEventFingerprint<UpcomingEventRow>(upcoming);
  }, [upcoming]);

  const confirmedTodayCarousel = useMemo(
    () => uniqueToday.filter((e) => e.id !== eventId),
    [uniqueToday, eventId]
  );
  const confirmedUpcomingCarousel = useMemo(
    () => uniqueUpcoming.filter((e) => e.id !== eventId),
    [uniqueUpcoming, eventId]
  );

  const onTodayCarouselScrollEnd = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const n = confirmedTodayCarousel.length;
    if (n <= 1) return;
    const x = e.nativeEvent.contentOffset.x;
    setTodayCarouselIndex(Math.min(Math.max(0, Math.round(x / CAROUSEL_EVENT_CARD_STRIDE)), n - 1));
  };

  const onUpcomingCarouselScrollEnd = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const n = confirmedUpcomingCarousel.length;
    if (n <= 1) return;
    const x = e.nativeEvent.contentOffset.x;
    setUpcomingCarouselIndex(Math.min(Math.max(0, Math.round(x / CAROUSEL_EVENT_CARD_STRIDE)), n - 1));
  };

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.container}>
      <AppText variant="headline" style={styles.title}>
        Scheduled
      </AppText>
      <AppText tone="secondary" style={styles.body}>
        This event is now on your EventFlow calendar.
      </AppText>
      {posterAssetId ? <PosterAssetImage apiBaseUrl={apiBaseUrl} posterAssetId={posterAssetId} height={220} /> : null}
      {sharedUrl ? <LinkThumbnail apiBaseUrl={apiBaseUrl} sharedUrl={sharedUrl} height={160} /> : null}

      <View style={styles.actionsRow}>
        <Button
          label="View Today"
          variant="outline"
          size="md"
          onPress={() =>
            navigation.navigate("Main", {
              screen: "Calendar",
              params: { screen: "CalendarHome", params: { segment: "today" } },
            })
          }
        />
        <Button label={busy ? "Exporting…" : "Export .ics"} loading={busy} size="md" onPress={() => void shareIcs()} />
      </View>

      {newlyScheduled ? (
        <Card style={styles.heroCard}>
          <AppText variant="labelSmall" tone="tertiary" style={styles.heroKicker}>
            Newly scheduled
          </AppText>
          <AppText variant="title" style={styles.heroTitle}>
            {newlyScheduled.title}
          </AppText>
          {"start_time" in newlyScheduled ? (
            <AppText tone="secondary" style={styles.meta}>
              {formatFriendlyEventDateTime(newlyScheduled.start_time)}
            </AppText>
          ) : null}
          <AppText tone="secondary" style={styles.venueText}>
            {newlyScheduled.venue}
          </AppText>
        </Card>
      ) : null}

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.textSecondary} />
        </View>
      ) : (
        <>
          <SectionHeader title="Today" />
          {uniqueToday.length ? (
            <View>
              <FlatList
                horizontal
                showsHorizontalScrollIndicator={false}
                snapToInterval={CAROUSEL_EVENT_CARD_STRIDE}
                snapToAlignment="start"
                decelerationRate="fast"
                disableIntervalMomentum
                contentContainerStyle={styles.carousel}
                data={confirmedTodayCarousel}
                keyExtractor={(e) => e.id}
                ItemSeparatorComponent={() => <View style={styles.carouselGap} />}
                onMomentumScrollEnd={onTodayCarouselScrollEnd}
                renderItem={({ item }) => (
                  <View style={styles.carouselItem}>
                    <UpcomingEventCard
                      apiBaseUrl={apiBaseUrl}
                      kickerLabel="Today"
                      todayContext={{
                        accessToken,
                        venueId: item.venue_id,
                        visibility: item.visibility,
                      }}
                      item={item}
                      onPress={({ eventId, sharedUrl }) => {
                        if (navigationRef.isReady()) {
                          navigationRef.navigate("EventDetail", {
                            eventId,
                            title: item.title,
                            start_time: item.start_time,
                            venue: item.venue,
                            price: item.price ?? undefined,
                            ownerUserId: item.user_id,
                            sharedUrl: sharedUrl ?? undefined,
                          });
                        }
                      }}
                    />
                  </View>
                )}
              />
              <CarouselDots count={confirmedTodayCarousel.length} activeIndex={todayCarouselIndex} />
            </View>
          ) : (
            <AppText tone="tertiary" style={styles.empty}>
              No more events today.
            </AppText>
          )}

          <SectionHeader title="Upcoming (30 days)" />
          {uniqueUpcoming.length ? (
            <View>
              <FlatList
                horizontal
                showsHorizontalScrollIndicator={false}
                snapToInterval={CAROUSEL_EVENT_CARD_STRIDE}
                snapToAlignment="start"
                decelerationRate="fast"
                disableIntervalMomentum
                contentContainerStyle={styles.carousel}
                data={confirmedUpcomingCarousel}
                keyExtractor={(e) => e.id}
                ItemSeparatorComponent={() => <View style={styles.carouselGap} />}
                onMomentumScrollEnd={onUpcomingCarouselScrollEnd}
                renderItem={({ item }) => (
                  <View style={styles.carouselItem}>
                    <UpcomingEventCard
                      apiBaseUrl={apiBaseUrl}
                      item={item}
                      onPress={({ eventId, sharedUrl }) => {
                        if (navigationRef.isReady()) {
                          navigationRef.navigate("EventDetail", {
                            eventId,
                            title: item.title,
                            start_time: item.start_time,
                            venue: item.venue,
                            price: item.price ?? undefined,
                            ownerUserId: item.user_id,
                            sharedUrl: sharedUrl ?? undefined,
                          });
                        }
                      }}
                    />
                  </View>
                )}
              />
              <CarouselDots count={confirmedUpcomingCarousel.length} activeIndex={upcomingCarouselIndex} />
            </View>
          ) : (
            <AppText tone="tertiary" style={styles.empty}>
              No upcoming events.
            </AppText>
          )}
        </>
      )}

      <Pressable style={({ pressed }) => [styles.footerBtn, pressedOpacityStyle(pressed)]} onPress={() => navigation.popToTop()}>
        <AppText tone="tertiary" style={styles.footerLabel}>
          Back to home
        </AppText>
      </Pressable>
    </ScrollView>
  );
}
