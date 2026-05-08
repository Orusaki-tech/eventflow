import { Platform, type TextStyle, type ViewStyle } from "react-native";
import { getThemeSnapshot } from "./themeState";

const baseTokens = {
  spacing: {
    0: 0,
    4: 4,
    8: 8,
    10: 10,
    12: 12,
    16: 16,
    20: 20,
    24: 24,
    32: 32,
  },
  radii: {
    sm: 12,
    md: 16,
    pill: 999,
  },
  type: {
    display: { fontSize: 32, lineHeight: 38, fontWeight: "900" } satisfies TextStyle,
    headline: { fontSize: 24, lineHeight: 30, fontWeight: "900" } satisfies TextStyle,
    title: { fontSize: 18, lineHeight: 24, fontWeight: "800" } satisfies TextStyle,
    body: { fontSize: 15, lineHeight: 22, fontWeight: "500" } satisfies TextStyle,
    label: { fontSize: 14, lineHeight: 18, fontWeight: "800" } satisfies TextStyle,
    labelSmall: { fontSize: 12, lineHeight: 16, fontWeight: "700" } satisfies TextStyle,
  },
  elevation: {
    card: Platform.select<ViewStyle>({
      ios: {
        shadowColor: "#000",
        shadowOpacity: 0.22,
        shadowRadius: 14,
        shadowOffset: { width: 0, height: 8 },
      },
      android: { elevation: 2 },
      default: {},
    })!,
    sheet: Platform.select<ViewStyle>({
      ios: {
        shadowColor: "#000",
        shadowOpacity: 0.3,
        shadowRadius: 22,
        shadowOffset: { width: 0, height: 14 },
      },
      android: { elevation: 6 },
      default: {},
    })!,
  },
} as const;

export type ThemeMode = "dark" | "light";

export const tokens = new Proxy({} as any, {
  get(_target, prop: keyof typeof baseTokens | "colors") {
    if (prop === "colors") return getThemeSnapshot().colors;
    return (baseTokens as any)[prop];
  },
}) as typeof baseTokens & { colors: ReturnType<typeof getThemeSnapshot>["colors"] };

export function pressedOpacityStyle(pressed: boolean): ViewStyle | null {
  return pressed ? { opacity: 0.75 } : null;
}

