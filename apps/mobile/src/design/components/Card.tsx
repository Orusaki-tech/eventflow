import React from "react";
import { StyleSheet, type ViewProps } from "react-native";
import { tokens } from "../tokens";
import { Surface, type SurfaceProps } from "./Surface";

export type CardProps = Omit<SurfaceProps, "level"> & {
  elevated?: boolean;
};

export function Card({ elevated = true, style, ...rest }: CardProps) {
  return <Surface style={[styles.card, elevated ? styles.elevated : null, style]} {...rest} />;
}

const styles = StyleSheet.create({
  card: {
    borderRadius: tokens.radii.sm,
  },
  elevated: tokens.elevation.card,
});

