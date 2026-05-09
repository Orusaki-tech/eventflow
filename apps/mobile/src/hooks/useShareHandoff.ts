import AsyncStorage from "@react-native-async-storage/async-storage";
import * as Linking from "expo-linking";
import * as FileSystem from "expo-file-system/legacy";
import { useCallback, useEffect } from "react";
import { AppState, Platform } from "react-native";
import { useAuth } from "../auth/AuthContext";
import {
  ANDROID_HANDOFF_FILENAME,
  STORAGE_PENDING_SHARE,
} from "../lib/constants";
import { readIosExtensionHandoff } from "../lib/readIosExtensionHandoff";
import { shouldPickInstagramCarouselSlides } from "../lib/captureRouting";
import { navigationRef } from "../navigation/navigationRef";

type SharePayload =
  | { kind: "text"; text: string; capturedAt?: number }
  | {
      kind: "media";
      text?: string;
      capturedAt?: number;
      items: Array<{ uri: string; mimeType: string; filename?: string }>;
    };

function safeDecode(s: string) {
  try {
    return decodeURIComponent(s);
  } catch {
    return s;
  }
}

function parseSharePayload(raw: string): SharePayload | null {
  try {
    const j: unknown = JSON.parse(raw);
    if (!j || typeof j !== "object") return null;
    const o = j as Record<string, unknown>;
    const kind = o.kind;
    if (kind === "text") {
      const text = typeof o.text === "string" ? o.text : "";
      if (!text.trim()) return null;
      return { kind: "text", text, capturedAt: typeof o.capturedAt === "number" ? o.capturedAt : undefined };
    }
    if (kind === "media") {
      const itemsRaw = o.items;
      if (!Array.isArray(itemsRaw)) return null;
      const items: Array<{ uri: string; mimeType: string; filename?: string }> = [];
      for (const it of itemsRaw) {
        if (!it || typeof it !== "object") continue;
        const r = it as Record<string, unknown>;
        const uri = typeof r.uri === "string" ? r.uri : "";
        const mimeType = typeof r.mimeType === "string" ? r.mimeType : "";
        const filename = typeof r.filename === "string" ? r.filename : undefined;
        if (!uri || !mimeType) continue;
        items.push({ uri, mimeType, filename });
      }
      if (items.length === 0) return null;
      return {
        kind: "media",
        text: typeof o.text === "string" ? o.text : undefined,
        capturedAt: typeof o.capturedAt === "number" ? o.capturedAt : undefined,
        items,
      };
    }
    return null;
  } catch {
    return null;
  }
}

function parseImportUrl(url: string | null): string | null {
  if (!url) return null;
  const parsed = Linking.parse(url);
  const q = parsed.queryParams as Record<string, string | string[] | undefined> | undefined;
  const text = q?.text;
  if (typeof text === "string") return safeDecode(text);
  if (Array.isArray(text) && text[0]) return safeDecode(text[0]);
  const urlParam = q?.url;
  if (typeof urlParam === "string") return safeDecode(urlParam);
  if (Array.isArray(urlParam) && urlParam[0]) return safeDecode(urlParam[0]);
  return null;
}

async function readAndroidHandoffFile(): Promise<string | null> {
  if (Platform.OS !== "android" || !FileSystem.documentDirectory) return null;
  const path = `${FileSystem.documentDirectory}${ANDROID_HANDOFF_FILENAME}`;
  const info = await FileSystem.getInfoAsync(path);
  if (!info.exists) return null;
  const raw = await FileSystem.readAsStringAsync(path);
  await FileSystem.deleteAsync(path, { idempotent: true });
  return raw;
}

export function useShareHandoff(navReady: boolean) {
  const { accessToken } = useAuth();

  const routeInbound = useCallback(
    async (raw: string | null) => {
      if (!raw?.trim()) return;
      const trimmed = raw.trim();
      const payload = parseSharePayload(trimmed);
      if (accessToken && navReady && navigationRef.isReady()) {
        if (payload?.kind === "media") {
          navigationRef.navigate("SharedMediaImport", { payloadJson: trimmed });
          return;
        }
        const text = payload?.kind === "text" ? payload.text : trimmed;
        const ig = shouldPickInstagramCarouselSlides(text);
        if (ig) {
          navigationRef.navigate("CarouselSlidePick", { rawText: ig.rawText, instagramUrl: ig.instagramUrl });
        } else {
          navigationRef.navigate("Processing", { rawText: text });
        }
      } else {
        await AsyncStorage.setItem(STORAGE_PENDING_SHARE, trimmed);
      }
    },
    [accessToken, navReady]
  );

  const scan = useCallback(async () => {
    const fromIos = readIosExtensionHandoff();
    if (fromIos) await routeInbound(fromIos);
    const fromAndroid = await readAndroidHandoffFile();
    if (fromAndroid) await routeInbound(fromAndroid);
  }, [routeInbound]);

  useEffect(() => {
    void scan();
    const sub = AppState.addEventListener("change", (s) => {
      if (s === "active") void scan();
    });
    return () => sub.remove();
  }, [scan]);

  useEffect(() => {
    const sub = Linking.addEventListener("url", async ({ url }) => {
      const parsed = Linking.parse(url);
      const path = parsed.path ?? "";
      if (path === "share-handoff" || parsed.hostname === "share-handoff") {
        await scan();
        return;
      }
      const fromQuery = parseImportUrl(url);
      if (fromQuery) await routeInbound(fromQuery);
    });
    void Linking.getInitialURL().then(async (url) => {
      const fromQuery = parseImportUrl(url);
      if (fromQuery) await routeInbound(fromQuery);
      await scan();
    });
    return () => sub.remove();
  }, [routeInbound, scan]);
}

export function useFlushPendingShare(navReady: boolean) {
  const { accessToken } = useAuth();

  useEffect(() => {
    if (!navReady || !accessToken || !navigationRef.isReady()) return;
    void (async () => {
      const p = await AsyncStorage.getItem(STORAGE_PENDING_SHARE);
      if (p) {
        await AsyncStorage.removeItem(STORAGE_PENDING_SHARE);
        const payload = parseSharePayload(p.trim());
        if (payload?.kind === "media") {
          navigationRef.navigate("SharedMediaImport", { payloadJson: p.trim() });
          return;
        }
        const text = payload?.kind === "text" ? payload.text : p;
        const ig = shouldPickInstagramCarouselSlides(text);
        if (ig) {
          navigationRef.navigate("CarouselSlidePick", { rawText: ig.rawText, instagramUrl: ig.instagramUrl });
        } else {
          navigationRef.navigate("Processing", { rawText: text });
        }
      }
    })();
  }, [navReady, accessToken]);
}
