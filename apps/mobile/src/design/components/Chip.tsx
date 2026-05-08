import React from "react";
import { Pressable, type PressableProps } from "react-native";
import { tokens, pressedOpacityStyle } from "../tokens";
import { useThemedStyles } from "../useThemedStyles";
import { AppText } from "./AppText";

export type ChipProps = Omit<PressableProps, "style" | "children"> & {
  label: string;
  selected?: boolean;
};

export function Chip({ label, selected = false, disabled, ...rest }: ChipProps) {
  const styles = useThemedStyles((c) => ({
    base: {
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: tokens.radii.pill,
      paddingVertical: tokens.spacing[8],
      paddingHorizontal: tokens.spacing[12],
      backgroundColor: c.surface1,
    },
    selected: {
      backgroundColor: c.textPrimary,
      borderColor: "transparent",
    },
    label: { color: c.textPrimary },
    selectedLabel: { color: c.bg },
    disabled: { opacity: 0.55 },
  }));

  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      style={({ pressed }) => [
        styles.base,
        selected ? styles.selected : null,
        pressedOpacityStyle(pressed),
        disabled ? styles.disabled : null,
      ]}
      {...rest}
    >
      <AppText variant="labelSmall" style={selected ? styles.selectedLabel : styles.label}>
        {label}
      </AppText>
    </Pressable>
  );
}

