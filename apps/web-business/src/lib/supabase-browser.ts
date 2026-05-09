import { createClient, SupabaseClient } from "@supabase/supabase-js";

const globalForSb = globalThis as unknown as { __eventflowSb?: SupabaseClient };

export function createSupabaseBrowserClient(): SupabaseClient {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anon) {
    throw new Error(
      "Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY. " +
        "On Vercel: Project → Settings → Environment Variables → add both → Redeploy."
    );
  }
  if (!globalForSb.__eventflowSb) {
    globalForSb.__eventflowSb = createClient(url, anon);
  }
  return globalForSb.__eventflowSb;
}
