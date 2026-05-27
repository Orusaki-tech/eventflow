import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useFocusEffect, useRoute } from "@react-navigation/native";
import React, { useCallback, useMemo, useState } from "react";
import { ActivityIndicator, FlatList, Linking, Pressable, View } from "react-native";
import {
  listToday,
  listUpcoming,
  getSavedCommunityEvents,
  startGoogleCalendarOAuth,
  type TodayEventRow,
  type UpcomingEventRow,
  type UnifiedFeedEvent,
} from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { UpcomingEventCard } from "../components/UpcomingEventCard";
import { EventCardCompact, COMPACT_CARD_WIDTH } from "../components/EventCardCompact";
import { dedupeByEventFingerprint } from "../lib/dedupeEvents";
import type { CalendarStackParamList } from "../navigation/types";
import { navigationRef } from "../navigation/navigationRef";
import { AppText, ProfileIconButton } from "../design/components";
import { pressedOpacityStyle, tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";

type Props = NativeStackScreenProps<CalendarStackParamList, "CalendarHome">;

type Segment = "today" | "upcoming";

export function CalendarScreen({ navigation }: Props) {
  const { colors } = useTheme();
  const styles = useThemedStyles((c) => ({
    root: { flex: 1, backgroundColor: c.bg },
    segmentRow: {
      flexDirection: "row" as const,
      paddingHorizontal: tokens.spacing[16],
      paddingTop: tokens.spacing[8],
      gap: tokens.spacing[8],
    },
    segment: {
      flex: 1,
      paddingVertical: tokens.spacing[12],
      alignItems: "center" as const,
      borderRadius: tokens.radii.sm,
      borderWidth: 1,
      borderColor: c.border,
      backgroundColor: c.surface1,
    },
    segmentActive: {
      backgroundColor: c.surface2,
      borderColor: c.textPrimary,
    },
    center: { flex: 1, justifyContent: "center" as const, alignItems: "center" as const },
    list: { padding: tokens.spacing[16], backgroundColor: c.bg, flexGrow: 1, gap: tokens.spacing[12] },
    empty: { textAlign: "center" as const, marginTop: 48, paddingHorizontal: 24 },
    connectBtn: {
      marginHorizontal: tokens.spacing[16],
      paddingVertical: tokens.spacing[12],
      borderRadius: tokens.radii.sm,
      borderWidth: 1,
      borderColor: c.border,
      alignItems: "center" as const,
      backgroundColor: c.surface1,
    },
    savedSection: { gap: tokens.spacing[8], paddingHorizontal: tokens.spacing[16] },
    savedRow: { flexDirection: "row" as const, gap: tokens.spacing[8] },
  }));
  const route = useRoute();
  const params = route.params as { segment?: Segment } | undefined;
  const [segment, setSegment] = useState<Segment>(params?.segment ?? "today");

  React.useLayoutEffect(() => {
    navigation.setOptions({
      headerRight: () => <ProfileIconButton onPress={() => navigationRef.navigate("SocialHub")} />,
    });
  }, [navigation]);

  React.useEffect(() => {
    const s = params?.segment;
    if (s === "today" || s === "upcoming") setSegment(s);
  }, [params?.segment]);

  const { accessToken, apiBaseUrl, refreshSession } = useAuth();
  const [todayRows, setTodayRows] = useState<TodayEventRow[]>([]);
  const [upcomingRows, setUpcomingRows] = useState<UpcomingEventRow[]>([]);
  const [savedEvents, setSavedEvents] = useState<UnifiedFeedEvent[]>([]);
  const [loading, setLoading] = useState(true);

  const tzOffsetMinutes = useMemo(() => -new Date().getTimezoneOffset(), []);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      void (async () => {
        setLoading(true);
        try {
          const [t, u, s] = await Promise.all([
            listToday(apiBaseUrl, accessToken, tzOffsetMinutes),
            listUpcoming(apiBaseUrl, accessToken),
            getSavedCommunityEvents(apiBaseUrl, accessToken).catch(() => []),
          ]);
          if (!cancelled) {
            setTodayRows(t);
            setUpcomingRows(u);
            setSavedEvents(s);
          }
        } catch (e: unknown) {
          if (!cancelled) {
            setTodayRows([]);
            setUpcomingRows([]);
            setSavedEvents([]);
          }
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [accessToken, apiBaseUrl, tzOffsetMinutes])
  );

  const uniqueTodayRows = useMemo(() => {
    return dedupeByEventFingerprint<TodayEventRow>(todayRows);
  }, [todayRows]);

  const uniqueUpcomingRows = useMemo(() => {
    return dedupeByEventFingerprint<UpcomingEventRow>(upcomingRows);
  }, [upcomingRows]);

  const handleConnectGoogleCalendar = async () => {
    try {
      const res = await startGoogleCalendarOAuth(apiBaseUrl, accessToken);
      if (res.url) {
        const ok = await Linking.canOpenURL(res.url);
        if (ok) await Linking.openURL(res.url);
      }
    } catch (e: unknown) {
      console.error("Google Calendar connect failed", e);
    }
  };

  const renderSavedEvents = () => {
    if (savedEvents.length === 0) return null;
    return (
      <View style={styles.savedSection}>
        <AppText variant="label">Saved Events</AppText>
        <FlatList
          horizontal
          showsHorizontalScrollIndicator={false}
          data={savedEvents}
          keyExtractor={(item) => item.item_id}
          renderItem={({ item }) => (
            <View style={{ width: COMPACT_CARD_WIDTH, marginRight: tokens.spacing[8] }}>
              <EventCardCompact item={item} />
            </View>
          )}
        />
      </View>
    );
  };

  return (
    <View style={styles.root}>
      <Pressable
        style={({ pressed }) => [styles.connectBtn, pressedOpacityStyle(pressed)]}
        onPress={handleConnectGoogleCalendar}
      >
        <AppText tone="secondary">Connect Google Calendar</AppText>
      </Pressable>

      <View style={styles.segmentRow}>
        <Pressable
          accessibilityLabel="Today tab"
          style={({ pressed }) => [
            styles.segment,
            segment === "today" && styles.segmentActive,
            pressedOpacityStyle(pressed),
          ]}
          onPress={() => setSegment("today")}
        >
          <AppText variant="label" tone={segment === "today" ? "primary" : "secondary"}>
            Today
          </AppText>
        </Pressable>
        <Pressable
          accessibilityLabel="Upcoming tab"
          style={({ pressed }) => [
            styles.segment,
            segment === "upcoming" && styles.segmentActive,
            pressedOpacityStyle(pressed),
          ]}
          onPress={() => setSegment("upcoming")}
        >
          <AppText variant="label" tone={segment === "upcoming" ? "primary" : "secondary"}>
            Upcoming
          </AppText>
        </Pressable>
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.textSecondary} />
        </View>
      ) : segment === "today" ? (
        <FlatList
          contentContainerStyle={styles.list}
          data={uniqueTodayRows}
          keyExtractor={(item) => item.id}
          ListHeaderComponent={renderSavedEvents}
          ListEmptyComponent={
            <AppText tone="tertiary" style={styles.empty}>
              No events for today.
            </AppText>
          }
          renderItem={({ item }) => (
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
          )}
        />
      ) : (
        <FlatList
          contentContainerStyle={styles.list}
          data={uniqueUpcomingRows}
          keyExtractor={(item) => item.id}
          ListHeaderComponent={renderSavedEvents}
          ListEmptyComponent={
            <AppText tone="tertiary" style={styles.empty}>
              No upcoming events yet. Import a link from the Capture tab.
            </AppText>
          }
          renderItem={({ item }) => (
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
          )}
        />
      )}
    </View>
  );
}
