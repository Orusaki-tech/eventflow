import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import { useHeaderHeight } from "@react-navigation/elements";
import * as Location from "expo-location";
import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import {
  attachManualVenueToEvent,
  autocompletePlaces,
  EventflowApiError,
  getPlaceDetails,
  type PlaceAutocompletePrediction,
} from "../api/eventflow";
import { useAuth } from "../auth/AuthContext";
import { VenuePinMap, type VenuePinMapRef } from "../components/VenuePinMap";
import { AppText, Button } from "../design/components";
import { pressedOpacityStyle, tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";
import type { RootStackParamList } from "../navigation/types";

type Props = NativeStackScreenProps<RootStackParamList, "ManualVenue">;

export function ManualVenueScreen({ navigation, route }: Props) {
  const params = route.params;
  const eventId = params?.eventId;
  const venueHint = params?.venueHint ?? null;

  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const headerHeight = useHeaderHeight();
  const { apiBaseUrl, accessToken } = useAuth();

  const styles = useThemedStyles((c) => ({
    root: { flex: 1, backgroundColor: c.bg },
    scrollContent: {
      paddingHorizontal: tokens.spacing[16],
      paddingTop: tokens.spacing[12],
      paddingBottom: tokens.spacing[24],
      gap: tokens.spacing[12],
      flexGrow: 1,
    },
    lead: { lineHeight: 22 },
    modalFieldLabel: { marginBottom: 4 },
    modalInput: {
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: tokens.radii.sm,
      paddingHorizontal: tokens.spacing[12],
      paddingVertical: tokens.spacing[12],
      color: c.textPrimary,
      backgroundColor: c.surface2,
      fontSize: 16,
    },
    modalSuggestLabelRow: {
      flexDirection: "row" as const,
      alignItems: "center" as const,
      justifyContent: "space-between" as const,
      gap: tokens.spacing[8],
    },
    suggestListWrap: {
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: tokens.radii.sm,
      backgroundColor: c.surface2,
      overflow: "hidden" as const,
    },
    suggestionRow: {
      paddingVertical: tokens.spacing[12],
      paddingHorizontal: tokens.spacing[12],
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: c.divider,
    },
    searchStatusRow: {
      flexDirection: "row" as const,
      alignItems: "center" as const,
      gap: tokens.spacing[8],
      marginTop: tokens.spacing[8],
      minHeight: 22,
    },
    suggestHint: { marginTop: tokens.spacing[8], lineHeight: 20 },
    suggestError: { marginTop: tokens.spacing[8], lineHeight: 20 },
    modalCoords: { fontSize: 13 },
    actions: { gap: tokens.spacing[8], marginTop: tokens.spacing[8] },
  }));

  const [manualName, setManualName] = useState(() => (venueHint?.trim() ? venueHint.trim() : ""));
  const [manualAddress, setManualAddress] = useState("");
  const [manualLat, setManualLat] = useState<number | null>(null);
  const [manualLng, setManualLng] = useState<number | null>(null);
  const [manualSaving, setManualSaving] = useState(false);
  const [locLoading, setLocLoading] = useState(false);
  const venueMapRef = useRef<VenuePinMapRef>(null);
  const lockAddressSuggestionsRef = useRef(false);
  const [searchBias, setSearchBias] = useState<{ lat: number; lng: number } | null>(null);
  const [addressSuggestions, setAddressSuggestions] = useState<PlaceAutocompletePrediction[]>([]);
  const [addressSuggestFetching, setAddressSuggestFetching] = useState(false);
  const [addressSuggestDebouncing, setAddressSuggestDebouncing] = useState(false);
  const [addressSuggestError, setAddressSuggestError] = useState<string | null>(null);
  /** After choosing a suggestion, hide “empty results” until the user edits the field again. */
  const [suppressSuggestEmptyHint, setSuppressSuggestEmptyHint] = useState(false);

  useLayoutEffect(() => {
    if (!eventId) navigation.goBack();
  }, [eventId, navigation]);

  useEffect(() => {
    let cancelled = false;
    void Location.getLastKnownPositionAsync({}).then((p) => {
      if (cancelled || !p?.coords) return;
      setSearchBias({ lat: p.coords.latitude, lng: p.coords.longitude });
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!accessToken || !eventId) return;
    const q = manualAddress.trim();
    if (q.length < 2) {
      setAddressSuggestions([]);
      setAddressSuggestFetching(false);
      setAddressSuggestDebouncing(false);
      setAddressSuggestError(null);
      setSuppressSuggestEmptyHint(false);
      return;
    }
    if (lockAddressSuggestionsRef.current) {
      setAddressSuggestFetching(false);
      setAddressSuggestDebouncing(false);
      return;
    }

    setAddressSuggestDebouncing(true);
    setAddressSuggestError(null);

    const ac = new AbortController();
    const debounceMs = 280;
    const t = setTimeout(() => {
      setAddressSuggestDebouncing(false);
      setAddressSuggestFetching(true);
      void (async () => {
        try {
          const res = await autocompletePlaces(apiBaseUrl, accessToken, {
            input: q,
            nearLat: searchBias?.lat,
            nearLng: searchBias?.lng,
            signal: ac.signal,
          });
          if (!ac.signal.aborted) {
            setAddressSuggestions(res.predictions ?? []);
            setAddressSuggestError(null);
          }
        } catch (e: unknown) {
          if (!ac.signal.aborted) {
            setAddressSuggestions([]);
            const msg =
              e instanceof EventflowApiError
                ? e.message
                : e instanceof Error
                  ? e.message
                  : "Could not load suggestions.";
            setAddressSuggestError(msg);
          }
        } finally {
          if (!ac.signal.aborted) setAddressSuggestFetching(false);
        }
      })();
    }, debounceMs);

    return () => {
      clearTimeout(t);
      ac.abort();
      setAddressSuggestDebouncing(false);
    };
  }, [manualAddress, apiBaseUrl, accessToken, searchBias, eventId]);

  const fillManualLocation = async () => {
    setLocLoading(true);
    try {
      const perm = await Location.requestForegroundPermissionsAsync();
      if (perm.status !== "granted") {
        Alert.alert("Location needed", "Allow location to pin this venue on the map.");
        return;
      }
      const pos = await Location.getCurrentPositionAsync({});
      const lat = pos.coords.latitude;
      const lng = pos.coords.longitude;
      setManualLat(lat);
      setManualLng(lng);
      venueMapRef.current?.animateTo(lat, lng);
    } catch (e: unknown) {
      Alert.alert("Location failed", e instanceof Error ? e.message : String(e));
    } finally {
      setLocLoading(false);
    }
  };

  const submitManualVenue = async () => {
    if (!accessToken || !eventId) return;
    const name = manualName.trim();
    if (!name) {
      Alert.alert("Name required", "Enter a venue name.");
      return;
    }
    if (manualLat == null || manualLng == null) {
      Alert.alert(
        "Pin required",
        "Pick an address from search suggestions, tap the map to drop a pin, drag to adjust, or use Use current location."
      );
      return;
    }
    setManualSaving(true);
    try {
      await attachManualVenueToEvent(apiBaseUrl, accessToken, eventId, {
        name,
        address: manualAddress.trim() || undefined,
        lat: manualLat,
        lng: manualLng,
      });
      lockAddressSuggestionsRef.current = false;
      setAddressSuggestions([]);
      navigation.goBack();
      Alert.alert("Venue saved", "You can get directions with Get ETA.");
    } catch (e: unknown) {
      Alert.alert("Could not save venue", e instanceof Error ? e.message : String(e));
    } finally {
      setManualSaving(false);
    }
  };

  const pickAddressSuggestion = async (pred: PlaceAutocompletePrediction) => {
    if (!accessToken) return;
    Keyboard.dismiss();
    lockAddressSuggestionsRef.current = true;
    setSuppressSuggestEmptyHint(true);
    setAddressSuggestions([]);
    setAddressSuggestFetching(true);
    try {
      const det = await getPlaceDetails(apiBaseUrl, accessToken, pred.place_id);
      setManualAddress(det.formatted_address ?? det.name);
      setManualName((prev) => (prev.trim() ? prev : det.name));
      setManualLat(det.lat);
      setManualLng(det.lng);
      venueMapRef.current?.animateTo(det.lat, det.lng);
    } catch (e: unknown) {
      lockAddressSuggestionsRef.current = false;
      Alert.alert("Could not load place", e instanceof Error ? e.message : String(e));
    } finally {
      setAddressSuggestFetching(false);
    }
  };

  if (!eventId) return null;

  const addressQuery = manualAddress.trim();
  const addressSearchBusy = addressSuggestDebouncing || addressSuggestFetching;
  const showSuggestEmpty =
    !addressSearchBusy &&
    !addressSuggestError &&
    addressQuery.length >= 2 &&
    addressSuggestions.length === 0 &&
    !suppressSuggestEmptyHint;

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={headerHeight}
    >
      <ScrollView
        style={{ flex: 1 }}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        showsVerticalScrollIndicator
        contentContainerStyle={[styles.scrollContent, { paddingBottom: tokens.spacing[24] + insets.bottom }]}
      >
        <AppText tone="secondary" style={styles.lead}>
          Search for an address like in rideshare apps, adjust the map pin if needed, or use your current location.
        </AppText>

        <VenuePinMap
          ref={venueMapRef}
          active
          pinLat={manualLat}
          pinLng={manualLng}
          onPinChange={(lat, lng) => {
            lockAddressSuggestionsRef.current = false;
            setManualLat(lat);
            setManualLng(lng);
          }}
        />

        <View>
          <AppText variant="labelSmall" tone="tertiary" style={styles.modalFieldLabel}>
            Venue name
          </AppText>
          <TextInput
            value={manualName}
            onChangeText={setManualName}
            placeholder="Venue name"
            placeholderTextColor={colors.textTertiary}
            style={styles.modalInput}
          />
        </View>

        <View>
          <View style={styles.modalSuggestLabelRow}>
            <AppText variant="labelSmall" tone="tertiary" style={styles.modalFieldLabel}>
              Address search
            </AppText>
          </View>
          <TextInput
            value={manualAddress}
            onChangeText={(t) => {
              lockAddressSuggestionsRef.current = false;
              setSuppressSuggestEmptyHint(false);
              setManualAddress(t);
            }}
            placeholder="Start typing for suggestions…"
            placeholderTextColor={colors.textTertiary}
            style={styles.modalInput}
            autoCorrect={false}
            autoCapitalize="words"
          />
          {addressSearchBusy ? (
            <View style={styles.searchStatusRow}>
              <ActivityIndicator size="small" color={colors.textSecondary} />
              <AppText tone="tertiary">Searching places…</AppText>
            </View>
          ) : null}
          {addressSuggestError ? (
            <AppText tone="secondary" style={styles.suggestError}>
              {addressSuggestError}
            </AppText>
          ) : null}
          {addressSuggestions.length > 0 ? (
            <View style={styles.suggestListWrap}>
              {addressSuggestions.map((p) => (
                <Pressable
                  key={p.place_id}
                  onPress={() => void pickAddressSuggestion(p)}
                  style={({ pressed }) => [styles.suggestionRow, pressedOpacityStyle(pressed)]}
                >
                  <AppText variant="label">{p.main_text}</AppText>
                  {p.secondary_text ? (
                    <AppText tone="tertiary" style={{ fontSize: 13, marginTop: 2 }}>
                      {p.secondary_text}
                    </AppText>
                  ) : null}
                </Pressable>
              ))}
            </View>
          ) : null}
          {showSuggestEmpty ? (
            <AppText tone="tertiary" style={styles.suggestHint}>
              No suggestions yet. If this never changes, the API server may be missing GOOGLE_MAPS_API_KEY or Places is
              not enabled for that key.
            </AppText>
          ) : null}
        </View>

        <Button
          label={locLoading ? "Getting location…" : "Use current location"}
          variant="outline"
          disabled={locLoading}
          onPress={() => void fillManualLocation()}
        />
        {manualLat != null && manualLng != null ? (
          <AppText tone="secondary" style={styles.modalCoords}>
            Pin: {manualLat.toFixed(5)}, {manualLng.toFixed(5)}
          </AppText>
        ) : (
          <AppText tone="tertiary" style={styles.modalCoords}>
            No pin yet — tap the map or use your current location.
          </AppText>
        )}

        <View style={styles.actions}>
          <Button
            label={manualSaving ? "Saving…" : "Save venue"}
            disabled={manualSaving}
            onPress={() => void submitManualVenue()}
          />
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
