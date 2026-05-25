import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useEffect, useMemo, useState } from "react";
import { Alert, Pressable, ScrollView, TextInput, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import * as Clipboard from "expo-clipboard";
import * as Linking from "expo-linking";
import { useAuth } from "../auth/AuthContext";
import {
  cancelEvent,
  EventflowApiError,
  getEvent,
  patchEventBasics,
  patchEventDescription,
  patchEventPrice,
  postSnoozeLeaveAlert,
} from "../api/eventflow";
import { removeDeviceCalendarMapping } from "../lib/deviceCalendar";
import { EventDateTimePickerField } from "../components/EventDateTimePickerField";
import { InstagramCarouselSourceGallery } from "../components/InstagramCarouselSourceGallery";
import { LinkThumbnail } from "../components/LinkThumbnail";
import { isInstagramPostUrl } from "../lib/normalizeSharePayload";
import { formatFriendlyEventDateTime } from "../lib/eventDateTime";
import {
  clampSnoozeMinutes,
  parseSnoozeMinutesInput,
  SNOOZE_MIN_MAX,
  SNOOZE_MIN_MIN,
} from "../lib/snoozeMinutes";
import { getEventSourceUrl } from "../lib/thumbnail";
import type { RootStackParamList } from "../navigation/types";
import { AppText, Button, Card } from "../design/components";
import { tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";

type Props = NativeStackScreenProps<RootStackParamList, "EventDetail">;

export function EventDetailScreen({ navigation, route }: Props) {
  const { colors } = useTheme();
  const styles = useThemedStyles((c) => ({
    root: { flex: 1, backgroundColor: c.bg },
    content: { padding: tokens.spacing[20], gap: tokens.spacing[16], flexGrow: 1 },
    linkRow: { flexDirection: "row" as const, alignItems: "center" as const, gap: tokens.spacing[12] },
    linkTextCol: { flex: 1, minWidth: 0 },
    linkText: { textDecorationLine: "underline" as const },
    linkBtnRow: { flexDirection: "row" as const, gap: tokens.spacing[8] },
    linkBtnWrap: { minWidth: 84 },
    card: { padding: tokens.spacing[20] },
    title: { marginBottom: tokens.spacing[8] },
    meta: { marginBottom: tokens.spacing[4] },
    venue: { marginBottom: tokens.spacing[4] },
    descCard: { padding: tokens.spacing[16], gap: tokens.spacing[12] },
    audienceRow: { flexDirection: "row" as const, gap: tokens.spacing[8], flexWrap: "wrap" as const },
    descInput: {
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: tokens.radii.sm,
      padding: tokens.spacing[12],
      color: c.textPrimary,
      minHeight: 90,
      textAlignVertical: "top" as const,
    },
    priceInput: {
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: tokens.radii.sm,
      padding: tokens.spacing[12],
      color: c.textPrimary,
      minHeight: 44,
    },
    priceRow: {
      flexDirection: "row" as const,
      alignItems: "center" as const,
      gap: tokens.spacing[8],
      justifyContent: "space-between" as const,
    },
    priceRowText: { flex: 1, minWidth: 0 },
    editIconHit: { padding: tokens.spacing[8] },
    detailsMainCol: { flex: 1, minWidth: 0 },
    detailsInput: {
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: tokens.radii.sm,
      padding: tokens.spacing[12],
      color: c.textPrimary,
      minHeight: 44,
      marginBottom: tokens.spacing[8],
    },
    detailsLabel: { marginBottom: tokens.spacing[4] },
    snoozeCard: { padding: tokens.spacing[16], gap: tokens.spacing[12] },
    snoozeRow: { flexDirection: "row" as const, flexWrap: "wrap" as const, gap: tokens.spacing[8] },
    snoozeCustomRow: { flexDirection: "row" as const, gap: tokens.spacing[8], alignItems: "center" as const },
    snoozeCustomInput: {
      flex: 1,
      minWidth: 80,
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: tokens.radii.sm,
      padding: tokens.spacing[10],
      color: c.textPrimary,
    },
  }));
  const { apiBaseUrl, accessToken, session, refreshSession } = useAuth();
  const { eventId, title, start_time, venue } = route.params;
  const initialSharedUrl = route.params.sharedUrl;
  const ownerUserId = route.params.ownerUserId;
  const initialPrice = route.params.price ?? null;
  const [sharedUrl, setSharedUrl] = useState<string | null>(initialSharedUrl ?? null);
  const [audience, setAudience] = useState<"public" | "close_friends">("public");
  const [description, setDescription] = useState("");
  const [descriptionLoaded, setDescriptionLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [priceInput, setPriceInput] = useState(initialPrice?.trim() ?? "");
  const [savingPrice, setSavingPrice] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [priceEditing, setPriceEditing] = useState(false);
  const [detailsEditing, setDetailsEditing] = useState(false);
  const [titleInput, setTitleInput] = useState(title);
  const [venueInput, setVenueInput] = useState(venue);
  const [startInput, setStartInput] = useState(start_time);
  const [savingDetails, setSavingDetails] = useState(false);
  const [snoozeBusy, setSnoozeBusy] = useState(false);
  const [snoozeCustomOpen, setSnoozeCustomOpen] = useState(false);
  const [snoozeCustomText, setSnoozeCustomText] = useState("");

  const eventStartsInFuture = useMemo(() => {
    const d = new Date(start_time);
    return !Number.isNaN(d.getTime()) && d.getTime() > Date.now();
  }, [start_time]);

  useEffect(() => {
    setTitleInput(title);
    setVenueInput(venue);
    setStartInput(start_time);
  }, [title, start_time, venue]);

  useEffect(() => {
    if (!accessToken) return;
    let cancelled = false;
    void (async () => {
      try {
        const evt = await getEvent(apiBaseUrl, accessToken, eventId);
        if (cancelled) return;
        const descPublic = evt.description_public ?? "";
        const descCloseFriends = evt.description_close_friends ?? "";
        if (descPublic) {
          setDescription(descPublic);
          setAudience("public");
        } else if (descCloseFriends) {
          setDescription(descCloseFriends);
          setAudience("close_friends");
        }
        setDescriptionLoaded(true);
      } catch {
        if (!cancelled) setDescriptionLoaded(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, accessToken, eventId]);

  const authUserId = session?.user?.id ?? null;
  const isEventOwner =
    Boolean(authUserId && ownerUserId && authUserId.toLowerCase() === ownerUserId.toLowerCase());
  const canCancelEvent = isEventOwner;

  useEffect(() => {
    if (sharedUrl) return;
    let cancelled = false;
    void (async () => {
      const u = await getEventSourceUrl(eventId);
      if (!cancelled && u) setSharedUrl(u);
    })();
    return () => {
      cancelled = true;
    };
  }, [eventId, sharedUrl]);

  const when = useMemo(() => formatFriendlyEventDateTime(start_time), [start_time]);

  const confirmAttendance = () => {
    Alert.alert("Attendance", "Marked as attending.");
  };

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      {sharedUrl && isInstagramPostUrl(sharedUrl) ? (
        <InstagramCarouselSourceGallery
          apiBaseUrl={apiBaseUrl}
          accessToken={accessToken}
          sharedUrl={sharedUrl}
          height={160}
          refreshSession={refreshSession}
          renderFallback={() => <LinkThumbnail apiBaseUrl={apiBaseUrl} sharedUrl={sharedUrl} height={160} />}
        />
      ) : sharedUrl ? (
        <LinkThumbnail apiBaseUrl={apiBaseUrl} sharedUrl={sharedUrl} height={160} />
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

      <Card style={styles.card}>
        {isEventOwner && detailsEditing ? (
          <>
            <AppText variant="labelSmall" tone="tertiary" style={styles.detailsLabel}>
              Title
            </AppText>
            <TextInput
              style={styles.detailsInput}
              value={titleInput}
              onChangeText={setTitleInput}
              placeholder="Event title"
              placeholderTextColor={colors.textTertiary}
            />
            <AppText variant="labelSmall" tone="tertiary" style={styles.detailsLabel}>
              Venue
            </AppText>
            <TextInput
              style={styles.detailsInput}
              value={venueInput}
              onChangeText={setVenueInput}
              placeholder="Venue or address"
              placeholderTextColor={colors.textTertiary}
            />
            <EventDateTimePickerField valueIso={startInput} onChangeIso={setStartInput} />
            <Button
              label={savingDetails ? "Saving…" : "Save event details"}
              loading={savingDetails}
              variant="outline"
              onPress={() => {
                setSavingDetails(true);
                void (async () => {
                  try {
                    const res = await patchEventBasics(apiBaseUrl, accessToken, eventId, {
                      title: titleInput.trim(),
                      venue: venueInput.trim(),
                      start_time: startInput.trim(),
                    });
                    navigation.setParams({
                      title: res.title,
                      venue: res.venue,
                      start_time: String(res.start_time),
                    });
                    setDetailsEditing(false);
                  } catch (e: unknown) {
                    if (e instanceof EventflowApiError && e.status === 401) await refreshSession();
                    Alert.alert("Save failed", e instanceof Error ? e.message : String(e));
                  } finally {
                    setSavingDetails(false);
                  }
                })();
              }}
              fullWidth
            />
            <Button
              label="Cancel"
              variant="text"
              onPress={() => {
                setTitleInput(title);
                setVenueInput(venue);
                setStartInput(start_time);
                setDetailsEditing(false);
              }}
              fullWidth
            />
          </>
        ) : isEventOwner ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Edit title, time, and location"
            onPress={() => setDetailsEditing(true)}
          >
            {({ pressed }) => (
              <View style={pressed ? { opacity: 0.92 } : undefined}>
                <View style={styles.priceRow}>
                  <View style={styles.detailsMainCol}>
                    <AppText variant="headline" style={styles.title}>
                      {title}
                    </AppText>
                    <AppText tone="secondary" style={styles.meta}>
                      {when}
                    </AppText>
                    <AppText tone="secondary" style={styles.venue}>
                      {venue}
                    </AppText>
                  </View>
                  <View style={styles.editIconHit} pointerEvents="none">
                    <Ionicons name="create-outline" size={22} color={colors.textSecondary} />
                  </View>
                </View>
              </View>
            )}
          </Pressable>
        ) : (
          <>
            <AppText variant="headline" style={styles.title}>
              {title}
            </AppText>
            <AppText tone="secondary" style={styles.meta}>
              {when}
            </AppText>
            <AppText tone="secondary" style={styles.venue}>
              {venue}
            </AppText>
          </>
        )}
      </Card>

      {accessToken && eventStartsInFuture ? (
        <Card style={styles.snoozeCard}>
          <AppText variant="title">Reminder</AppText>
          <AppText variant="labelSmall" tone="tertiary">
            Get a push notification in a few minutes (replaces any earlier snooze for this event).
          </AppText>
          <View style={styles.snoozeRow}>
            {([10, 30, 60] as const).map((m) => (
              <Button
                key={m}
                label={`${m} min`}
                variant="outline"
                size="md"
                loading={snoozeBusy}
                onPress={() => {
                  setSnoozeBusy(true);
                  void (async () => {
                    try {
                      const res = await postSnoozeLeaveAlert(apiBaseUrl, accessToken, eventId, clampSnoozeMinutes(m));
                      Alert.alert("Reminder scheduled", `You'll get a nudge around ${new Date(res.fire_at).toLocaleString()}.`);
                    } catch (e: unknown) {
                      if (e instanceof EventflowApiError && e.status === 401) await refreshSession();
                      else if (e instanceof EventflowApiError && e.status === 409) {
                        Alert.alert("Can't snooze", e.message);
                      } else {
                        Alert.alert("Snooze failed", e instanceof Error ? e.message : String(e));
                      }
                    } finally {
                      setSnoozeBusy(false);
                    }
                  })();
                }}
              />
            ))}
            <Button
              label={snoozeCustomOpen ? "Hide custom" : "Custom"}
              variant="outline"
              size="md"
              onPress={() => {
                setSnoozeCustomOpen((o) => !o);
                setSnoozeCustomText("");
              }}
            />
          </View>
          {snoozeCustomOpen ? (
            <>
              <View style={styles.snoozeCustomRow}>
                <TextInput
                  style={styles.snoozeCustomInput}
                  value={snoozeCustomText}
                  onChangeText={setSnoozeCustomText}
                  keyboardType="number-pad"
                  placeholder={`${SNOOZE_MIN_MIN}–${SNOOZE_MIN_MAX}`}
                  placeholderTextColor={colors.textTertiary}
                />
                <Button
                  label={snoozeBusy ? "…" : "Schedule"}
                  variant="filled"
                  size="md"
                  loading={snoozeBusy}
                  onPress={() => {
                    const mins = parseSnoozeMinutesInput(snoozeCustomText);
                    if (mins == null) {
                      Alert.alert("Minutes", `Enter a whole number from ${SNOOZE_MIN_MIN} to ${SNOOZE_MIN_MAX}.`);
                      return;
                    }
                    setSnoozeBusy(true);
                    void (async () => {
                      try {
                        const res = await postSnoozeLeaveAlert(apiBaseUrl, accessToken, eventId, mins);
                        Alert.alert("Reminder scheduled", `You'll get a nudge around ${new Date(res.fire_at).toLocaleString()}.`);
                        setSnoozeCustomOpen(false);
                        setSnoozeCustomText("");
                      } catch (e: unknown) {
                        if (e instanceof EventflowApiError && e.status === 401) await refreshSession();
                        else if (e instanceof EventflowApiError && e.status === 409) {
                          Alert.alert("Can't snooze", e.message);
                        } else {
                          Alert.alert("Snooze failed", e instanceof Error ? e.message : String(e));
                        }
                      } finally {
                        setSnoozeBusy(false);
                      }
                    })();
                  }}
                />
              </View>
            </>
          ) : null}
        </Card>
      ) : null}

      <Card style={styles.descCard}>
        <AppText variant="title">Ticket price</AppText>
        {isEventOwner && !priceEditing ? (
          <View style={styles.priceRow}>
            <AppText tone="secondary" style={styles.priceRowText} numberOfLines={2}>
              {priceInput.trim() ? priceInput.trim() : "No price"}
            </AppText>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Edit ticket price"
              style={styles.editIconHit}
              onPress={() => setPriceEditing(true)}
            >
              <Ionicons name="create-outline" size={22} color={colors.textSecondary} />
            </Pressable>
          </View>
        ) : isEventOwner ? (
          <>
            <AppText variant="labelSmall" tone="tertiary">
              For example $25 or Free. Leave empty for no price.
            </AppText>
            <TextInput
              style={styles.priceInput}
              value={priceInput}
              onChangeText={setPriceInput}
              placeholder="No price"
              placeholderTextColor={colors.textTertiary}
            />
            <Button
              label={savingPrice ? "Saving…" : "Save price"}
              loading={savingPrice}
              variant="outline"
              onPress={() => {
                setSavingPrice(true);
                void (async () => {
                  try {
                    const res = await patchEventPrice(apiBaseUrl, accessToken, eventId, {
                      price: priceInput.trim() ? priceInput.trim() : null,
                    });
                    setPriceInput(res.price?.trim() ?? "");
                    setPriceEditing(false);
                  } catch (e: unknown) {
                    Alert.alert("Save failed", e instanceof Error ? e.message : String(e));
                  } finally {
                    setSavingPrice(false);
                  }
                })();
              }}
              fullWidth
            />
          </>
        ) : (
          <AppText tone="secondary">{priceInput.trim() ? priceInput.trim() : "No price"}</AppText>
        )}
      </Card>

      <Card style={styles.descCard}>
        <AppText variant="title">Description</AppText>
        <View style={styles.audienceRow}>
          <Button
            label="Public"
            variant={audience === "public" ? "filled" : "outline"}
            size="md"
            onPress={() => setAudience("public")}
          />
          <Button
            label="Close friends"
            variant={audience === "close_friends" ? "filled" : "outline"}
            size="md"
            onPress={() => setAudience("close_friends")}
          />
        </View>
        <TextInput
          style={styles.descInput}
          value={description}
          onChangeText={setDescription}
          placeholder="Add a note others can see…"
          placeholderTextColor={colors.textTertiary}
          multiline
        />
        <Button
          label={saving ? "Saving…" : "Save description"}
          loading={saving}
          variant="outline"
          onPress={() => {
            if (!descriptionLoaded) {
              Alert.alert("Still loading", "Description data is not ready yet. Please wait.");
              return;
            }
            setSaving(true);
            void (async () => {
              try {
                await patchEventDescription(apiBaseUrl, accessToken, eventId, {
                  description: description.trim() ? description.trim() : null,
                  audience,
                });
              } catch (e: unknown) {
                Alert.alert("Save failed", e instanceof Error ? e.message : String(e));
              } finally {
                setSaving(false);
              }
            })();
          }}
          fullWidth
        />
      </Card>

      <Button label="Confirm attendance" onPress={confirmAttendance} fullWidth />

      {canCancelEvent ? (
        <Button
          label={cancelling ? "Cancelling…" : "Cancel event"}
          variant="outline"
          loading={cancelling}
          onPress={() => {
            Alert.alert(
              "Cancel this event?",
              "It will be removed from your upcoming lists.",
              [
                { text: "Keep event", style: "cancel" },
                {
                  text: "Cancel event",
                  style: "destructive",
                  onPress: () => {
                    setCancelling(true);
                    void (async () => {
                      try {
                        await removeDeviceCalendarMapping(apiBaseUrl, accessToken, eventId);
                        await cancelEvent(apiBaseUrl, accessToken, eventId);
                        navigation.goBack();
                      } catch (e: unknown) {
                        if (e instanceof EventflowApiError && e.status === 401) await refreshSession();
                        Alert.alert("Could not cancel", e instanceof Error ? e.message : String(e));
                      } finally {
                        setCancelling(false);
                      }
                    })();
                  },
                },
              ]
            );
          }}
          fullWidth
        />
      ) : null}
    </ScrollView>
  );
}

