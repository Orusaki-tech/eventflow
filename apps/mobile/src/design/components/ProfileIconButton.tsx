import React from "react";
import { Alert, Pressable, StyleSheet } from "react-native";
import { AppText } from "./AppText";
import { pressedOpacityStyle, tokens } from "../tokens";
import { useTheme } from "../theme";

type Props = {
  onPress: () => void;
  accessibilityLabel?: string;
};

export function ProfileIconButton({ onPress, accessibilityLabel = "Profile" }: Props) {
  const { mode, toggle } = useTheme();
  const { colors } = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      style={({ pressed }) => [
        styles.btn,
        { borderColor: colors.border, backgroundColor: colors.surface1 },
        pressedOpacityStyle(pressed),
      ]}
      onPress={() => {
        Alert.alert("Quick actions", undefined, [
          { text: `Switch to ${mode === "dark" ? "Light" : "Dark"} theme`, onPress: () => toggle() },
          { text: "Open profile", onPress },
          { text: "Cancel", style: "cancel" },
        ]);
      }}
    >
      <AppText variant="labelSmall" style={styles.label}>
        ME
      </AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: {
    width: 32,
    height: 32,
    borderRadius: 999,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  label: { letterSpacing: 0.8 },
});
