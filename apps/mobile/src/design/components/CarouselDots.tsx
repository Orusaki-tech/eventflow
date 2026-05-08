import React from "react";
import { View } from "react-native";
import { useTheme } from "../theme";

type Props = {
  count: number;
  activeIndex: number;
};

/** Horizontal stride for inbox-style cards (320px card + 10px separator gap). */
export const CAROUSEL_EVENT_CARD_STRIDE = 320 + 10;

export function CarouselDots({ count, activeIndex }: Props) {
  const { colors } = useTheme();
  if (count <= 1) return null;

  const idx = Math.min(Math.max(0, activeIndex), count - 1);

  return (
    <View
      accessibilityRole="progressbar"
      accessibilityLabel={`Slide ${idx + 1} of ${count}`}
      style={{
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "center",
        gap: 6,
        paddingVertical: 8,
      }}
    >
      {Array.from({ length: count }, (_, i) => {
        const active = i === idx;
        return (
          <View
            key={i}
            style={{
              height: 6,
              borderRadius: 3,
              width: active ? 14 : 6,
              backgroundColor: active ? colors.textPrimary : colors.textTertiary,
              opacity: active ? 1 : 0.35,
            }}
          />
        );
      })}
    </View>
  );
}
