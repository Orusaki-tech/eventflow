import React from "react";
import { StyleSheet, View, type ViewProps } from "react-native";
import { tokens } from "../tokens";
import { useTheme } from "../theme";

export type SurfaceProps = ViewProps & {
  level?: 1 | 2;
  padded?: boolean;
};

export function Surface({ level = 1, padded = false, style, ...rest }: SurfaceProps) {
  const { colors } = useTheme();
  return (
    <View
      style={[
        styles.base,
        { borderColor: colors.border, backgroundColor: level === 2 ? colors.surface2 : colors.surface1 },
        padded ? styles.padded : null,
        style,
      ]}
      {...rest}
    />
  );
}

const styles = StyleSheet.create({
  base: {
    borderWidth: 1,
    borderRadius: tokens.radii.sm,
  },
  padded: { padding: tokens.spacing[16] },
});

