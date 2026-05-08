import { Ionicons } from "@expo/vector-icons";
import DateTimePicker, { DateTimePickerEvent } from "@react-native-community/datetimepicker";
import React, { useCallback, useMemo, useState } from "react";
import { Modal, Platform, Pressable, TextInput, View } from "react-native";
import {
  dateFromIsoOrNow,
  formatFriendlyEventDateTime,
  mergeDatePart,
  mergeTimePart,
  toIsoUtcString,
} from "../lib/eventDateTime";
import { AppText, Button } from "../design/components";
import { tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";

type Props = {
  valueIso: string;
  onChangeIso: (iso: string) => void;
  label?: string;
};

export function EventDateTimePickerField({
  valueIso,
  onChangeIso,
  label = "Start date & time",
}: Props) {
  const { colors, mode } = useTheme();
  const styles = useThemedStyles((c) => ({
    label: { marginTop: tokens.spacing[8] },
    row: {
      flexDirection: "row" as const,
      alignItems: "center" as const,
      gap: tokens.spacing[12],
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: 10,
      paddingHorizontal: tokens.spacing[12],
      paddingVertical: tokens.spacing[12],
      backgroundColor: c.surface1,
      minHeight: 48,
    },
    rowText: { flex: 1, minWidth: 0 },
    iosModalBackdrop: {
      flex: 1,
      justifyContent: "flex-end" as const,
      backgroundColor: "rgba(0,0,0,0.45)",
    },
    iosSheet: {
      backgroundColor: c.surface1,
      borderTopLeftRadius: 16,
      borderTopRightRadius: 16,
      paddingBottom: tokens.spacing[24],
      paddingHorizontal: tokens.spacing[16],
      paddingTop: tokens.spacing[12],
      borderTopWidth: 1,
      borderColor: c.border,
    },
    iosToolbar: {
      flexDirection: "row" as const,
      justifyContent: "space-between" as const,
      alignItems: "center" as const,
      marginBottom: tokens.spacing[8],
    },
    input: {
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: 10,
      padding: 12,
      color: c.textPrimary,
      backgroundColor: c.surface1,
    },
  }));

  const friendly = useMemo(() => {
    const s = formatFriendlyEventDateTime(valueIso);
    return s || "Tap to choose date & time";
  }, [valueIso]);

  const [iosOpen, setIosOpen] = useState(false);
  const [iosDraft, setIosDraft] = useState(() => dateFromIsoOrNow(valueIso));

  const [showAndroidDate, setShowAndroidDate] = useState(false);
  const [showAndroidTime, setShowAndroidTime] = useState(false);
  const [androidDraft, setAndroidDraft] = useState(() => dateFromIsoOrNow(valueIso));

  const openPickers = useCallback(() => {
    const d = dateFromIsoOrNow(valueIso);
    setIosDraft(d);
    setAndroidDraft(d);
    if (Platform.OS === "android") {
      setShowAndroidDate(true);
    } else if (Platform.OS === "ios") {
      setIosOpen(true);
    }
  }, [valueIso]);

  const onAndroidDateChange = (event: DateTimePickerEvent, selected?: Date) => {
    setShowAndroidDate(false);
    if (event.type === "dismissed" || !selected) return;
    setAndroidDraft((prev) => mergeDatePart(prev, selected));
    setShowAndroidTime(true);
  };

  const onAndroidTimeChange = (event: DateTimePickerEvent, selected?: Date) => {
    setShowAndroidTime(false);
    if (event.type === "dismissed" || !selected) return;
    setAndroidDraft((prev) => {
      const merged = mergeTimePart(prev, selected);
      onChangeIso(toIsoUtcString(merged));
      return merged;
    });
  };

  const onIosChange = (_event: DateTimePickerEvent, selected?: Date) => {
    if (selected) setIosDraft(selected);
  };

  if (Platform.OS === "web") {
    return (
      <View>
        <AppText variant="labelSmall" tone="tertiary" style={styles.label}>
          {label} (ISO for web preview)
        </AppText>
        <TextInput
          style={styles.input}
          value={valueIso}
          onChangeText={onChangeIso}
          autoCapitalize="none"
          placeholder="2026-05-04T18:00:00.000Z"
          placeholderTextColor={colors.textTertiary}
        />
      </View>
    );
  }

  return (
    <View>
      <AppText variant="labelSmall" tone="tertiary" style={styles.label}>
        {label}
      </AppText>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${label}: ${friendly}`}
        onPress={openPickers}
        style={({ pressed }) => [styles.row, pressed ? { opacity: 0.92 } : undefined]}
      >
        <AppText variant="body" style={styles.rowText} numberOfLines={2}>
          {friendly}
        </AppText>
        <Ionicons name="calendar-outline" size={22} color={colors.textSecondary} />
      </Pressable>

      {Platform.OS === "android" && showAndroidDate ? (
        <DateTimePicker value={androidDraft} mode="date" display="default" onChange={onAndroidDateChange} />
      ) : null}
      {Platform.OS === "android" && showAndroidTime ? (
        <DateTimePicker value={androidDraft} mode="time" display="default" onChange={onAndroidTimeChange} />
      ) : null}

      {Platform.OS === "ios" ? (
        <Modal visible={iosOpen} animationType="slide" transparent onRequestClose={() => setIosOpen(false)}>
          <Pressable style={styles.iosModalBackdrop} onPress={() => setIosOpen(false)}>
            <Pressable style={styles.iosSheet} onPress={(e) => e.stopPropagation()}>
              <View style={styles.iosToolbar}>
                <Button label="Cancel" variant="text" size="md" onPress={() => setIosOpen(false)} />
                <Button
                  label="Done"
                  variant="text"
                  size="md"
                  onPress={() => {
                    onChangeIso(toIsoUtcString(iosDraft));
                    setIosOpen(false);
                  }}
                />
              </View>
              <DateTimePicker
                value={iosDraft}
                mode="datetime"
                display="spinner"
                onChange={onIosChange}
                themeVariant={mode === "dark" ? "dark" : "light"}
              />
            </Pressable>
          </Pressable>
        </Modal>
      ) : null}
    </View>
  );
}
