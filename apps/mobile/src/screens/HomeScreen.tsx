import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useFocusEffect } from "@react-navigation/native";
import React, { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  NativeScrollEvent,
  NativeSyntheticEvent,
  Pressable,
  ScrollView,
  View,
} from "react-native";
import { listToday, listUpcoming, type TodayEventRow, type UpcomingEventRow } from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import type { InboxStackParamList } from "../navigation/types";
import { navigationRef } from "../navigation/navigationRef";
import { UpcomingEventCard } from "../components/UpcomingEventCard";
import { dedupeByEventFingerprint } from "../lib/dedupeEvents";
import { tokens, pressedOpacityStyle } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";
import { AppText, Button, CarouselDots, CAROUSEL_EVENT_CARD_STRIDE, ProfileIconButton } from "../design/components";

type Props = NativeStackScreenProps<InboxStackParamList, "InboxHome">;

function isThisWeek(dateStr: string): boolean {
  const now = new Date();
  const d = new Date(dateStr);
  const endOfWeek = new Date(now);
  endOfWeek.setDate(now.getDate() + (7 - now.getDay()));
  endOfWeek.setHours(23, 59, 59, 999);
  return d > now && d <= endOfWeek;
}

export function HomeScreen({ navigation }: Props) {
  const { colors } = useTheme();
  const styles = useThemedStyles((c) => ({
    root: { flex: 1, backgroundColor: c.bg },
    content: { paddingBottom: 32, flexGrow: 1 },
    lead: { marginBottom: tokens.spacing[8] },
    center: { paddingVertical: 48, alignItems: "center" as const, justifyContent: "center" as const },
    empty: { lineHeight: 20 },
    sectionTitle: { marginBottom: tokens.spacing[12] },
    todayList: { gap: tokens.spacing[12] },
    todayCardWrap: { width: "100%" as const },
    carousel: { paddingVertical: 2 },
    carouselGap: { width: 10 },
    carouselItem: { width: 320 },
  }));
  const { apiBaseUrl, accessToken } = useAuth();

  const [thisWeekIdx, setThisWeekIdx] = useState(0);
  const [laterIdx, setLaterIdx] = useState(0);

  React.useLayoutEffect(() => {
    navigation.setOptions({
      headerTitle: () => {
        const hour = new Date().getHours();
        let greeting = "Good evening";
        if (hour < 12) greeting = "Good morning";
        else if (hour < 17) greeting = "Good afternoon";
        return (
          <AppText variant="title" style={{ letterSpacing: 0.2 }}>
            {greeting}
          </AppText>
        );
      },
      headerRight: () => <ProfileIconButton onPress={() => navigationRef.navigate("SocialHub")} />,
    });
  }, [navigation]);

  const tzOffsetMinutes = useMemo(() => -new Date().getTimezoneOffset(), []);
  const [loading, setLoading] = useState(true);
  const [today, setToday] = useState<TodayEventRow[]>([]);
  const [upcoming, setUpcoming] = useState<UpcomingEventRow[]>([]);

  useFocusEffect(
    useCallback(() => {
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
        } catch {
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
    }, [apiBaseUrl, accessToken, tzOffsetMinutes])
  );

  const uniqueToday = useMemo(() => dedupeByEventFingerprint<TodayEventRow>(today), [today]);
  const uniqueUpcoming = useMemo(() => dedupeByEventFingerprint<UpcomingEventRow>(upcoming), [upcoming]);

  const thisWeek = useMemo(
    () => uniqueUpcoming.filter((e) => isThisWeek(e.start_time)).slice(0, 8),
    [uniqueUpcoming]
  );

  const later = useMemo(
    () => uniqueUpcoming.filter((e) => !isThisWeek(e.start_time)).slice(0, 8),
    [uniqueUpcoming]
  );

  const renderEventCard = useCallback(
    (e: UpcomingEventRow) => (
      <UpcomingEventCard
        apiBaseUrl={apiBaseUrl}
        item={e}
        onPress={({ eventId, sharedUrl }) => {
          if (navigationRef.isReady()) {
            navigationRef.navigate("EventDetail", {
              eventId,
              title: e.title,
              start_time: e.start_time,
              venue: e.venue,
              price: e.price ?? undefined,
              ownerUserId: e.user_id,
              sharedUrl: sharedUrl ?? undefined,
            });
          }
        }}
      />
    ),
    [apiBaseUrl]
  );

  const onScrollEnd = (setter: (n: number) => void, n: number) =>
    (e: NativeSyntheticEvent<NativeScrollEvent>) => {
      if (n <= 1) return;
      const x = e.nativeEvent.contentOffset.x;
      const idx = Math.min(Math.max(0, Math.round(x / CAROUSEL_EVENT_CARD_STRIDE)), n - 1);
      setter(idx);
    };

  if (loading) {
    return (
      <View style={[styles.center, { backgroundColor: colors.bg }]}>
        <ActivityIndicator color={colors.textSecondary} />
      </View>
    );
  }

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content}>
      {/* Lead + quick actions */}
      <View style={{ paddingHorizontal: tokens.spacing[20], paddingTop: tokens.spacing[8], gap: tokens.spacing[16] }}>
        <AppText tone="secondary" style={styles.lead}>
          {uniqueToday.length > 0
            ? `You have ${uniqueToday.length} event${uniqueToday.length > 1 ? "s" : ""} today.`
            : "No events today. Use Capture to add one."}
        </AppText>

        <Button
          label="Open Capture"
          variant="outline"
          onPress={() => navigation.getParent()?.navigate("Capture", { screen: "CaptureHome" })}
          fullWidth
        />
      </View>

      {/* Today */}
      {uniqueToday.length > 0 && (
        <View style={{ marginTop: tokens.spacing[24], paddingHorizontal: tokens.spacing[20] }}>
          <AppText variant="title" style={{ marginBottom: tokens.spacing[12] }}>Today</AppText>
          <View style={styles.todayList}>
            {uniqueToday.map((e) => (
              <View key={e.id} style={styles.todayCardWrap}>
                <UpcomingEventCard
                  apiBaseUrl={apiBaseUrl}
                  kickerLabel="Today"
                  todayContext={{
                    accessToken,
                    venueId: e.venue_id,
                    visibility: e.visibility,
                  }}
                  item={e}
                  onPress={({ eventId, sharedUrl }) => {
                    if (navigationRef.isReady()) {
                      navigationRef.navigate("EventDetail", {
                        eventId,
                        title: e.title,
                        start_time: e.start_time,
                        venue: e.venue,
                        price: e.price ?? undefined,
                        ownerUserId: e.user_id,
                        sharedUrl: sharedUrl ?? undefined,
                      });
                    }
                  }}
                />
              </View>
            ))}
          </View>
        </View>
      )}

      {/* This Week */}
      {thisWeek.length > 0 && (
        <View style={{ marginTop: tokens.spacing[24] }}>
          <View style={{ paddingHorizontal: tokens.spacing[20] }}>
            <AppText variant="title" style={styles.sectionTitle}>This Week</AppText>
          </View>
          <FlatList
            horizontal
            showsHorizontalScrollIndicator={false}
            snapToInterval={CAROUSEL_EVENT_CARD_STRIDE}
            snapToAlignment="start"
            decelerationRate="fast"
            disableIntervalMomentum
            contentContainerStyle={styles.carousel}
            data={thisWeek}
            keyExtractor={(e) => e.id}
            ItemSeparatorComponent={() => <View style={styles.carouselGap} />}
            onMomentumScrollEnd={onScrollEnd(setThisWeekIdx, thisWeek.length)}
            renderItem={({ item: e }) => (
              <View style={styles.carouselItem}>{renderEventCard(e)}</View>
            )}
          />
          <View style={{ paddingHorizontal: tokens.spacing[20] }}>
            <CarouselDots count={thisWeek.length} activeIndex={thisWeekIdx} />
          </View>
        </View>
      )}

      {/* Later (beyond this week) */}
      {later.length > 0 && (
        <View style={{ marginTop: tokens.spacing[24] }}>
          <View style={{ paddingHorizontal: tokens.spacing[20] }}>
            <AppText variant="title" style={styles.sectionTitle}>Upcoming</AppText>
          </View>
          <FlatList
            horizontal
            showsHorizontalScrollIndicator={false}
            snapToInterval={CAROUSEL_EVENT_CARD_STRIDE}
            snapToAlignment="start"
            decelerationRate="fast"
            disableIntervalMomentum
            contentContainerStyle={styles.carousel}
            data={later}
            keyExtractor={(e) => e.id}
            ItemSeparatorComponent={() => <View style={styles.carouselGap} />}
            onMomentumScrollEnd={onScrollEnd(setLaterIdx, later.length)}
            renderItem={({ item: e }) => (
              <View style={styles.carouselItem}>{renderEventCard(e)}</View>
            )}
          />
          <View style={{ paddingHorizontal: tokens.spacing[20] }}>
            <CarouselDots count={later.length} activeIndex={laterIdx} />
          </View>
        </View>
      )}

      {/* Empty state */}
      {uniqueToday.length === 0 && thisWeek.length === 0 && later.length === 0 && (
        <View style={[styles.center, { paddingHorizontal: tokens.spacing[20] }]}>
          <AppText tone="tertiary" style={styles.empty}>
            Nothing on your calendar yet.
          </AppText>
        </View>
      )}

      {/* View full calendar */}
      <Pressable
        accessibilityLabel="View full calendar"
        style={({ pressed }) => [
          { paddingVertical: tokens.spacing[16], paddingHorizontal: tokens.spacing[20], marginTop: tokens.spacing[8] },
          pressedOpacityStyle(pressed),
        ]}
        onPress={() =>
          navigation.getParent()?.navigate("Calendar", {
            screen: "CalendarHome",
            params: { segment: "upcoming" },
          })
        }
      >
        <AppText variant="label" tone="secondary">
          View full calendar
        </AppText>
      </Pressable>
    </ScrollView>
  );
}
