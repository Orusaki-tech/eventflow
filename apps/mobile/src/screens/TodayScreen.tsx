import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useCallback, useMemo, useState } from "react";
import { ActivityIndicator, FlatList, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { listToday, type TodayEventRow } from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { UpcomingEventCard } from "../components/UpcomingEventCard";
import { dedupeByEventFingerprint } from "../lib/dedupeEvents";
import type { CalendarStackParamList } from "../navigation/types";
import { navigationRef } from "../navigation/navigationRef";
import { AppText } from "../design/components";
import { tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";

type Props = NativeStackScreenProps<CalendarStackParamList, "CalendarHome">;

export function TodayScreen({}: Props) {
  const { colors } = useTheme();
  const styles = useThemedStyles((c) => ({
    center: { flex: 1, backgroundColor: c.bg, justifyContent: "center" as const, alignItems: "center" as const },
    list: { padding: tokens.spacing[16], backgroundColor: c.bg, flexGrow: 1, gap: tokens.spacing[12] },
    empty: { textAlign: "center" as const, marginTop: 48, paddingHorizontal: 24 },
  }));
  const { accessToken, apiBaseUrl, refreshSession } = useAuth();
  const [rows, setRows] = useState<TodayEventRow[]>([]);
  const [loading, setLoading] = useState(true);

  const tzOffsetMinutes = useMemo(() => -new Date().getTimezoneOffset(), []);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      void (async () => {
        setLoading(true);
        try {
          const list = await listToday(apiBaseUrl, accessToken, tzOffsetMinutes);
          if (!cancelled) setRows(list);
        } catch {
          if (!cancelled) setRows([]);
          await refreshSession().catch(() => undefined);
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [accessToken, apiBaseUrl, refreshSession, tzOffsetMinutes])
  );

  const uniqueRows = useMemo(() => {
    return dedupeByEventFingerprint<TodayEventRow>(rows);
  }, [rows]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.textSecondary} />
      </View>
    );
  }

  return (
    <FlatList
      contentContainerStyle={styles.list}
      data={uniqueRows}
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
  );
}
