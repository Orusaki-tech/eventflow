import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect } from "@react-navigation/native";
import * as Clipboard from "expo-clipboard";
import * as Linking from "expo-linking";
import {
  confirmDraft,
  EventflowApiError,
  getDraft,
  parseDraftFromImageToken,
  type EventDraftDetail,
} from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { InstagramCarouselSourceGallery } from "../components/InstagramCarouselSourceGallery";
import { LinkThumbnail } from "../components/LinkThumbnail";
import { PosterAssetImage } from "../components/PosterAssetImage";
import { isInstagramPostUrl } from "../lib/normalizeSharePayload";
import {
  getDraftPosterAssetId,
  getDraftSourceUrl,
  saveDraftPosterAssetId,
  saveEventPosterAssetId,
  saveEventSourceUrl,
} from "../lib/thumbnail";
import { describeEventStartTime } from "../lib/eventDateTime";
import type { RootStackParamList } from "../navigation/types";
import { AppText, Button, Card } from "../design/components";
import { tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";

type Props = NativeStackScreenProps<RootStackParamList, "DraftDetail">;

export function DraftDetailScreen({ navigation, route }: Props) {
  const { draftId } = route.params;
  const initialSharedUrl = route.params.sharedUrl;
  const { accessToken, apiBaseUrl, refreshSession } = useAuth();
  const [draft, setDraft] = useState<EventDraftDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState(false);
  const [sharedUrl, setSharedUrl] = useState<string | null>(initialSharedUrl ?? null);
  const [posterAssetId, setPosterAssetId] = useState<string | null>(null);
  const [parsingPoster, setParsingPoster] = useState(false);
  const [igCarouselMulti, setIgCarouselMulti] = useState(false);
  const parsedOnce = React.useRef(false);
  const { colors } = useTheme();
  const styles = useThemedStyles((c) => ({
    center: { flex: 1, backgroundColor: c.bg, justifyContent: "center" as const, alignItems: "center" as const },
    root: { flex: 1, backgroundColor: c.bg },
    content: { padding: tokens.spacing[20], gap: tokens.spacing[16], flexGrow: 1 },
    linkRow: {
      flexDirection: "row" as const,
      alignItems: "center" as const,
      gap: tokens.spacing[12],
    },
    linkTextCol: { flex: 1, minWidth: 0 },
    linkText: { textDecorationLine: "underline" as const },
    linkBtnRow: { flexDirection: "row" as const, gap: tokens.spacing[8] },
    linkBtnWrap: { minWidth: 84 },
    card: {
      padding: tokens.spacing[20],
    },
    title: { marginBottom: tokens.spacing[8] },
    meta: { marginBottom: tokens.spacing[4] },
    venue: { marginBottom: tokens.spacing[12] },
    conf: {},
    parsing: { marginTop: tokens.spacing[12] },
    cardPressRow: {
      flexDirection: "row" as const,
      alignItems: "flex-start" as const,
      justifyContent: "space-between" as const,
      gap: tokens.spacing[12],
    },
    cardMainCol: { flex: 1, minWidth: 0 },
    editIconHit: { padding: tokens.spacing[8], marginTop: -tokens.spacing[4] },
  }));

  useEffect(() => {
    if (sharedUrl) return;
    let cancelled = false;
    void (async () => {
      const u = await getDraftSourceUrl(draftId);
      if (!cancelled && u) setSharedUrl(u);
    })();
    return () => {
      cancelled = true;
    };
  }, [draftId, sharedUrl]);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      void (async () => {
        void getDraftPosterAssetId(draftId).then((pid) => {
          if (!cancelled) setPosterAssetId(pid ?? null);
        });
        setLoading(true);
        try {
          const d = await getDraft(apiBaseUrl, accessToken, draftId);
          if (!cancelled) setDraft(d);
        } catch {
          if (!cancelled) setDraft(null);
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [apiBaseUrl, accessToken, draftId])
  );

  const runPosterParseFromToken = useCallback(
    (imageToken: string) => {
      if (parsedOnce.current) return;
      parsedOnce.current = true;
      setParsingPoster(true);
      void (async () => {
        try {
          const updated = await parseDraftFromImageToken(apiBaseUrl, accessToken, draftId, imageToken);
          setDraft(updated);
          if (updated.poster_asset_id) {
            await saveDraftPosterAssetId(draftId, updated.poster_asset_id);
            setPosterAssetId(updated.poster_asset_id);
          }
        } catch {
          /* best-effort; keep existing text-derived draft */
        } finally {
          setParsingPoster(false);
        }
      })();
    },
    [apiBaseUrl, accessToken, draftId]
  );

  const linkThumbnailFallback = useMemo(() => {
    if (!sharedUrl) return <></>;
    return (
      <LinkThumbnail
        apiBaseUrl={apiBaseUrl}
        sharedUrl={sharedUrl}
        onImageTokenReady={(imageToken) => runPosterParseFromToken(imageToken)}
      />
    );
  }, [apiBaseUrl, sharedUrl, runPosterParseFromToken]);

  const onConfirm = async () => {
    setConfirming(true);
    try {
      const res = await confirmDraft(apiBaseUrl, accessToken, draftId);
      if (sharedUrl) {
        try {
          await saveEventSourceUrl(res.event_id, sharedUrl);
        } catch {
          /* non-fatal */
        }
      }
      if (posterAssetId) {
        try {
          await saveEventPosterAssetId(res.event_id, posterAssetId);
        } catch {
          /* non-fatal */
        }
      }
      navigation.replace("Confirmed", { eventId: res.event_id, sharedUrl: sharedUrl ?? undefined });
    } catch (e: unknown) {
      if (e instanceof EventflowApiError && e.status === 401) await refreshSession();
      Alert.alert("Could not confirm", e instanceof Error ? e.message : String(e));
    } finally {
      setConfirming(false);
    }
  };

  if (loading || !draft) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.textSecondary} />
      </View>
    );
  }

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content}>
      {posterAssetId && !igCarouselMulti ? (
        <PosterAssetImage apiBaseUrl={apiBaseUrl} posterAssetId={posterAssetId} height={200} />
      ) : null}
      {sharedUrl && isInstagramPostUrl(sharedUrl) ? (
        <InstagramCarouselSourceGallery
          apiBaseUrl={apiBaseUrl}
          accessToken={accessToken}
          sharedUrl={sharedUrl}
          height={200}
          onMultiSlideChange={setIgCarouselMulti}
          onPosterSlideTokenReady={runPosterParseFromToken}
          refreshSession={refreshSession}
          renderFallback={() => linkThumbnailFallback}
        />
      ) : sharedUrl ? (
        linkThumbnailFallback
      ) : null}

      {sharedUrl ? (
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
      ) : null}

      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Edit title, time, venue, and price"
        onPress={() => navigation.navigate("DraftEdit", { draftId, sharedUrl: sharedUrl ?? undefined })}
      >
        {({ pressed }) => (
          <Card style={[styles.card, pressed ? { opacity: 0.92 } : null]}>
            <View style={styles.cardPressRow}>
              <View style={styles.cardMainCol}>
                <AppText variant="headline" style={styles.title}>
                  {draft.title}
                </AppText>
                <AppText tone="secondary" style={styles.meta}>
                  {describeEventStartTime(draft.start_time)}
                </AppText>
                <AppText tone="secondary" style={styles.venue}>
                  {draft.venue}
                </AppText>
              </View>
              <View style={styles.editIconHit} pointerEvents="none">
                <Ionicons name="create-outline" size={22} color={colors.textSecondary} />
              </View>
            </View>
            <AppText tone="secondary" style={styles.meta}>
              {draft.price?.trim() ? draft.price.trim() : "No price"}
            </AppText>
            <AppText tone="tertiary" style={styles.conf}>
              Confidence {(draft.confidence_score * 100).toFixed(0)}%
            </AppText>
            {parsingPoster ? (
              <AppText variant="labelSmall" tone="secondary" style={styles.parsing}>
                Reading poster…
              </AppText>
            ) : null}
          </Card>
        )}
      </Pressable>

      <Button
        label="Confirm event"
        loading={confirming}
        disabled={!draft.start_time?.trim()}
        onPress={() => void onConfirm()}
        fullWidth
      />
      <Button
        label="Edit details"
        variant="text"
        onPress={() => navigation.navigate("DraftEdit", { draftId, sharedUrl: sharedUrl ?? undefined })}
        fullWidth
      />
    </ScrollView>
  );
}
