import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useFocusEffect } from "@react-navigation/native";
import React, { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  View,
} from "react-native";
import {
  listToday,
  listUpcoming,
  getSavedCommunityEvents,
  type TodayEventRow,
  type UpcomingEventRow,
  type UnifiedFeedEvent,
} from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import type { InboxStackParamList } from "../navigation/types";
import { navigationRef } from "../navigation/navigationRef";
import { UpcomingEventCard } from "../components/UpcomingEventCard";
import { EventCardCompact, COMPACT_CARD_WIDTH } from "../components/EventCardCompact";
import { dedupeByEventFingerprint } from "../lib/dedupeEvents";
import { tokens, pressedOpacityStyle } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";
import { AppText, Button, ProfileIconButton } from "../design/components";

type Props = NativeStackScreenProps<InboxStackParamList, "InboxHome">;

type Segment = "today" | "upcoming";

export function HomeScreen({ navigation }: Props) {
  const { colors } = useTheme();
  const styles = useThemedStyles((c) => ({
    root: { flex: 1, backgroundColor: c.bg },
    lead: { marginBottom: tokens.spacing[8] },
    segmentRow: {
      flexDirection: "row" as const,
      paddingHorizontal: tokens.spacing[16],
      paddingTop: tokens.spacing[16],
      paddingBottom: tokens.spacing[8],
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
    savedSection: { gap: tokens.spacing[8], paddingHorizontal: tokens.spacing[16], marginBottom: tokens.spacing[16] },
  }));
  const { apiBaseUrl, accessToken } = useAuth();
  const [segment, setSegment] = useState<Segment>("today");

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
  const [todayRows, setTodayRows] = useState<TodayEventRow[]>([]);
  const [upcomingRows, setUpcomingRows] = useState<UpcomingEventRow[]>([]);
  const [savedEvents, setSavedEvents] = useState<UnifiedFeedEvent[]>([]);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      void (async () => {
        setLoading(true);
        try {
          const [t, u, s] = await Promise.all([
            listToday(apiBaseUrl, accessToken, tzOffsetMinutes),
            listUpcoming(apiBaseUrl, accessToken, 30),
            getSavedCommunityEvents(apiBaseUrl, accessToken).catch(() => []),
          ]);
          if (!cancelled) {
            setTodayRows(t);
            setUpcomingRows(u);
            setSavedEvents(s);
          }
        } catch {
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
    }, [apiBaseUrl, accessToken, tzOffsetMinutes])
  );

  const uniqueTodayRows = useMemo(() => dedupeByEventFingerprint<TodayEventRow>(todayRows), [todayRows]);
  const uniqueUpcomingRows = useMemo(() => dedupeByEventFingerprint<UpcomingEventRow>(upcomingRows), [upcomingRows]);

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
      {/* Lead + quick actions */}
      <View style={{ paddingHorizontal: tokens.spacing[20], paddingTop: tokens.spacing[8], gap: tokens.spacing[16] }}>
        <AppText tone="secondary" style={styles.lead}>
          {uniqueTodayRows.length > 0
            ? `You have ${uniqueTodayRows.length} event${uniqueTodayRows.length > 1 ? "s" : ""} today.`
            : "No events today. Use Capture to add one."}
        </AppText>

        <Button
          label="Open Capture"
          variant="outline"
          onPress={() => navigation.getParent()?.navigate("Capture", { screen: "CaptureHome" })}
          fullWidth
        />
      </View>

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
