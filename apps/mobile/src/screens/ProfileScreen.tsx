import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useCallback, useMemo, useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, TextInput, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import {
  EventflowApiError,
  getBudgetSummary,
  getMyProfile,
  getUserPreferences,
  patchUserPreferences,
  upsertMyProfile,
  type BudgetSummary,
} from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { AppText, Button, Card } from "../design/components";
import { pressedOpacityStyle, tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";
import type { ProfileStackParamList } from "../navigation/types";
import { navigationRef } from "../navigation/navigationRef";

type Props = NativeStackScreenProps<ProfileStackParamList, "ProfileHome">;

function fmtUsdMinor(minor: number): string {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(minor / 100);
}

function monthLabel(year: number, month: number) {
  return new Date(year, month - 1, 1).toLocaleString(undefined, { month: "long", year: "numeric" });
}

function budgetAccentColor(band: BudgetSummary["band"], dangerHex: string): string | undefined {
  if (band === "under") return "#22C55E";
  if (band === "tight") return "#F59E0B";
  if (band === "over") return dangerHex;
  return undefined;
}

export function ProfileScreen({ navigation }: Props) {
  const { colors } = useTheme();
  const styles = useThemedStyles((c) => ({
    root: { flex: 1, backgroundColor: c.bg },
    content: { padding: tokens.spacing[20], gap: tokens.spacing[16], flexGrow: 1 },
    card: { padding: tokens.spacing[16], gap: tokens.spacing[10] },
    email: {},
    center: { paddingVertical: 24, alignItems: "center" as const },
    monthRow: {
      flexDirection: "row" as const,
      alignItems: "center" as const,
      justifyContent: "space-between" as const,
      gap: tokens.spacing[12],
    },
    monthBtn: { paddingVertical: 8, paddingHorizontal: 12, borderRadius: tokens.radii.sm, borderWidth: 1, borderColor: c.border },
    totalLine: { fontSize: 22, fontWeight: "800" as const },
    hint: {},
    input: {
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: tokens.radii.sm,
      padding: tokens.spacing[12],
      color: c.textPrimary,
      backgroundColor: c.surface1,
    },
  }));
  const { session, signOut, accessToken, apiBaseUrl, refreshSession } = useAuth();
  const email = session?.user?.email ?? null;

  const tzOffsetMinutes = useMemo(() => -new Date().getTimezoneOffset(), []);
  const anchor = useMemo(() => new Date(), []);
  const [year, setYear] = useState(anchor.getFullYear());
  const [month, setMonth] = useState(anchor.getMonth() + 1);

  const [displayName, setDisplayName] = useState("");
  const [isPublic, setIsPublic] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [budgetDollarsInput, setBudgetDollarsInput] = useState("");
  const [summary, setSummary] = useState<BudgetSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingBudget, setSavingBudget] = useState(false);

  const shiftMonth = (delta: number) => {
    const d = new Date(year, month - 1 + delta, 1);
    setYear(d.getFullYear());
    setMonth(d.getMonth() + 1);
  };

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      void (async () => {
        setLoading(true);
        try {
          const [prefs, sum, profile] = await Promise.all([
            getUserPreferences(apiBaseUrl, accessToken),
            getBudgetSummary(apiBaseUrl, accessToken, {
              year,
              month,
              tzOffsetMinutes: tzOffsetMinutes,
            }),
            getMyProfile(apiBaseUrl, accessToken).catch(() => null),
          ]);
          if (cancelled) return;
          if (prefs.monthly_budget_minor_units != null) {
            setBudgetDollarsInput(String(prefs.monthly_budget_minor_units / 100));
          } else {
            setBudgetDollarsInput("");
          }
          if (profile) {
            setDisplayName(profile.display_name === "User" ? "" : profile.display_name);
            setIsPublic(profile.is_public);
          }
          setSummary(sum);
        } catch (e: unknown) {
          if (e instanceof EventflowApiError && e.status === 401) await refreshSession().catch(() => undefined);
          if (!cancelled) setSummary(null);
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [accessToken, apiBaseUrl, month, refreshSession, year, tzOffsetMinutes])
  );

  const onSignOut = () => {
    Alert.alert("Sign out?", "You can sign back in anytime.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Sign out",
        style: "destructive",
        onPress: () => {
          signOut().then(() => {
            if (navigationRef.isReady()) {
              navigationRef.reset({ index: 0, routes: [{ name: "Auth" }] });
            }
          }).catch(() => undefined);
        },
      },
    ]);
  };

  const saveProfile = async () => {
    const name = displayName.trim();
    if (!name) {
      Alert.alert("Display name required", "Enter your display name so others can find you.");
      return;
    }
    setSavingProfile(true);
    try {
      await upsertMyProfile(apiBaseUrl, accessToken, { display_name: name, is_public: isPublic });
    } catch (e: unknown) {
      Alert.alert("Save failed", e instanceof Error ? e.message : String(e));
    } finally {
      setSavingProfile(false);
    }
  };

  const saveBudget = async () => {
    const trimmed = budgetDollarsInput.trim();
    let minor: number | null = null;
    if (trimmed.length) {
      const n = Number.parseFloat(trimmed.replace(/,/g, ""));
      if (!Number.isFinite(n) || n < 0) {
        Alert.alert("Invalid budget", "Enter a non-negative number (USD), or leave blank to clear.");
        return;
      }
      minor = Math.round(n * 100);
    }
    setSavingBudget(true);
    try {
      await patchUserPreferences(apiBaseUrl, accessToken, { monthly_budget_minor_units: minor });
      const sum = await getBudgetSummary(apiBaseUrl, accessToken, {
        year,
        month,
        tzOffsetMinutes: tzOffsetMinutes,
      });
      setSummary(sum);
    } catch (e: unknown) {
      if (e instanceof EventflowApiError && e.status === 401) await refreshSession();
      Alert.alert("Save failed", e instanceof Error ? e.message : String(e));
    } finally {
      setSavingBudget(false);
    }
  };

  const accent =
    summary && summary.budget_minor_units != null && summary.budget_minor_units > 0
      ? budgetAccentColor(summary.band, colors.danger)
      : colors.textSecondary;

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <Card style={styles.card}>
        <AppText variant="title">Account</AppText>
        <AppText tone="secondary" style={styles.email}>
          {email ?? "Signed in"}
        </AppText>
      </Card>

      <Card style={styles.card}>
        <AppText variant="title">Profile</AppText>
        <AppText variant="labelSmall" tone="tertiary" style={styles.hint}>
          Your display name lets others find you in search.
        </AppText>
        <TextInput
          style={styles.input}
          value={displayName}
          onChangeText={setDisplayName}
          placeholder="Your display name"
          placeholderTextColor={colors.textTertiary}
          autoCapitalize="words"
        />
        <Pressable
          onPress={() => setIsPublic((p) => !p)}
          style={({ pressed }) => [pressedOpacityStyle(pressed)]}
        >
          <AppText variant="labelSmall" style={{ color: isPublic ? "#4CAF50" : colors.textTertiary }}>
            {isPublic ? "Public profile (visible to everyone)" : "Private profile (hidden from search)"}
          </AppText>
        </Pressable>
        <Button label={savingProfile ? "Saving…" : "Save profile"} variant="outline" loading={savingProfile} onPress={() => void saveProfile()} fullWidth />
      </Card>

      <Card style={styles.card}>
        <AppText variant="title">Promoter</AppText>
        <AppText variant="labelSmall" tone="tertiary" style={styles.hint}>
          Create a listing business profile and open the billing demo checkout stub.
        </AppText>
        <Button label="Listing business" variant="outline" onPress={() => navigation.navigate("BusinessProfile")} fullWidth />
      </Card>

      <Card style={styles.card}>
        <AppText variant="title">Event budget</AppText>
        <AppText variant="labelSmall" tone="tertiary" style={styles.hint}>
          Totals use ticket prices on your own events. Parses dollar amounts from each price field (best effort).
        </AppText>

        <View style={styles.monthRow}>
          <Pressable accessibilityLabel="Previous month" style={({ pressed }) => [styles.monthBtn, pressedOpacityStyle(pressed)]} onPress={() => shiftMonth(-1)}>
            <AppText variant="label">←</AppText>
          </Pressable>
          <AppText variant="title" style={{ flex: 1, textAlign: "center" }}>
            {monthLabel(year, month)}
          </AppText>
          <Pressable accessibilityLabel="Next month" style={({ pressed }) => [styles.monthBtn, pressedOpacityStyle(pressed)]} onPress={() => shiftMonth(1)}>
            <AppText variant="label">→</AppText>
          </Pressable>
        </View>

        {loading ? (
          <View style={styles.center}>
            <ActivityIndicator color={colors.textSecondary} />
          </View>
        ) : summary ? (
          <>
            <AppText variant="labelSmall" tone="tertiary">
              Estimated spend (priced lines only)
            </AppText>
            <AppText style={[styles.totalLine, accent ? { color: accent } : {}]}>{fmtUsdMinor(summary.spent_minor_units)}</AppText>
            <AppText tone="secondary">
              Budget cap:{" "}
              {summary.budget_minor_units != null && summary.budget_minor_units > 0
                ? fmtUsdMinor(summary.budget_minor_units)
                : "Not set"}
            </AppText>
            {summary.budget_minor_units != null && summary.budget_minor_units > 0 ? (
              <AppText variant="labelSmall" tone="secondary">
                {summary.band === "under" && "Comfortably under budget"}
                {summary.band === "tight" && "Getting tight — you're near your cap"}
                {summary.band === "over" && "Over budget for this month"}
              </AppText>
            ) : (
              <AppText variant="labelSmall" tone="tertiary">
                Set a monthly cap below to color‑code your spending (green / amber / red).
              </AppText>
            )}
            <AppText variant="labelSmall" tone="tertiary">
              {summary.events_total_count} events this month · {summary.priced_events_count} with a parsed price ·{" "}
              {summary.unpriced_events_count} without
            </AppText>
          </>
        ) : (
          <AppText tone="tertiary">Budget insights require the API database (configure DB_URL).</AppText>
        )}

        <AppText variant="labelSmall" tone="tertiary">
          Monthly cap (USD)
        </AppText>
        <TextInput
          style={styles.input}
          value={budgetDollarsInput}
          onChangeText={setBudgetDollarsInput}
          keyboardType="decimal-pad"
          placeholder="e.g. 500 (leave empty to clear)"
          placeholderTextColor={colors.textTertiary}
        />
        <Button label={savingBudget ? "Saving…" : "Save budget"} variant="outline" loading={savingBudget} onPress={() => void saveBudget()} fullWidth />
      </Card>

      <Button label="Sign out" variant="outline" onPress={onSignOut} fullWidth />
    </ScrollView>
  );
}
