import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import * as ImagePicker from "expo-image-picker";
import React, { useCallback, useState } from "react";
import { Alert, TextInput, View } from "react-native";
import { EventflowApiError, sharePoster } from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { saveDraftPosterAssetId, saveDraftSourceUrl } from "../lib/thumbnail";
import type { RootStackParamList } from "../navigation/types";
import { AppText, Button } from "../design/components";
import { tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";

type Props = NativeStackScreenProps<RootStackParamList, "PosterImport">;

export function PosterImportScreen({ navigation }: Props) {
  const { colors } = useTheme();
  const styles = useThemedStyles((c) => ({
    root: { flex: 1, backgroundColor: c.bg, padding: tokens.spacing[20], gap: tokens.spacing[16] },
    title: {},
    body: { lineHeight: 22 },
    field: { gap: 8, marginTop: 4 },
    label: { fontWeight: "700" },
    input: {
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: 12,
      paddingVertical: 12,
      paddingHorizontal: 12,
      color: c.textPrimary,
      backgroundColor: c.surface1,
    },
  }));
  const { accessToken, apiBaseUrl, refreshSession } = useAuth();
  const [busy, setBusy] = useState(false);
  const [sourceUrl, setSourceUrl] = useState("");

  const pickAndUpload = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    try {
      const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!perm.granted) {
        Alert.alert("Permission needed", "Please allow photo library access to upload a poster screenshot.");
        return;
      }
      const res = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true, // native crop UI
        aspect: [3, 4],
        quality: 1,
      });
      if (res.canceled || !res.assets?.length) return;
      const asset = res.assets[0];
      const uri = asset.uri;
      const mimeType = asset.mimeType ?? "image/jpeg";

      const out = await sharePoster(apiBaseUrl, accessToken, {
        uri,
        mimeType,
        sourceUrl: sourceUrl.trim() || undefined,
      });
      try {
        await saveDraftPosterAssetId(out.draft_id, out.poster_asset_id);
      } catch {
        /* non-fatal */
      }
      if (sourceUrl.trim()) {
        try {
          await saveDraftSourceUrl(out.draft_id, sourceUrl.trim());
        } catch {
          /* non-fatal */
        }
      }
      navigation.replace("DraftDetail", {
        draftId: out.draft_id,
        sharedUrl: sourceUrl.trim() || undefined,
      });
    } catch (e: unknown) {
      // If auth expired, retry once after refresh.
      if (e instanceof EventflowApiError && e.status === 401) {
        await refreshSession().catch(() => undefined);
      }
      const msg = e instanceof Error ? e.message : String(e);
      Alert.alert("Upload failed", msg);
    } finally {
      setBusy(false);
    }
  }, [accessToken, apiBaseUrl, busy, navigation, refreshSession, sourceUrl]);

  return (
    <View style={styles.root}>
      <AppText variant="headline" style={styles.title}>
        Upload a poster screenshot
      </AppText>
      <AppText tone="secondary" style={styles.body}>
        Crop tightly around the event poster. We use the poster image to recognize repeats and avoid re-parsing.
      </AppText>

      <View style={styles.field}>
        <AppText variant="labelSmall" tone="tertiary" style={styles.label}>
          Original post link (optional)
        </AppText>
        <TextInput
          value={sourceUrl}
          onChangeText={setSourceUrl}
          placeholder="https://…"
          placeholderTextColor={colors.textTertiary}
          autoCapitalize="none"
          autoCorrect={false}
          style={styles.input}
        />
      </View>

      <Button
        label={busy ? "Uploading…" : "Choose image & crop"}
        loading={busy}
        onPress={() => void pickAndUpload()}
        fullWidth
      />
    </View>
  );
}

