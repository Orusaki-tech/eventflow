import fs from "node:fs";
import path from "node:path";

import type { ExpoConfig } from "expo/config";

const APP_GROUP = "group.com.eventflow.mobile";

/** Written by `deploy/gcp/deploy.sh` after a successful health check (gitignored). */
function readDeploymentApiUrl(): string | undefined {
  try {
    const deploymentEnvPath = path.join(__dirname, ".env.deployment");
    if (!fs.existsSync(deploymentEnvPath)) return undefined;
    const raw = fs.readFileSync(deploymentEnvPath, "utf8");
    const line = raw
      .split("\n")
      .map((l) => l.trim())
      .find((l) => l.startsWith("EXPO_PUBLIC_EVENTFLOW_API_URL=") && !l.startsWith("#"));
    if (!line) return undefined;
    const value = line.slice("EXPO_PUBLIC_EVENTFLOW_API_URL=".length).trim();
    const unquoted = value.replace(/^["']|["']$/g, "");
    return unquoted.length ? unquoted : undefined;
  } catch {
    return undefined;
  }
}

/**
 * Precedence: shell/env `EXPO_PUBLIC_EVENTFLOW_API_URL` → `.env.deployment` from deploy script → localhost.
 * When using `http://` (e.g. GCP VM IP), native needs cleartext/ATS exceptions below.
 */
const PUBLIC_API_URL =
  process.env.EXPO_PUBLIC_EVENTFLOW_API_URL ?? readDeploymentApiUrl() ?? "http://localhost:8000";
const USE_HTTP_API = PUBLIC_API_URL.startsWith("http://");

const defineConfig = (): ExpoConfig => ({
  name: "EventFlow",
  slug: "eventflow",
  version: "1.0.0",
  orientation: "portrait",
  icon: "./assets/icon.png",
  userInterfaceStyle: "automatic",
  newArchEnabled: true,
  scheme: "eventflow",
  splash: {
    image: "./assets/splash-icon.png",
    resizeMode: "contain",
    backgroundColor: "#0f172a",
  },
  ios: {
    supportsTablet: true,
    bundleIdentifier: "com.eventflow.mobile",
    ...(process.env.EXPO_PUBLIC_APPLE_TEAM_ID
      ? { appleTeamId: process.env.EXPO_PUBLIC_APPLE_TEAM_ID }
      : {}),
    entitlements: {
      "com.apple.security.application-groups": [APP_GROUP],
    },
    infoPlist: {
      UIBackgroundModes: ["remote-notification"],
      ...(USE_HTTP_API
        ? {
            // Remove when API is served over HTTPS (recommended for production).
            NSAppTransportSecurity: { NSAllowsArbitraryLoads: true },
          }
        : {}),
    },
  },
  android: {
    package: "com.eventflow.mobile",
    ...(USE_HTTP_API ? { usesCleartextTraffic: true } : {}),
    config: {
      googleMaps: {
        // Same env name as backend / root .env; optional legacy Expo-only alias below.
        apiKey: process.env.GOOGLE_MAPS_API_KEY ?? process.env.EXPO_PUBLIC_GOOGLE_MAPS_API_KEY ?? "",
      },
    },
    permissions: ["POST_NOTIFICATIONS"],
    adaptiveIcon: {
      foregroundImage: "./assets/adaptive-icon.png",
      backgroundColor: "#0f172a",
    },
    intentFilters: [
      {
        action: "SEND",
        category: ["DEFAULT"],
        data: [{ mimeType: "text/plain" }, { mimeType: "image/*" }, { mimeType: "video/*" }],
      },
      {
        action: "SEND_MULTIPLE",
        category: ["DEFAULT"],
        data: [{ mimeType: "image/*" }, { mimeType: "video/*" }],
      },
    ],
  },
  web: {
    favicon: "./assets/favicon.png",
  },
  plugins: [
    "./plugins/withAndroidShareHandoff.js",
    "@bacons/apple-targets",
    "@react-native-community/datetimepicker",
    [
      "expo-calendar",
      {
        calendarPermission:
          "EventFlow adds confirmed events to your calendar so you see them alongside your other plans.",
      },
    ],
  ],
  extra: {
    appGroup: APP_GROUP,
    eas: {
      projectId: "23426ae5-63ec-4cfc-b7ec-49433febbb5f",
    },
    apiBaseUrl: PUBLIC_API_URL,
    supabaseUrl: process.env.EXPO_PUBLIC_SUPABASE_URL ?? "",
    // Dashboard templates sometimes use EXPO_PUBLIC_SUPABASE_KEY for the publishable/anon key.
    supabaseAnonKey:
      process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? process.env.EXPO_PUBLIC_SUPABASE_KEY ?? "",
  },
});

export default defineConfig;
