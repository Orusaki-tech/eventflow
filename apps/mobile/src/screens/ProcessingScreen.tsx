import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Alert, View } from "react-native";
import {
  EventflowApiError,
  postInstagramCarouselDrafts,
  postShareFromNormalized,
} from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { isInstagramPostUrl, normalizeSharePayload } from "../lib/normalizeSharePayload";
import { saveDraftPosterAssetId, saveDraftSourceUrl } from "../lib/thumbnail";
import type { RootStackParamList } from "../navigation/types";
import { LinkThumbnail } from "../components/LinkThumbnail";
import { AppText } from "../design/components";
import { useThemedStyles } from "../design/useThemedStyles";

type Props = NativeStackScreenProps<RootStackParamList, "Processing">;

const STAGES = ["Reading your link…", "Extracting time and place…", "Almost there…"];

function withImgIndex(url: string, index: number): string {
  try {
    const u = new URL(url);
    u.searchParams.set("img_index", String(index));
    return u.toString();
  } catch {
    return url;
  }
}

export function ProcessingScreen({ navigation, route }: Props) {
  const styles = useThemedStyles((c) => ({
    root: {
      flex: 1,
      backgroundColor: c.bg,
      justifyContent: "center" as const,
      alignItems: "center" as const,
      padding: 24,
      gap: 14,
    },
    logo: { marginBottom: 8 },
    queue: { marginBottom: 24 },
    stage: { fontSize: 16, textAlign: "center" as const },
  }));
  const { accessToken, apiBaseUrl, refreshSession } = useAuth();
  const rawText = route.params?.rawText?.trim() ?? "";
  const carouselSlideIndices = route.params?.carouselSlideIndices;
  const [stage, setStage] = useState(0);

  const normalized = useMemo(() => normalizeSharePayload(rawText), [rawText]);
  const sharedUrl = normalized.mode === "url" ? normalized.url : undefined;
  const started = useRef(false);

  useEffect(() => {
    if (!rawText) {
      Alert.alert("Nothing to import", "Go back and paste a link or share again.");
      navigation.goBack();
      return;
    }

    const t = setInterval(() => {
      setStage((s) => Math.min(s + 1, STAGES.length - 1));
    }, 900);
    return () => clearInterval(t);
  }, [rawText, navigation]);

  useEffect(() => {
    if (!rawText || started.current) return;
    started.current = true;
    let cancelled = false;
    void (async () => {
      try {
        const useCarousel =
          normalized.mode === "url" &&
          !!normalized.url &&
          isInstagramPostUrl(normalized.url);

        const carouselRes = useCarousel
          ? await postInstagramCarouselDrafts(apiBaseUrl, accessToken, {
              url: normalized.url!,
              carousel_slide_indices: carouselSlideIndices,
            })
          : null;

        const drafts = carouselRes ? carouselRes.drafts : [await postShareFromNormalized(apiBaseUrl, accessToken, normalized)];
        const slidesUsed = carouselRes?.slides_used;

        if (cancelled) return;

        const first = drafts[0];
        if (!first) {
          Alert.alert("Import failed", "No drafts were created.");
          navigation.goBack();
          return;
        }

        if (drafts.length > 1) {
          const slidesLabel =
            slidesUsed && slidesUsed.length === drafts.length ? slidesUsed.join(", ") : String(drafts.length);
          Alert.alert(
            "Carousel imported",
            `Created ${drafts.length} drafts from slides ${slidesLabel}.`
          );
        }

        if (sharedUrl) {
          try {
            for (let i = 0; i < drafts.length; i++) {
              const d = drafts[i]!;
              const slideNum =
                slidesUsed && slidesUsed.length === drafts.length ? slidesUsed[i]! : drafts.length > 1 ? i + 1 : undefined;
              const perUrl =
                slideNum !== undefined ? withImgIndex(sharedUrl, slideNum) : sharedUrl;
              await saveDraftSourceUrl(d.draft_id, perUrl);
              if (d.poster_asset_id) {
                await saveDraftPosterAssetId(d.draft_id, d.poster_asset_id);
              }
            }
          } catch {
            /* non-fatal */
          }
        }

        navigation.replace("DraftDetail", { draftId: first.draft_id, sharedUrl });
      } catch (e: unknown) {
        if (e instanceof EventflowApiError && e.status === 401) {
          await refreshSession();
        }
        if (!cancelled) {
          Alert.alert(
            "Import failed",
            e instanceof EventflowApiError ? e.message : e instanceof Error ? e.message : String(e)
          );
          navigation.goBack();
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [
    rawText,
    accessToken,
    apiBaseUrl,
    normalized,
    navigation,
    refreshSession,
    sharedUrl,
    carouselSlideIndices,
  ]);

  return (
    <View style={styles.root}>
      <AppText variant="display" style={styles.logo}>
        EventFlow
      </AppText>
      <AppText variant="title" tone="secondary" style={styles.queue}>
        Skipping queue
      </AppText>
      {sharedUrl ? <LinkThumbnail apiBaseUrl={apiBaseUrl} sharedUrl={sharedUrl} height={160} /> : null}
      <AppText tone="secondary" style={styles.stage}>
        {STAGES[stage]}
      </AppText>
    </View>
  );
}
