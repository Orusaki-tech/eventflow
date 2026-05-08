import { useMemo } from "react";
import { StyleSheet, type ImageStyle, type TextStyle, type ViewStyle } from "react-native";
import type { ThemeColors } from "./theme";
import { useTheme } from "./theme";

type NamedStyles = Record<string, ViewStyle | TextStyle | ImageStyle>;

export function useThemedStyles<T extends NamedStyles>(factory: (colors: ThemeColors) => T): T {
  const { colors } = useTheme();
  // factory should only depend on `colors`; omit from deps to allow stable inline factories.
  return useMemo(() => StyleSheet.create(factory(colors)) as unknown as T, [colors]);
}
