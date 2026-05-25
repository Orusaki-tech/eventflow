import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, Image, Linking, Pressable, ScrollView, View } from "react-native";
import {
  type BusinessProfileResponse,
  deleteFollowBusiness,
  getBusinessProfile,
  getFollowBusiness,
  postFollowBusiness,
} from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { AppText, Button, Card } from "../design/components";
import { pressedOpacityStyle, tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";
import { formatFriendlyEventDateTime } from "../lib/eventDateTime";
import { whatsAppMeUrlFromE164 } from "../lib/whatsappLink";
import type { RootStackParamList } from "../navigation/types";
import { navigationRef } from "../navigation/navigationRef";

type Props = NativeStackScreenProps<RootStackParamList, "BusinessProfileView">;

export function BusinessProfileViewScreen({ route }: Props) {
  const { businessId } = route.params;
  const { colors } = useTheme();
  const { accessToken, refreshSession, apiBaseUrl } = useAuth();
  const styles = useThemedStyles((c) => ({
    root: { flex: 1, backgroundColor: c.bg },
    scrollContent: { padding: tokens.spacing[16], gap: tokens.spacing[16], paddingBottom: 40 },
    center: { paddingVertical: 24, alignItems: "center" as const },
    header: { alignItems: "center" as const, gap: tokens.spacing[8], paddingVertical: tokens.spacing[16] },
    logo: { width: 80, height: 80, borderRadius: 40, backgroundColor: c.surface1 },
    infoRow: { flexDirection: "row" as const, alignItems: "center" as const, gap: tokens.spacing[4] },
    section: { gap: tokens.spacing[8] },
    listingCard: { padding: tokens.spacing[12], gap: tokens.spacing[8] },
    poster: { width: "100%" as const, height: 140, borderRadius: tokens.radii.sm, backgroundColor: c.surface1 },
    verifiedBadge: { fontSize: 11, color: c.textTertiary },
  }));

  const [profile, setProfile] = useState<BusinessProfileResponse | null>(null);
  const [following, setFollowing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [followBusy, setFollowBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const p = await getBusinessProfile(apiBaseUrl, businessId);
        if (!cancelled) setProfile(p);
      } catch (e: unknown) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [businessId, apiBaseUrl]);

  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    void (async () => {
      try {
        const { following: f } = await getFollowBusiness(apiBaseUrl, accessToken, businessId);
        if (!cancelled) setFollowing(f);
      } catch { /* not critical */ }
    })();
    return () => { cancelled = true; };
  }, [accessToken, businessId, apiBaseUrl]);

  const toggleFollow = async () => {
    if (!accessToken) return;
    setFollowBusy(true);
    try {
      if (following) {
        await deleteFollowBusiness(apiBaseUrl, accessToken, businessId);
        setFollowing(false);
        setProfile((p) => p ? { ...p, follower_count: Math.max(0, p.follower_count - 1) } : p);
      } else {
        await postFollowBusiness(apiBaseUrl, accessToken, businessId);
        setFollowing(true);
        setProfile((p) => p ? { ...p, follower_count: p.follower_count + 1 } : p);
      }
    } catch {
      try { await refreshSession(); } catch { /* give up */ }
    } finally {
      setFollowBusy(false);
    }
  };

  if (loading) {
    return (
      <View style={[styles.root, styles.center]}>
        <ActivityIndicator size="large" color={colors.textPrimary} />
      </View>
    );
  }

  if (err || !profile) {
    return (
      <View style={[styles.root, styles.center]}>
        <AppText style={{ color: colors.danger }}>{err ?? "Business not found"}</AppText>
      </View>
    );
  }

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.scrollContent}>
      <Card style={styles.header}>
        {profile.logo_url ? (
          <Image source={{ uri: profile.logo_url }} style={styles.logo} />
        ) : (
          <View style={[styles.logo, { alignItems: "center", justifyContent: "center" }]}>
            <AppText style={{ fontSize: 28 }}>{profile.name.charAt(0).toUpperCase()}</AppText>
          </View>
        )}
        <AppText variant="headline">{profile.name}</AppText>
        {profile.verified ? <AppText style={styles.verifiedBadge}>✓ Verified</AppText> : null}
        <View style={styles.infoRow}>
          <AppText variant="labelSmall" tone="tertiary">{profile.follower_count} follower{profile.follower_count !== 1 ? "s" : ""}</AppText>
          <AppText variant="labelSmall" tone="tertiary">·</AppText>
          <AppText variant="labelSmall" tone="tertiary">{profile.listing_count} listing{profile.listing_count !== 1 ? "s" : ""}</AppText>
        </View>
        {profile.description ? <AppText style={{ textAlign: "center" }}>{profile.description}</AppText> : null}
        {accessToken ? (
          <Button
            label={following ? "Following" : "Follow"}
            variant={following ? "outline" : "filled"}
            onPress={toggleFollow}
            disabled={followBusy}
          />
        ) : null}
      </Card>

      {profile.website || profile.contact_email || profile.whatsapp_e164 ? (
        <Card style={styles.section}>
          <AppText variant="title">Contact</AppText>
          {profile.website ? (
            <Pressable accessibilityLabel="Open website" style={({ pressed }) => pressedOpacityStyle(pressed)} onPress={() => Linking.openURL(profile.website!)}>
              <AppText style={{ color: colors.textPrimary }}>🌐 {profile.website}</AppText>
            </Pressable>
          ) : null}
          {profile.contact_email ? <AppText>✉ {profile.contact_email}</AppText> : null}
          {(() => {
            const wa = profile.whatsapp_e164;
            if (!wa) return null;
            return (
              <Pressable accessibilityLabel="Open WhatsApp" style={({ pressed }) => pressedOpacityStyle(pressed)} onPress={() => {
                const url = whatsAppMeUrlFromE164(wa);
                if (url) Linking.openURL(url);
              }}>
                <AppText style={{ color: colors.textPrimary }}>💬 Chat on WhatsApp</AppText>
              </Pressable>
            );
          })()}
        </Card>
      ) : null}

      <AppText variant="title">Upcoming listings</AppText>

      {profile.listings.length === 0 ? (
        <AppText tone="tertiary">No upcoming listings from this business.</AppText>
      ) : (
        profile.listings.map((l) => (
          <Pressable
            accessibilityLabel="View listing"
            key={l.community_event_id}
            style={({ pressed }) => pressedOpacityStyle(pressed)}
            onPress={() =>
              navigationRef.navigate("CommunityListingDetail", {
                communityEventId: l.community_event_id,
                organizerUserId: null,
                title: l.title,
                start_time: l.start_time,
                venue: l.venue,
                whatsapp_e164: l.whatsapp_e164,
                business_id: profile.business_id,
              })
            }
          >
            <Card style={styles.listingCard}>
              {l.poster_image_uri ? (
                <Image source={{ uri: l.poster_image_uri }} style={styles.poster} resizeMode="cover" />
              ) : null}
              <AppText variant="body">{l.title}</AppText>
              <AppText variant="labelSmall">{formatFriendlyEventDateTime(l.start_time)}</AppText>
              <AppText variant="labelSmall" tone="tertiary">{l.venue}</AppText>
            </Card>
          </Pressable>
        ))
      )}
    </ScrollView>
  );
}
