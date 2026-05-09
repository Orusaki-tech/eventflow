import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useFocusEffect, useRoute } from "@react-navigation/native";
import React, { useCallback, useMemo, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, View } from "react-native";
import {
  listToday,
  listUpcoming,
  type TodayEventRow,
  type UpcomingEventRow,
} from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { UpcomingEventCard } from "../components/UpcomingEventCard";
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
  const [loadingToday, setLoadingToday] = useState(true);
  const [loadingUpcoming, setLoadingUpcoming] = useState(true);

  const tzOffsetMinutes = useMemo(() => -new Date().getTimezoneOffset(), []);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      void (async () => {
        setLoadingToday(true);
        try {
          const list = await listToday(apiBaseUrl, accessToken, tzOffsetMinutes);
          if (!cancelled) setTodayRows(list);
        } catch {
          if (!cancelled) setTodayRows([]);
          await refreshSession().catch(() => undefined);
        } finally {
          if (!cancelled) setLoadingToday(false);
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [accessToken, apiBaseUrl, refreshSession, tzOffsetMinutes])
  );

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      void (async () => {
        setLoadingUpcoming(true);
        try {
          const list = await listUpcoming(apiBaseUrl, accessToken);
          if (!cancelled) setUpcomingRows(list);
        } catch {
          if (!cancelled) setUpcomingRows([]);
        } finally {
          if (!cancelled) setLoadingUpcoming(false);
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [accessToken, apiBaseUrl])
  );

  const uniqueTodayRows = useMemo(() => {
    return dedupeByEventFingerprint<TodayEventRow>(todayRows);
  }, [todayRows]);

  const uniqueUpcomingRows = useMemo(() => {
    return dedupeByEventFingerprint<UpcomingEventRow>(upcomingRows);
  }, [upcomingRows]);

  const loading = segment === "today" ? loadingToday : loadingUpcoming;

  return (
    <View style={styles.root}>
      <View style={styles.segmentRow}>
        <Pressable
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
