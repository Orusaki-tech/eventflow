import React from "react";
import { Text, type TextProps, type TextStyle } from "react-native";
import { tokens } from "../tokens";
import { useTheme } from "../theme";

type Variant = keyof typeof tokens.type;

export type AppTextProps = TextProps & {
  variant?: Variant;
  tone?: "primary" | "secondary" | "tertiary";
};

export function AppText({ variant = "body", tone = "primary", style, ...rest }: AppTextProps) {
  const { colors } = useTheme();
  const toneColor: Record<NonNullable<AppTextProps["tone"]>, string> = {
    primary: colors.textPrimary,
    secondary: colors.textSecondary,
    tertiary: colors.textTertiary,
  };
  const base: TextStyle = { color: toneColor[tone] };
  return <Text style={[tokens.type[variant], base, style]} {...rest} />;
}

