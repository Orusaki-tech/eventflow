import type { ExpoConfig } from "expo/config";

const APP_GROUP = "group.com.eventflow.mobile";

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
    },
  },
  android: {
    package: "com.eventflow.mobile",
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
  plugins: ["./plugins/withAndroidShareHandoff.js", "@bacons/apple-targets", "@react-native-community/datetimepicker"],
  extra: {
    appGroup: APP_GROUP,
    eas: {
      projectId: "23426ae5-63ec-4cfc-b7ec-49433febbb5f",
    },
    apiBaseUrl: process.env.EXPO_PUBLIC_EVENTFLOW_API_URL ?? "http://localhost:8000",
    supabaseUrl: process.env.EXPO_PUBLIC_SUPABASE_URL ?? "",
    // Dashboard templates sometimes use EXPO_PUBLIC_SUPABASE_KEY for the publishable/anon key.
    supabaseAnonKey:
      process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? process.env.EXPO_PUBLIC_SUPABASE_KEY ?? "",
  },
});

export default defineConfig;
