import AsyncStorage from "@react-native-async-storage/async-storage";
import { createClient } from "@supabase/supabase-js";
import Constants from "expo-constants";

const extra = Constants.expoConfig?.extra as {
  supabaseUrl?: string;
  supabaseAnonKey?: string;
} | null;

const url = extra?.supabaseUrl;
const key = extra?.supabaseAnonKey;

export const supabaseConfigured = Boolean(url && key);

/** Inert client when env is missing so imports never throw; do not call auth until configured. */
export const supabase = createClient(
  url ?? "https://disabled.invalid",
  key ?? "disabled",
  {
  auth: {
    storage: AsyncStorage,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
});
