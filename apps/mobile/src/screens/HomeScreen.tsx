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

export function HomeScreen({ navigation }: Props) {
  const { colors } = useTheme();
  const styles = useThemedStyles((c) => ({
    root: { flex: 1, backgroundColor: c.bg },
    content: { padding: tokens.spacing[20], gap: tokens.spacing[16], flexGrow: 1 },
    lead: { marginBottom: tokens.spacing[8] },
    headerTitle: { letterSpacing: 0.2 },
    sectionTitle: { marginTop: tokens.spacing[8] },
    center: { paddingVertical: 8, alignItems: "center" as const, justifyContent: "center" as const },
    empty: { lineHeight: 20 },
    carousel: { paddingVertical: 2 },
    carouselGap: { width: 10 },
    carouselItem: { width: 320 },
    secondaryBtn: { paddingVertical: tokens.spacing[12] },
    secondaryLabel: {},
    todayList: { gap: tokens.spacing[12] },
    todayCardWrap: { width: "100%" as const },
  }));
  const { apiBaseUrl, accessToken } = useAuth();

  React.useLayoutEffect(() => {
    navigation.setOptions({
      headerTitle: () => (
        <AppText variant="title" style={styles.headerTitle}>
          EventFlow
        </AppText>
      ),
      headerRight: () => <ProfileIconButton onPress={() => navigationRef.navigate("SocialHub")} />,
    });
  }, [navigation, styles.headerTitle]);

  const tzOffsetMinutes = useMemo(() => -new Date().getTimezoneOffset(), []);
  const [loading, setLoading] = useState(true);
  const [today, setToday] = useState<TodayEventRow[]>([]);
  const [upcoming, setUpcoming] = useState<UpcomingEventRow[]>([]);
  const [upcomingCarouselIndex, setUpcomingCarouselIndex] = useState(0);

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
          setUpcoming(u.slice(0, 3));
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

  const uniqueUpcoming = useMemo(() => {
    return dedupeByEventFingerprint<UpcomingEventRow>(upcoming);
  }, [upcoming]);

  const upcomingCarouselData = useMemo(() => uniqueUpcoming.slice(0, 8), [uniqueUpcoming]);

  const onUpcomingCarouselScrollEnd = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const n = upcomingCarouselData.length;
    if (n <= 1) return;
    const x = e.nativeEvent.contentOffset.x;
    const idx = Math.min(Math.max(0, Math.round(x / CAROUSEL_EVENT_CARD_STRIDE)), n - 1);
    setUpcomingCarouselIndex(idx);
  };

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content}>
      <AppText tone="secondary" style={styles.lead}>
        Today’s plan, then what’s next. Use the Capture tab to paste a link or upload a poster.
      </AppText>

      <Button
        label="Open Capture"
        variant="outline"
        onPress={() => navigation.getParent()?.navigate("Capture", { screen: "CaptureHome" })}
        fullWidth
      />

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.textSecondary} />
        </View>
      ) : (
        <>
          <AppText variant="title" style={styles.sectionTitle}>
            Today
          </AppText>
          {uniqueToday.length ? (
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
          ) : (
            <AppText tone="tertiary" style={styles.empty}>
              Nothing on your calendar for today.
            </AppText>
          )}

          <AppText variant="title" style={styles.sectionTitle}>
            Upcoming (30 days)
          </AppText>
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
                data={upcomingCarouselData}
                keyExtractor={(e) => e.id}
                ItemSeparatorComponent={() => <View style={styles.carouselGap} />}
                onMomentumScrollEnd={onUpcomingCarouselScrollEnd}
                renderItem={({ item: e }) => (
                  <View style={styles.carouselItem}>
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
                  </View>
                )}
              />
              <CarouselDots count={upcomingCarouselData.length} activeIndex={upcomingCarouselIndex} />
            </View>
          ) : (
            <AppText tone="tertiary" style={styles.empty}>
              No upcoming events yet.
            </AppText>
          )}
        </>
      )}

      <Pressable
        style={({ pressed }) => [styles.secondaryBtn, pressedOpacityStyle(pressed)]}
        onPress={() =>
          navigation.getParent()?.navigate("Calendar", {
            screen: "CalendarHome",
            params: { segment: "upcoming" },
          })
        }
      >
        <AppText variant="label" tone="secondary" style={styles.secondaryLabel}>
          View full calendar
        </AppText>
      </Pressable>
    </ScrollView>
  );
}
