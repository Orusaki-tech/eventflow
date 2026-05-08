import type { Session } from "@supabase/supabase-js";
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import Constants from "expo-constants";
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";
import { registerExpoPushToken } from "../api/eventflow";
import { supabase, supabaseConfigured } from "../lib/supabase";

type AuthCtx = {
  session: Session | null;
  loading: boolean;
  accessToken: string | null;
  apiBaseUrl: string;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  refreshSession: () => Promise<void>;
};

const AuthContext = createContext<AuthCtx | null>(null);

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

async function tryRegisterPush(apiBaseUrl: string, accessToken: string | null) {
  if (!Device.isDevice || !accessToken) return;
  const { status } = await Notifications.requestPermissionsAsync();
  if (status !== "granted") return;
  const projectId =
    (Constants.expoConfig?.extra as { eas?: { projectId?: string } } | undefined)?.eas
      ?.projectId;
  const tokenData = await Notifications.getExpoPushTokenAsync(
    projectId ? { projectId } : undefined
  );
  const tok = tokenData.data;
  if (!tok?.startsWith("ExponentPushToken[")) return;
  try {
    await registerExpoPushToken(apiBaseUrl, accessToken, tok, Platform.OS as "ios" | "android");
  } catch {
    /* non-fatal */
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const apiBaseUrl =
    (Constants.expoConfig?.extra as { apiBaseUrl?: string } | undefined)?.apiBaseUrl ??
    "http://localhost:8000";
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!supabaseConfigured) {
      setLoading(false);
      return;
    }
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session ?? null);
      setLoading(false);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_e, sess) => {
      setSession(sess);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    const tok = session?.access_token ?? null;
    if (tok) void tryRegisterPush(apiBaseUrl, tok);
  }, [session?.access_token, apiBaseUrl]);

  const refreshSession = useCallback(async () => {
    if (!supabaseConfigured) return;
    const { data, error } = await supabase.auth.refreshSession();
    if (!error) setSession(data.session ?? null);
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    if (!supabaseConfigured) throw new Error("Supabase is not configured");
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
  }, []);

  const signUp = useCallback(async (email: string, password: string) => {
    if (!supabaseConfigured) throw new Error("Supabase is not configured");
    const { error } = await supabase.auth.signUp({ email, password });
    if (error) throw error;
  }, []);

  const signOut = useCallback(async () => {
    if (!supabaseConfigured) return;
    await supabase.auth.signOut();
  }, []);

  const value = useMemo<AuthCtx>(
    () => ({
      session,
      loading,
      accessToken: session?.access_token ?? null,
      apiBaseUrl,
      signIn,
      signUp,
      signOut,
      refreshSession,
    }),
    [session, loading, apiBaseUrl, signIn, signUp, signOut, refreshSession]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
