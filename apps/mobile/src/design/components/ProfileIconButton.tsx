import React from "react";
import { Pressable, StyleSheet } from "react-native";
import { AppText } from "./AppText";
import { pressedOpacityStyle, tokens } from "../tokens";
import { useTheme } from "../theme";

type Props = {
  onPress: () => void;
  accessibilityLabel?: string;
};

export function ProfileIconButton({ onPress, accessibilityLabel = "Open connections" }: Props) {
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
      onPress={onPress}
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
