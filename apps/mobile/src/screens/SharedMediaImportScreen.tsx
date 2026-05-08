import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useCallback, useMemo, useState } from "react";
import { Alert, ScrollView, View } from "react-native";
import * as FileSystem from "expo-file-system";
import { EventflowApiError, shareMedia } from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { AppText, Button } from "../design/components";
import { tokens } from "../design/tokens";
import { useThemedStyles } from "../design/useThemedStyles";
import type { RootStackParamList } from "../navigation/types";

type Props = NativeStackScreenProps<RootStackParamList, "SharedMediaImport">;

type SharedItem = { uri: string; mimeType: string; filename?: string };
type SharedPayload = { kind: "media"; capturedAt?: number; text?: string; items: SharedItem[] };

function parsePayload(raw: string): SharedPayload | null {
  try {
    const j: unknown = JSON.parse(raw);
    if (!j || typeof j !== "object") return null;
    const o = j as Record<string, unknown>;
    if (o.kind !== "media") return null;
    const items = o.items;
    if (!Array.isArray(items)) return null;
    const mapped: SharedItem[] = [];
    for (const it of items) {
      if (!it || typeof it !== "object") continue;
      const r = it as Record<string, unknown>;
      const uri = typeof r.uri === "string" ? r.uri : "";
      const mimeType = typeof r.mimeType === "string" ? r.mimeType : "";
      const filename = typeof r.filename === "string" ? r.filename : undefined;
      if (!uri || !mimeType) continue;
      mapped.push({ uri, mimeType, filename });
    }
    if (mapped.length === 0) return null;
    return {
      kind: "media",
      capturedAt: typeof o.capturedAt === "number" ? o.capturedAt : undefined,
      text: typeof o.text === "string" ? o.text : undefined,
      items: mapped,
    };
  } catch {
    return null;
  }
}

function ensureFileUri(uri: string): string {
  if (/^file:\/\//i.test(uri)) return uri;
  // Android native handoff writes absolute paths; fetch FormData expects file:// URIs.
  if (uri.startsWith("/")) return `file://${uri}`;
  return uri;
}

async function safeDeleteFileUri(uri: string): Promise<void> {
  try {
    const u = ensureFileUri(uri);
    const info = await FileSystem.getInfoAsync(u);
    if (!info.exists) return;
    await FileSystem.deleteAsync(u, { idempotent: true });
  } catch {
    /* best-effort cleanup */
  }
}

export function SharedMediaImportScreen({ navigation, route }: Props) {
  const styles = useThemedStyles((c) => ({
    root: { flex: 1, backgroundColor: c.bg },
    content: { padding: tokens.spacing[20], gap: tokens.spacing[12] },
    card: { padding: 14, borderRadius: tokens.radii.md, borderWidth: 1, borderColor: c.border, backgroundColor: c.surface1 },
    row: { gap: 4 },
    mono: { fontFamily: "System" },
  }));
  const { apiBaseUrl, accessToken, refreshSession } = useAuth();
  const payload = useMemo(() => parsePayload(route.params.payloadJson), [route.params.payloadJson]);
  const [busy, setBusy] = useState(false);

  const upload = useCallback(async () => {
    if (!payload) {
      Alert.alert("Nothing to import", "No media found in share payload.");
      navigation.goBack();
      return;
    }
    if (busy) return;
    setBusy(true);
    try {
      const created = [];
      for (const item of payload.items) {
        const uri = ensureFileUri(item.uri);
        const out = await shareMedia(apiBaseUrl, accessToken, {
          uri,
          mimeType: item.mimeType,
          filename: item.filename,
          sourceText: payload.text,
        });
        created.push(out);
        // Best-effort: once uploaded, remove local copied share file to avoid storage buildup.
        await safeDeleteFileUri(uri);
      }
      const first = created[0];
      if (!first) {
        Alert.alert("Import failed", "No drafts were created.");
        navigation.goBack();
        return;
      }
      if (created.length > 1) {
        Alert.alert("Imported", `Created ${created.length} drafts from shared media.`);
      }
      navigation.replace("DraftDetail", { draftId: first.draft_id, sharedUrl: payload.text });
    } catch (e: unknown) {
      if (e instanceof EventflowApiError && e.status === 401) {
        await refreshSession().catch(() => undefined);
      }
      const msg = e instanceof EventflowApiError ? e.message : e instanceof Error ? e.message : String(e);
      Alert.alert("Import failed", msg);
    } finally {
      setBusy(false);
    }
  }, [accessToken, apiBaseUrl, busy, navigation, payload, refreshSession]);

  if (!payload) {
    return (
      <ScrollView style={styles.root} contentContainerStyle={styles.content}>
        <AppText variant="title">Couldn't read shared media</AppText>
        <AppText tone="secondary">Try sharing again, or use “Upload poster screenshot”.</AppText>
        <Button label="Go back" onPress={() => navigation.goBack()} fullWidth />
      </ScrollView>
    );
  }

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content}>
      <AppText variant="title">Import shared media</AppText>
      <AppText tone="secondary">
        We’ll upload the files you shared and create drafts. This works without logging into social apps.
      </AppText>

      {payload.items.map((it, idx) => (
        <View key={`${it.uri}-${idx}`} style={styles.card}>
          <View style={styles.row}>
            <AppText variant="label">Item {idx + 1}</AppText>
            <AppText tone="secondary">{it.mimeType}</AppText>
            <AppText tone="tertiary" numberOfLines={1} style={styles.mono}>
              {it.filename ?? it.uri}
            </AppText>
          </View>
        </View>
      ))}

      <Button label={busy ? "Importing…" : `Import (${payload.items.length})`} loading={busy} onPress={() => void upload()} fullWidth />
    </ScrollView>
  );
}

