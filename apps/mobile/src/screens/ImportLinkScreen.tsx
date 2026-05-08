import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import React, { useState } from "react";
import { ScrollView, TextInput } from "react-native";
import { shouldPickInstagramCarouselSlides } from "../lib/captureRouting";
import type { RootStackParamList } from "../navigation/types";
import { AppText, Button } from "../design/components";
import { tokens } from "../design/tokens";
import { useTheme } from "../design/theme";
import { useThemedStyles } from "../design/useThemedStyles";

type Props = NativeStackScreenProps<RootStackParamList, "ImportLink">;

export function ImportLinkScreen({ navigation }: Props) {
  const { colors } = useTheme();
  const styles = useThemedStyles((c) => ({
    root: { flex: 1, backgroundColor: c.bg },
    content: { padding: tokens.spacing[20], gap: tokens.spacing[12], flexGrow: 1 },
    label: { fontSize: 14, lineHeight: 20 },
    input: {
      minHeight: 120,
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: 12,
      padding: 14,
      color: c.textPrimary,
      backgroundColor: c.surface1,
      textAlignVertical: "top" as const,
    },
  }));
  const [text, setText] = useState("");

  const submit = () => {
    const raw = text.trim();
    if (!raw) return;
    const ig = shouldPickInstagramCarouselSlides(raw);
    if (ig) {
      navigation.navigate("CarouselSlidePick", { rawText: ig.rawText, instagramUrl: ig.instagramUrl });
      return;
    }
    navigation.navigate("Processing", { rawText: raw });
  };

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <AppText tone="secondary" style={styles.label}>
        Paste a URL or any text that mentions your event
      </AppText>
      <TextInput
        style={styles.input}
        multiline
        placeholder="https://..."
        placeholderTextColor={colors.textTertiary}
        value={text}
        onChangeText={setText}
      />
      <AppText variant="labelSmall" tone="tertiary" style={styles.label}>
        Instagram carousel posts: you'll pick two slides on the next screen.
      </AppText>
      <Button label="Continue" onPress={submit} fullWidth />
    </ScrollView>
  );
}
