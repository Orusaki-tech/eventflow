import React, { useCallback, useState } from "react";
import { ActivityIndicator, Linking, ScrollView, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import {
  createCheckoutSession,
  getSubscription,
  getWatchQuota,
} from "../api/eventflow";
import type { SubscriptionResponse } from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { AppText, Button } from "../design/components";
import { tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";

export function SubscriptionScreen() {
  const { colors } = useTheme();
  const styles = useThemedStyles((c) => ({
    root: { flex: 1, backgroundColor: c.bg, padding: tokens.spacing[16] } as const,
    center: { flex: 1, justifyContent: "center" as const, alignItems: "center" as const } as const,
    card: {
      backgroundColor: c.surface1,
      borderRadius: tokens.radii.md,
      padding: tokens.spacing[24],
      gap: tokens.spacing[16],
      marginTop: tokens.spacing[32],
    } as const,
    price: { fontSize: 36, fontWeight: "900" as const, color: c.textPrimary, textAlign: "center" as const },
    period: { fontSize: 14, color: c.textSecondary, textAlign: "center" as const },
    feature: { fontSize: 15, color: c.textPrimary, lineHeight: 22 },
    statusBadge: {
      alignSelf: "center",
      paddingHorizontal: 16,
      paddingVertical: 6,
      borderRadius: 20,
      backgroundColor: "#4CAF50",
    } as const,
    statusText: { color: "#fff", fontWeight: "700" as const, fontSize: 13 },
    error: { color: "#E53935", textAlign: "center" as const },
  }));

  const { accessToken, apiBaseUrl, refreshSession } = useAuth();
  const [subscription, setSubscription] = useState<SubscriptionResponse | null>(null);
  const [quota, setQuota] = useState<{ videos_watched_today: number; daily_limit: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [checkingOut, setCheckingOut] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [sub, q] = await Promise.all([
        getSubscription(apiBaseUrl, accessToken),
        getWatchQuota(apiBaseUrl, accessToken).catch(() => null),
      ]);
      setSubscription(sub);
      setQuota(q);
    } catch (e: unknown) {
      if (e instanceof Error && "status" in e && (e as { status: number }).status === 401) {
        await refreshSession().catch(() => undefined);
      }
    }
  }, [apiBaseUrl, accessToken, refreshSession]);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      void (async () => {
        setLoading(true);
        await load();
        if (!cancelled) setLoading(false);
      })();
      return () => { cancelled = true; };
    }, [load])
  );

  const handleSubscribe = async () => {
    setCheckingOut(true);
    setError(null);
    try {
      const res = await createCheckoutSession(apiBaseUrl, accessToken);
      if (res.url) {
        await Linking.openURL(res.url);
      } else {
        setError(res.error ?? "Could not create checkout session");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start checkout");
    } finally {
      setCheckingOut(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.textSecondary} size="large" />
      </View>
    );
  }

  const isPremium = subscription?.status === "active" && subscription?.current_period_end
    ? new Date(subscription.current_period_end) > new Date()
    : false;

  return (
    <ScrollView style={styles.root} contentContainerStyle={{ flexGrow: 1 }}>
      <View style={styles.card}>
        <AppText variant="headline" style={{ textAlign: "center" }}>
          {isPremium ? "Premium" : "EventFlow Premium"}
        </AppText>

        {isPremium ? (
          <View style={styles.statusBadge}>
            <AppText style={styles.statusText}>Active</AppText>
          </View>
        ) : null}

        <AppText style={styles.price}>
          {isPremium ? "Active" : (quota ? `$${((quota.daily_limit * 3) / 100).toFixed(2)}` : "$4.99")}
        </AppText>
        <AppText style={styles.period}>per month</AppText>

        <View style={{ gap: 12, marginTop: 16 }}>
          <AppText style={styles.feature}>✓ Unlimited video watching</AppText>
          <AppText style={styles.feature}>✓ No daily quota</AppText>
          <AppText style={styles.feature}>✓ Full access to Calendar</AppText>
          <AppText style={styles.feature}>✓ Support independent businesses</AppText>
        </View>

        {error ? <AppText style={styles.error}>{error}</AppText> : null}

        {isPremium ? (
          <AppText tone="secondary" style={{ textAlign: "center", marginTop: 16 }}>
            {subscription?.current_period_end
              ? `Renews ${new Date(subscription.current_period_end).toLocaleDateString()}`
              : "No expiration"}
          </AppText>
        ) : (
          <Button
            label={checkingOut ? "Opening checkout..." : "Subscribe"}
            variant="filled"
            size="lg"
            fullWidth
            loading={checkingOut}
            disabled={checkingOut}
            onPress={handleSubscribe}
          />
        )}
      </View>
    </ScrollView>
  );
}
