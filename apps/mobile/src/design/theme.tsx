import AsyncStorage from "@react-native-async-storage/async-storage";
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { setThemeSnapshot } from "./themeState";

export type ThemeMode = "dark" | "light";

const STORAGE_THEME_MODE = "@eventflow/theme/mode";

export type ThemeColors = {
  bg: string;
  surface1: string;
  surface2: string;
  textPrimary: string;
  textSecondary: string;
  textTertiary: string;
  border: string;
  divider: string;
  overlay: string;
  focus: string;
  danger: string;
};

function colorsFor(mode: ThemeMode): ThemeColors {
  if (mode === "light") {
    return {
      bg: "#F6F6F8",
      surface1: "#FFFFFF",
      surface2: "#F0F1F4",
      textPrimary: "#0B0B0C",
      textSecondary: "rgba(11,11,12,0.72)",
      textTertiary: "rgba(11,11,12,0.52)",
      border: "rgba(11,11,12,0.12)",
      divider: "rgba(11,11,12,0.08)",
      overlay: "rgba(0,0,0,0.18)",
      focus: "rgba(11,11,12,0.12)",
      danger: "#D92D20",
    };
  }

  return {
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
  };
}

type ThemeValue = {
  mode: ThemeMode;
  colors: ThemeColors;
  setMode: (mode: ThemeMode) => void;
  toggle: () => void;
  hydrated: boolean;
};

const ThemeContext = createContext<ThemeValue | null>(null);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>("dark");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const stored = await AsyncStorage.getItem(STORAGE_THEME_MODE);
        if (cancelled) return;
        if (stored === "light" || stored === "dark") setModeState(stored);
      } finally {
        if (!cancelled) setHydrated(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const setMode = useCallback((next: ThemeMode) => {
    setModeState(next);
    void AsyncStorage.setItem(STORAGE_THEME_MODE, next);
  }, []);

  const toggle = useCallback(() => {
    setMode(mode === "dark" ? "light" : "dark");
  }, [mode, setMode]);

  const colors = useMemo(() => colorsFor(mode), [mode]);

  useEffect(() => {
    setThemeSnapshot({ mode, colors });
  }, [mode, colors]);

  const value = useMemo(() => ({ mode, colors, setMode, toggle, hydrated }), [mode, colors, setMode, toggle, hydrated]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}

