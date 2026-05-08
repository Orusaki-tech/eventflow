import * as Location from "expo-location";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Alert, Image, Pressable, View } from "react-native";
import * as Clipboard from "expo-clipboard";
import * as Linking from "expo-linking";
import { EventflowApiError, getEta, patchEventVisibility, resolveVenueForEvent, type EtaResponse, type UpcomingEventRow } from "../api/eventflow";
import { AppText, Button, Chip } from "../design/components";
import { pressedOpacityStyle, tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";
import { formatFriendlyEventDateTime } from "../lib/eventDateTime";
import {
  buildPosterAssetUri,
  buildResolvedImageUri,
  buildThumbnailUri,
  getEventPosterAssetId,
  getEventSourceUrl,
} from "../lib/thumbnail";
import { navigationRef } from "../navigation/navigationRef";
import { EventCard } from "./EventCard";

/** Minimal fields shared by today/upcoming list rows for this card. */
export type EventListCardRow = Pick<UpcomingEventRow, "id" | "title" | "start_time" | "venue" | "price"> & {
  user_id?: string;
};

export type TodayCardActionsContext = {
  accessToken: string | null;
  venueId: string | null;
  visibility: "private" | "public";
};

type Props = {
  apiBaseUrl: string;
  item: EventListCardRow;
  /** Label above the title (e.g. `Today` vs `Upcoming`). */
  kickerLabel?: string;
  /** When set with `kickerLabel` `"Today"`, shows venue and visibility chips in the header row. */
  todayContext?: TodayCardActionsContext;
  onPress?: (args: { eventId: string; sharedUrl: string | null }) => void;
};

function fmtDistance(meters: number) {
  if (meters < 1000) return `${meters} m`;
  return `${(meters / 1000).toFixed(1)} km`;
}

function fmtDuration(seconds: number) {
  const mins = Math.round(seconds / 60);
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${h}h ${m}m`;
}

export function UpcomingEventCard({
  apiBaseUrl,
  item,
  kickerLabel = "Upcoming",
  todayContext,
  onPress,
}: Props) {
  const { colors } = useTheme();
  const styles = useThemedStyles((c) => ({
    kicker: { letterSpacing: 0.2 },
    title: { fontSize: 17, fontWeight: "800", color: c.textPrimary },
    meta: { fontSize: 14 },
    venue: { fontSize: 15 },
    previewRow: {
      marginTop: tokens.spacing[8],
      flexDirection: "row" as const,
      justifyContent: "flex-end" as const,
      width: "100%" as const,
    },
    thumbWrap: {
      position: "relative" as const,
      width: 76,
      height: 76,
      borderRadius: tokens.radii.sm,
      overflow: "hidden",
      backgroundColor: c.surface2,
      borderWidth: 1,
      borderColor: c.border,
      alignItems: "center" as const,
      justifyContent: "center" as const,
    },
    thumbImg: { width: "100%", height: "100%" },
    thumbLoading: {
      position: "absolute" as const,
      left: 0,
      right: 0,
      top: 0,
      bottom: 0,
      alignItems: "center" as const,
      justifyContent: "center" as const,
    },
    linkRow: { marginTop: tokens.spacing[12], flexDirection: "row" as const, alignItems: "center" as const, gap: tokens.spacing[12] },
    linkTextCol: { flex: 1, minWidth: 0 },
    linkText: { textDecorationLine: "underline" as const },
    linkBtnRow: { flexDirection: "row" as const, gap: tokens.spacing[8] },
    linkBtnWrap: { minWidth: 84 },
    todayKickerRow: {
      flexDirection: "row" as const,
      flexWrap: "wrap" as const,
      alignItems: "center" as const,
      gap: tokens.spacing[8],
    },
    todayChipsWrap: {
      flexDirection: "row" as const,
      flexWrap: "wrap" as const,
      alignItems: "center" as const,
      gap: tokens.spacing[8],
      flexShrink: 1,
    },
    etaBox: {
      padding: tokens.spacing[12],
      borderRadius: tokens.radii.sm,
      backgroundColor: c.surface2,
    },
    etaText: { fontWeight: "700" },
  }));

  const showTodayTools = kickerLabel === "Today" && todayContext != null;

  const [visibility, setVisibility] = useState(todayContext?.visibility ?? "private");
  const [venueId, setVenueId] = useState<string | null>(todayContext?.venueId ?? null);
  const [eta, setEta] = useState<EtaResponse | null>(null);
  const [etaLoading, setEtaLoading] = useState(false);
  const [resolvingVenue, setResolvingVenue] = useState(false);

  useEffect(() => {
    if (!todayContext) return;
    setVisibility(todayContext.visibility);
    setVenueId(todayContext.venueId);
  }, [todayContext?.visibility, todayContext?.venueId]);

  const [sharedUrl, setSharedUrl] = useState<string | null>(null);
  const [posterAssetId, setPosterAssetId] = useState<string | null>(null);
  const [imageToken, setImageToken] = useState<string | null>(null);
  const [imgLoading, setImgLoading] = useState(false);
  const [imgFailed, setImgFailed] = useState(false);
  const thumbFallbackOnceRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const [url, poster] = await Promise.all([
        getEventSourceUrl(item.id),
        getEventPosterAssetId(item.id),
      ]);
      if (!cancelled) {
        setSharedUrl(url);
        setPosterAssetId(poster);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [item.id]);

  useEffect(() => {
    if (!sharedUrl || posterAssetId) return;
    let cancelled = false;
    setImageToken(null);
    void (async () => {
      try {
        const base = apiBaseUrl.replace(/\/$/, "");
        const res = await fetch(`${base}/api/v1/media/resolve-image`, {
          method: "POST",
          headers: { Accept: "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ url: sharedUrl }),
        });
        if (!res.ok) return;
        const j = (await res.json()) as { image_token?: string };
        if (!cancelled && j.image_token) setImageToken(j.image_token);
      } catch {
        /* fall back to /media/thumbnail URI below */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, sharedUrl, posterAssetId]);

  useEffect(() => {
    setImgFailed(false);
    thumbFallbackOnceRef.current = false;
  }, [item.id, posterAssetId, sharedUrl]);

  const fallbackUri = useMemo(
    () => (sharedUrl ? buildThumbnailUri(apiBaseUrl, sharedUrl) : null),
    [apiBaseUrl, sharedUrl]
  );
  const resolvedUri = useMemo(
    () => (imageToken ? buildResolvedImageUri(apiBaseUrl, imageToken) : null),
    [apiBaseUrl, imageToken]
  );
  const posterUri = useMemo(
    () => (posterAssetId ? buildPosterAssetUri(apiBaseUrl, posterAssetId) : null),
    [apiBaseUrl, posterAssetId]
  );

  const previewUri = posterUri ?? resolvedUri ?? fallbackUri;
  const showPreviewSlot = !!(posterAssetId || sharedUrl);

  const meta = useMemo(() => formatFriendlyEventDateTime(item.start_time), [item.start_time]);

  const toggleVisibility = async () => {
    if (!todayContext?.accessToken) return;
    const next = visibility === "private" ? "public" : "private";
    try {
      await patchEventVisibility(apiBaseUrl, todayContext.accessToken, item.id, next);
      setVisibility(next);
    } catch (e: unknown) {
      Alert.alert("Update failed", e instanceof Error ? e.message : String(e));
    }
  };

  const openManualVenue = () => {
    if (!navigationRef.isReady()) return;
    navigationRef.navigate("ManualVenue", {
      eventId: item.id,
      venueHint: item.venue ?? null,
    });
  };

  const onResolveVenue = async () => {
    if (!todayContext?.accessToken) return;
    setResolvingVenue(true);
    try {
      const res = await resolveVenueForEvent(apiBaseUrl, todayContext.accessToken, item.id, item.venue);
      setVenueId(res.venue.id);
      Alert.alert("Venue updated", "Venue coordinates saved. You can calculate ETA now.");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      const noMatch = e instanceof EventflowApiError && e.status === 404;
      Alert.alert(noMatch ? "No matching venue" : "Could not resolve venue", msg, [
        { text: "Close", style: "cancel" },
        ...(noMatch ? [{ text: "Add manually", onPress: () => openManualVenue() }] : []),
      ]);
    } finally {
      setResolvingVenue(false);
    }
  };

  const onGetEta = async () => {
    if (!todayContext?.accessToken) return;
    setEtaLoading(true);
    try {
      const perm = await Location.requestForegroundPermissionsAsync();
      if (perm.status !== "granted") {
        Alert.alert("Location needed", "Enable location permission to calculate ETA.");
        return;
      }
      const pos = await Location.getCurrentPositionAsync({});
      const out = await getEta(apiBaseUrl, todayContext.accessToken, item.id, pos.coords.latitude, pos.coords.longitude);
      setEta(out);
    } catch (e: unknown) {
      Alert.alert("ETA failed", e instanceof Error ? e.message : String(e));
    } finally {
      setEtaLoading(false);
    }
  };

  const venueResolved = venueId != null && venueId !== "";

  const previewBlock =
    showPreviewSlot ? (
      <View style={styles.previewRow}>
        <View style={styles.thumbWrap}>
          {previewUri && !imgFailed ? (
            <Image
              key={previewUri}
              source={{ uri: previewUri }}
              style={styles.thumbImg}
              resizeMode="cover"
              accessibilityIgnoresInvertColors
              onLoadStart={() => setImgLoading(true)}
              onLoadEnd={() => setImgLoading(false)}
              onError={() => {
                setImgLoading(false);
                if (posterAssetId) {
                  setImgFailed(true);
                  return;
                }
                if (imageToken != null && !thumbFallbackOnceRef.current) {
                  thumbFallbackOnceRef.current = true;
                  setImageToken(null);
                  setImgFailed(false);
                  return;
                }
                setImgFailed(true);
              }}
            />
          ) : null}
          {imgLoading && previewUri && !imgFailed ? (
            <View style={styles.thumbLoading}>
              <ActivityIndicator size="small" color={colors.textSecondary} />
            </View>
          ) : null}
        </View>
      </View>
    ) : null;

  const linksBlock =
    sharedUrl ? (
      <View style={styles.linkRow}>
        <View style={styles.linkTextCol}>
          <AppText variant="labelSmall" tone="tertiary">
            Source link
          </AppText>
          <AppText tone="secondary" style={styles.linkText} numberOfLines={1}>
            {sharedUrl}
          </AppText>
        </View>
        <View style={styles.linkBtnRow}>
          <View style={styles.linkBtnWrap}>
            <Button label="Copy" variant="outline" size="md" onPress={() => void Clipboard.setStringAsync(sharedUrl)} />
          </View>
          <View style={styles.linkBtnWrap}>
            <Button label="Open" variant="outline" size="md" onPress={() => void Linking.openURL(sharedUrl)} />
          </View>
        </View>
      </View>
    ) : null;

  const authReady = Boolean(todayContext?.accessToken);

  return (
    <EventCard>
      {showTodayTools && todayContext ? (
        <>
          <View style={styles.todayKickerRow}>
            <AppText variant="labelSmall" tone="tertiary" style={styles.kicker}>
              Today
            </AppText>
            <View style={styles.todayChipsWrap}>
              <Chip
                label={visibility === "public" ? "Public" : "Private"}
                disabled={!authReady}
                onPress={() => void toggleVisibility()}
              />
              {!venueResolved ? (
                <>
                  <Chip
                    label={resolvingVenue ? "Resolving…" : "Resolve venue"}
                    disabled={resolvingVenue || !authReady}
                    onPress={() => void onResolveVenue()}
                  />
                  <Chip label="Add venue" disabled={!authReady} onPress={() => openManualVenue()} />
                </>
              ) : (
                <Chip
                  label={etaLoading ? "Calculating…" : "Get ETA"}
                  disabled={etaLoading || !authReady}
                  onPress={() => void onGetEta()}
                />
              )}
            </View>
          </View>
          {eta ? (
            <View style={styles.etaBox}>
              <AppText variant="label" style={styles.etaText}>
                {fmtDistance(eta.distance_meters)} • {fmtDuration(eta.duration_in_traffic_seconds ?? eta.duration_seconds)}
              </AppText>
            </View>
          ) : null}
        </>
      ) : (
        <AppText variant="labelSmall" tone="tertiary" style={styles.kicker}>
          {kickerLabel}
        </AppText>
      )}

      <Pressable
        disabled={!onPress}
        accessibilityRole={onPress ? "button" : undefined}
        onPress={() => onPress?.({ eventId: item.id, sharedUrl })}
        style={({ pressed }) => [pressedOpacityStyle(pressed), { gap: 10 }]}
      >
        <AppText variant="title" style={styles.title}>
          {item.title}
        </AppText>
        <AppText tone="secondary" style={styles.meta}>
          {meta}
        </AppText>
        <AppText tone="secondary" style={styles.venue}>
          {item.venue}
        </AppText>
        <AppText tone={item.price?.trim() ? "secondary" : "tertiary"} style={styles.meta}>
          {item.price?.trim() ? item.price.trim() : "No price"}
        </AppText>
        {previewBlock}
        {linksBlock}
      </Pressable>
    </EventCard>
  );
}
