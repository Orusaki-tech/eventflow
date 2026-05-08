import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useFocusEffect } from "@react-navigation/native";
import React, { useCallback, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, View } from "react-native";
import { listDrafts, type DraftListRow } from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import * as Clipboard from "expo-clipboard";
import * as Linking from "expo-linking";
import type { CaptureStackParamList } from "../navigation/types";
import { navigationRef } from "../navigation/navigationRef";
import { EventCard } from "../components/EventCard";
import { AppText, Button, ProfileIconButton } from "../design/components";
import { pressedOpacityStyle, tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";
import { describeEventStartTime } from "../lib/eventDateTime";
import { getDraftSourceUrl } from "../lib/thumbnail";

type Props = NativeStackScreenProps<CaptureStackParamList, "CaptureHome">;

export function CaptureScreen({ navigation }: Props) {
  const { colors } = useTheme();
  const styles = useThemedStyles((c) => ({
    root: { flex: 1, backgroundColor: c.bg },
    content: { padding: tokens.spacing[20], gap: tokens.spacing[16], flexGrow: 1 },
    title: { marginBottom: tokens.spacing[4] },
    lead: { lineHeight: 22 },
    hint: { lineHeight: 18 },
    sectionTitle: { marginTop: tokens.spacing[8] },
    center: { paddingVertical: 8, alignItems: "center" as const, justifyContent: "center" as const },
    list: { gap: 10 },
    draftCard: { padding: 14, gap: 6 },
    kicker: { letterSpacing: 0.2 },
    draftTitle: {},
    draftMeta: {},
    linkRow: { marginTop: 6, flexDirection: "row" as const, alignItems: "center" as const, gap: 10 },
    linkTextCol: { flex: 1, minWidth: 0 },
    linkText: { textDecorationLine: "underline" as const },
    linkBtn: {
      paddingVertical: 8,
      paddingHorizontal: 12,
      borderRadius: tokens.radii.sm,
      borderWidth: 1,
      borderColor: c.border,
      backgroundColor: c.surface1,
    },
    empty: { lineHeight: 20 },
  }));
  const { apiBaseUrl, accessToken } = useAuth();
  const [loading, setLoading] = useState(true);
  const [drafts, setDrafts] = useState<DraftListRow[]>([]);
  const [draftSourceUrls, setDraftSourceUrls] = useState<Record<string, string>>({});

  React.useLayoutEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <ProfileIconButton onPress={() => navigation.getParent()?.navigate("Profile")} />
      ),
    });
  }, [navigation]);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      void (async () => {
        setLoading(true);
        try {
          const d = await listDrafts(apiBaseUrl, accessToken, { status: "pending", limit: 20 });
          if (cancelled) return;
          setDrafts(d);

          // Best-effort: load cached "pasted link" per draft from AsyncStorage.
          const pairs = await Promise.all(d.map(async (row) => [row.draft_id, await getDraftSourceUrl(row.draft_id)] as const));
          if (cancelled) return;
          const next: Record<string, string> = {};
          for (const [id, url] of pairs) {
            if (url) next[id] = url;
          }
          setDraftSourceUrls(next);
        } catch {
          if (!cancelled) {
            setDrafts([]);
            setDraftSourceUrls({});
          }
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [apiBaseUrl, accessToken])
  );

  const uniqueDrafts = useMemo(() => {
    const seen = new Set<string>();
    const out: DraftListRow[] = [];
    for (const d of drafts) {
      if (seen.has(d.draft_id)) continue;
      seen.add(d.draft_id);
      out.push(d);
    }
    return out;
  }, [drafts]);

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content}>
      <AppText variant="title" style={styles.title}>
        Capture
      </AppText>
      <AppText tone="secondary" style={styles.lead}>
        Paste a link, share from another app, or upload a poster screenshot. We turn it into a draft you can confirm.
      </AppText>

      <Button
        label="Paste a link"
        onPress={() => {
          if (navigationRef.isReady()) navigationRef.navigate("ImportLink");
        }}
        fullWidth
      />
      <Button
        label="Upload poster screenshot"
        variant="outline"
        onPress={() => {
          if (navigationRef.isReady()) navigationRef.navigate("PosterImport");
        }}
        fullWidth
      />

      <AppText variant="labelSmall" tone="tertiary" style={styles.hint}>
        Tip: from TikTok or Instagram, use Share and pick EventFlow (dev build).
      </AppText>

      <AppText variant="title" style={styles.sectionTitle}>
        Drafts
      </AppText>
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.textSecondary} />
        </View>
      ) : uniqueDrafts.length ? (
        <View style={styles.list}>
          {uniqueDrafts.map((d) => (
            <Pressable
              key={d.draft_id}
              style={({ pressed }) => pressedOpacityStyle(pressed)}
              onPress={() => {
                if (navigationRef.isReady()) navigationRef.navigate("DraftDetail", { draftId: d.draft_id });
              }}
            >
              <EventCard style={styles.draftCard}>
                <AppText variant="labelSmall" tone="tertiary" style={styles.kicker}>
                  Draft{d.confidence_score < 0.7 ? " • Low confidence" : ""}
                </AppText>
                <AppText variant="title" style={styles.draftTitle}>
                  {d.title}
                </AppText>
                <AppText tone="secondary" style={styles.draftMeta}>
                  {describeEventStartTime(d.start_time)}
                </AppText>
                <AppText tone="secondary" style={styles.draftMeta}>
                  {d.venue}
                </AppText>
                <AppText tone="secondary" style={styles.draftMeta}>
                  {d.price?.trim() ? d.price.trim() : "No price"}
                </AppText>

                {draftSourceUrls[d.draft_id] ? (
                  <View style={styles.linkRow}>
                    <View style={styles.linkTextCol}>
                      <AppText variant="labelSmall" tone="tertiary">
                        Source link
                      </AppText>
                      <AppText tone="secondary" style={styles.linkText} numberOfLines={1}>
                        {draftSourceUrls[d.draft_id]}
                      </AppText>
                    </View>

                    <Pressable
                      style={({ pressed }) => [styles.linkBtn, pressedOpacityStyle(pressed)]}
                      onPress={async () => {
                        const url = draftSourceUrls[d.draft_id];
                        if (!url) return;
                        await Clipboard.setStringAsync(url);
                      }}
                    >
                      <AppText variant="label" tone="secondary">
                        Copy
                      </AppText>
                    </Pressable>

                    <Pressable
                      style={({ pressed }) => [styles.linkBtn, pressedOpacityStyle(pressed)]}
                      onPress={async () => {
                        const url = draftSourceUrls[d.draft_id];
                        if (!url) return;
                        await Linking.openURL(url);
                      }}
                    >
                      <AppText variant="label" tone="secondary">
                        Open
                      </AppText>
                    </Pressable>
                  </View>
                ) : null}
              </EventCard>
            </Pressable>
          ))}
        </View>
      ) : (
        <AppText tone="tertiary" style={styles.empty}>
          No drafts yet.
        </AppText>
      )}
    </ScrollView>
  );
}
