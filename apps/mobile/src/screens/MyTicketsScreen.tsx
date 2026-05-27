import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useFocusEffect } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { ActivityIndicator, FlatList, StyleSheet, View } from "react-native";
import QRCode from "react-native-qrcode-svg";
import { listMyOrders, type OrderRow } from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { AppText } from "../design/components";
import { tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
// Used in both TicketsStack (TicketsHome) and RootStack (MyTickets)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Props = any;

export function MyTicketsScreen(_props: Props) {
  const { colors } = useTheme();
  const { accessToken, apiBaseUrl } = useAuth();
  const [orders, setOrders] = useState<OrderRow[]>([]);
  const [loading, setLoading] = useState(true);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      void (async () => {
        setLoading(true);
        try {
          const res = await listMyOrders(apiBaseUrl, accessToken);
          if (!cancelled) setOrders(res);
        } catch {
          if (!cancelled) setOrders([]);
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
      return () => { cancelled = true; };
    }, [accessToken, apiBaseUrl]),
  );

  if (loading) {
    return (
      <View style={[styles.center, { backgroundColor: colors.bg }]}>
        <ActivityIndicator color={colors.textSecondary} />
      </View>
    );
  }

  if (orders.length === 0) {
    return (
      <View style={[styles.center, { backgroundColor: colors.bg }]}>
        <AppText tone="tertiary">No tickets yet.</AppText>
      </View>
    );
  }

  return (
    <FlatList
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={styles.list}
      data={orders}
      keyExtractor={(o) => o.order_id}
      renderItem={({ item }) => (
        <View style={[styles.card, { backgroundColor: colors.surface1, borderColor: colors.border }]}>
          <AppText style={styles.eventTitle}>{item.event_title}</AppText>
          <AppText tone="secondary" style={{ fontSize: 12 }}>
            {item.receipt_number ?? "No receipt"}
          </AppText>
          <AppText tone="secondary" style={{ fontSize: 12 }}>
            {item.paid_at ? new Date(item.paid_at).toLocaleDateString() : "Unpaid"}
          </AppText>

          {item.tickets.map((t) => (
            <View key={t.ticket_id} style={styles.ticketRow}>
              <View style={styles.qrWrap}>
                <QRCode value={t.short_code} size={60} backgroundColor="white" color="black" />
              </View>
              <View style={{ gap: 2 }}>
                <AppText style={styles.ticketType}>{t.ticket_type_name}</AppText>
                <AppText style={styles.shortCode}>{t.short_code}</AppText>
                <AppText style={styles.statusBadge}>{t.status}</AppText>
              </View>
            </View>
          ))}
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  list: { padding: tokens.spacing[16], gap: tokens.spacing[12] },
  card: {
    padding: tokens.spacing[16],
    borderRadius: tokens.radii.md,
    borderWidth: 1,
    gap: 8,
  },
  eventTitle: { fontSize: 16, fontWeight: "800" },
  ticketRow: {
    flexDirection: "row",
    gap: 12,
    alignItems: "center",
    paddingTop: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: "#333",
  },
  qrWrap: {
    borderRadius: 8,
    overflow: "hidden",
    backgroundColor: "white",
    padding: 4,
  },
  ticketType: { fontSize: 13, fontWeight: "600" },
  shortCode: { fontSize: 12, fontFamily: "monospace", color: "#888" },
  statusBadge: { fontSize: 11, fontWeight: "700", color: "#4CAF50" },
});
