import React, { useCallback, useMemo, useState } from "react";
import { ActivityIndicator, FlatList, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { listUpcoming, type UpcomingEventRow } from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { UpcomingEventCard } from "../components/UpcomingEventCard";
import { dedupeByEventFingerprint } from "../lib/dedupeEvents";
import { AppText } from "../design/components";
import { tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";

type Props = { navigation: { navigate: (name: string, params?: any) => void } };

export function UpcomingScreen({ navigation }: Props) {
  const { colors } = useTheme();
  const styles = useThemedStyles((c) => ({
    center: { flex: 1, backgroundColor: c.bg, justifyContent: "center" as const, alignItems: "center" as const },
    list: { padding: tokens.spacing[16], backgroundColor: c.bg, flexGrow: 1 },
    empty: { textAlign: "center" as const, marginTop: 48, paddingHorizontal: 24 },
  }));
  const { accessToken, apiBaseUrl } = useAuth();
  const [rows, setRows] = useState<UpcomingEventRow[]>([]);
  const [loading, setLoading] = useState(true);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      void (async () => {
        setLoading(true);
        try {
          const list = await listUpcoming(apiBaseUrl, accessToken);
          if (!cancelled) setRows(list);
        } catch {
          if (!cancelled) setRows([]);
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [apiBaseUrl, accessToken])
  );

  const uniqueRows = useMemo(() => {
    return dedupeByEventFingerprint<UpcomingEventRow>(rows);
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
          No upcoming events yet. Import a link from the home screen.
        </AppText>
      }
      renderItem={({ item }) => (
        <UpcomingEventCard
          apiBaseUrl={apiBaseUrl}
          item={item}
          onPress={({ eventId, sharedUrl }) =>
            navigation.navigate("EventDetail", {
              eventId,
              title: item.title,
              start_time: item.start_time,
              venue: item.venue,
              price: item.price ?? undefined,
              ownerUserId: item.user_id,
              sharedUrl: sharedUrl ?? undefined,
            })
          }
        />
      )}
    />
  );
}
