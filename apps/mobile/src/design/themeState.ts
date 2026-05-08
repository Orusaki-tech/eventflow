import type { ThemeColors, ThemeMode } from "./theme";

type ThemeSnapshot = {
  mode: ThemeMode;
  colors: ThemeColors;
};

// Defaults match ThemeProvider dark palette.
let snapshot: ThemeSnapshot = {
  mode: "dark",
  colors: {
    bg: "#0B0B0C",
    surface1: "#0F0F10",
    surface2: "#141416",
    textPrimary: "#FFFFFF",
    textSecondary: "rgba(255,255,255,0.72)",
    textTertiary: "rgba(255,255,255,0.52)",
    border: "rgba(255,255,255,0.12)",
    divider: "rgba(255,255,255,0.08)",
    overlay: "rgba(0,0,0,0.55)",
    focus: "rgba(255,255,255,0.18)",
    danger: "#FF5A5F",
  },
};

export function setThemeSnapshot(next: ThemeSnapshot) {
  snapshot = next;
}

export function getThemeSnapshot(): ThemeSnapshot {
  return snapshot;
}

