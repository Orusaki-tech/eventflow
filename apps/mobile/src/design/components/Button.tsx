import React from "react";
import { ActivityIndicator, Pressable, StyleSheet, type PressableProps, type TextStyle, type ViewStyle } from "react-native";
import { tokens, pressedOpacityStyle } from "../tokens";
import { AppText } from "./AppText";
import { useTheme } from "../theme";

export type ButtonVariant = "filled" | "tonal" | "text" | "outline";
export type ButtonSize = "md" | "lg";

export type ButtonProps = Omit<PressableProps, "style" | "children"> & {
  label: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  fullWidth?: boolean;
};

export function Button({
  label,
  variant = "filled",
  size = "lg",
  loading = false,
  disabled,
  fullWidth = false,
  ...rest
}: ButtonProps) {
  const { colors } = useTheme();
  const isDisabled = disabled || loading;

  const variantStyles: {
    container: Record<ButtonVariant, ViewStyle>;
    label: Record<ButtonVariant, TextStyle>;
    spinner: Record<ButtonVariant, string>;
  } = React.useMemo(
    () => ({
      container: {
        filled: {
          backgroundColor: colors.textPrimary,
          borderColor: "transparent",
        },
        tonal: {
          backgroundColor: colors.surface2,
          borderColor: colors.border,
        },
        text: {
          backgroundColor: "transparent",
          borderColor: "transparent",
        },
        outline: {
          backgroundColor: "transparent",
          borderColor: colors.border,
        },
      },
      label: {
        filled: { color: colors.bg },
        tonal: { color: colors.textPrimary },
        text: { color: colors.textPrimary },
        outline: { color: colors.textPrimary },
      },
      spinner: {
        filled: colors.bg,
        tonal: colors.textPrimary,
        text: colors.textPrimary,
        outline: colors.textPrimary,
      },
    }),
    [colors]
  );

  return (
    <Pressable
      accessibilityRole="button"
      disabled={isDisabled}
      style={({ pressed }) => [
        styles.base,
        fullWidth ? styles.fullWidth : null,
        size === "md" ? styles.md : styles.lg,
        variantStyles.container[variant],
        pressedOpacityStyle(pressed),
        isDisabled ? styles.disabled : null,
      ]}
      {...rest}
    >
      {loading ? (
        <ActivityIndicator
          size="small"
          color={variantStyles.spinner[variant]}
          style={{ marginRight: tokens.spacing[8] }}
        />
      ) : null}
      <AppText variant="label" style={variantStyles.label[variant]}>
        {label}
      </AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: tokens.radii.sm,
    borderWidth: 1,
  },
  lg: { paddingVertical: 16, paddingHorizontal: 16 },
  md: { paddingVertical: 12, paddingHorizontal: 14 },
  fullWidth: { alignSelf: "stretch" },
  disabled: { opacity: 0.55 },
});

