import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import * as ImagePicker from "expo-image-picker";
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Alert, ScrollView, TextInput, View } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { EventflowApiError, getDraft, patchDraft, sharePoster } from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { InstagramCarouselSourceGallery } from "../components/InstagramCarouselSourceGallery";
import { LinkThumbnail } from "../components/LinkThumbnail";
import { PosterAssetImage } from "../components/PosterAssetImage";
import { isInstagramPostUrl } from "../lib/normalizeSharePayload";
import { getDraftPosterAssetId, getDraftSourceUrl, saveDraftPosterAssetId } from "../lib/thumbnail";
import type { RootStackParamList } from "../navigation/types";
import { EventDateTimePickerField } from "../components/EventDateTimePickerField";
import { AppText, Button } from "../design/components";
import { tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";

type Props = NativeStackScreenProps<RootStackParamList, "DraftEdit">;

export function DraftEditScreen({ navigation, route }: Props) {
  const { colors } = useTheme();
  const styles = useThemedStyles((c) => ({
    center: { flex: 1, backgroundColor: c.bg, justifyContent: "center" as const, alignItems: "center" as const },
    root: { flex: 1, backgroundColor: c.bg },
    content: { padding: tokens.spacing[20], paddingBottom: tokens.spacing[32], gap: tokens.spacing[8], flexGrow: 1 },
    previewBlock: { gap: tokens.spacing[8] },
    label: { marginTop: tokens.spacing[8] },
    input: {
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: 10,
      padding: 12,
      color: c.textPrimary,
      backgroundColor: c.surface1,
    },
  }));
  const { draftId } = route.params;
  const initialSharedUrl = route.params.sharedUrl;
  const { accessToken, apiBaseUrl, refreshSession } = useAuth();
  const [loading, setLoading] = useState(true);
  const [title, setTitle] = useState("");
  const [venue, setVenue] = useState("");
  const [price, setPrice] = useState("");
  const [startIso, setStartIso] = useState("");
  const [saving, setSaving] = useState(false);
  const [sharedUrl, setSharedUrl] = useState<string | null>(initialSharedUrl ?? null);
  const [posterAssetId, setPosterAssetId] = useState<string | null>(null);
  const [posterBusy, setPosterBusy] = useState(false);
  const [igCarouselMulti, setIgCarouselMulti] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const pid = await getDraftPosterAssetId(draftId);
      if (!cancelled && pid) setPosterAssetId(pid);
    })();
    return () => {
      cancelled = true;
    };
  }, [draftId]);

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
        setLoading(true);
        try {
          const d = await getDraft(apiBaseUrl, accessToken, draftId);
          if (!cancelled) {
            setTitle(d.title);
            setVenue(d.venue);
            setPrice(d.price?.trim() ?? "");
            setStartIso(d.start_time ?? "");
          }
        } catch {
          if (!cancelled) Alert.alert("Error", "Could not load draft");
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [apiBaseUrl, accessToken, draftId])
  );

  const pickPosterScreenshot = useCallback(async () => {
    if (posterBusy) return;
    setPosterBusy(true);
    try {
      const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!perm.granted) {
        Alert.alert("Permission needed", "Please allow photo library access to add a screenshot.");
        return;
      }
      const res = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
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
        draftId,
        sourceUrl: sharedUrl?.trim() || undefined,
      });
      try {
        await saveDraftPosterAssetId(draftId, out.poster_asset_id);
      } catch {
        /* non-fatal */
      }
      setPosterAssetId(out.poster_asset_id);
      setTitle(out.title);
      setVenue(out.venue);
      setPrice(out.price?.trim() ?? "");
      setStartIso(out.start_time ?? "");
    } catch (e: unknown) {
      if (e instanceof EventflowApiError && e.status === 401) await refreshSession();
      Alert.alert("Screenshot upload failed", e instanceof Error ? e.message : String(e));
    } finally {
      setPosterBusy(false);
    }
  }, [accessToken, apiBaseUrl, draftId, posterBusy, refreshSession, sharedUrl]);

  const save = async () => {
    setSaving(true);
    try {
      await patchDraft(apiBaseUrl, accessToken, draftId, {
        title: title.trim() || undefined,
        venue: venue.trim() || undefined,
        start_time: startIso.trim() || undefined,
        price: price.trim() ? price.trim() : null,
      });
      navigation.navigate("DraftDetail", { draftId });
    } catch (e: unknown) {
      if (e instanceof EventflowApiError && e.status === 401) await refreshSession();
      Alert.alert("Save failed", e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.textSecondary} />
      </View>
    );
  }

  const addScreenshotBtn = (
    <Button
      label="Add screenshot"
      variant="outline"
      size="md"
      loading={posterBusy}
      onPress={() => void pickPosterScreenshot()}
      fullWidth
    />
  );

  const replaceScreenshotBtn = (
    <Button
      label="Replace screenshot"
      variant="outline"
      size="md"
      loading={posterBusy}
      onPress={() => void pickPosterScreenshot()}
      fullWidth
    />
  );

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <View style={styles.previewBlock}>
        {sharedUrl && isInstagramPostUrl(sharedUrl) ? (
          <>
            <InstagramCarouselSourceGallery
              apiBaseUrl={apiBaseUrl}
              accessToken={accessToken}
              sharedUrl={sharedUrl}
              height={160}
              refreshSession={refreshSession}
              onMultiSlideChange={setIgCarouselMulti}
              renderFallback={() =>
                posterAssetId ? (
                  <>
                    <PosterAssetImage apiBaseUrl={apiBaseUrl} posterAssetId={posterAssetId} height={160} />
                    {replaceScreenshotBtn}
                  </>
                ) : (
                  <LinkThumbnail
                    apiBaseUrl={apiBaseUrl}
                    sharedUrl={sharedUrl}
                    height={160}
                    placeholderAccessory={addScreenshotBtn}
                    successAccessory={
                      <Button
                        label="Add screenshot"
                        variant="outline"
                        size="md"
                        loading={posterBusy}
                        onPress={() => void pickPosterScreenshot()}
                        fullWidth
                      />
                    }
                  />
                )
              }
            />
            {igCarouselMulti ? replaceScreenshotBtn : null}
          </>
        ) : posterAssetId ? (
          <>
            <PosterAssetImage apiBaseUrl={apiBaseUrl} posterAssetId={posterAssetId} height={160} />
            {replaceScreenshotBtn}
          </>
        ) : sharedUrl ? (
          <LinkThumbnail
            apiBaseUrl={apiBaseUrl}
            sharedUrl={sharedUrl}
            height={160}
            placeholderAccessory={addScreenshotBtn}
            successAccessory={
              <Button
                label="Add screenshot"
                variant="outline"
                size="md"
                loading={posterBusy}
                onPress={() => void pickPosterScreenshot()}
                fullWidth
              />
            }
          />
        ) : (
          <>
            <AppText variant="labelSmall" tone="tertiary">
              No link thumbnail yet — add a poster screenshot to improve recognition.
            </AppText>
            {addScreenshotBtn}
          </>
        )}
      </View>
      <AppText variant="labelSmall" tone="tertiary" style={styles.label}>
        Title
      </AppText>
      <TextInput style={styles.input} value={title} onChangeText={setTitle} />
      <AppText variant="labelSmall" tone="tertiary" style={styles.label}>
        Admission / price
      </AppText>
      <TextInput
        style={styles.input}
        value={price}
        onChangeText={setPrice}
        placeholder="e.g. Free entry, $25 — from poster"
        placeholderTextColor={colors.textTertiary}
      />
      <AppText variant="labelSmall" tone="tertiary" style={styles.label}>
        Venue
      </AppText>
      <TextInput style={styles.input} value={venue} onChangeText={setVenue} />
      <EventDateTimePickerField valueIso={startIso} onChangeIso={setStartIso} />
      <Button label="Save" loading={saving} onPress={() => void save()} fullWidth />
    </ScrollView>
  );
}
