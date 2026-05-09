"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { createSupabaseBrowserClient } from "@/lib/supabase-browser";

const supabaseEnvReady =
  Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL?.trim()) &&
  Boolean(process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim());

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const supabase = createSupabaseBrowserClient();
      const { error: signErr } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
      if (signErr) throw signErr;
      router.push("/dashboard");
      router.refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="marketing-wrap">
      <div className="card">
      <h1 style={{ marginTop: 0 }}>Sign in</h1>
      <p style={{ color: "var(--muted)" }}>Use the same Supabase user as EventFlow mobile.</p>
      {!supabaseEnvReady ? (
        <p className="error" style={{ marginBottom: "1rem" }}>
          Supabase env is not configured. Add{" "}
          <code style={{ color: "inherit" }}>NEXT_PUBLIC_SUPABASE_URL</code> and{" "}
          <code style={{ color: "inherit" }}>NEXT_PUBLIC_SUPABASE_ANON_KEY</code> in Vercel → Settings → Environment
          Variables, then redeploy. See <code style={{ color: "inherit" }}>apps/web-business/.env.example</code>.
        </p>
      ) : null}
      <form onSubmit={(e) => void onSubmit(e)}>
        <label>
          Email
          <input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error ? <p className="error">{error}</p> : null}
        <div style={{ marginTop: "1rem", display: "flex", gap: "0.75rem", alignItems: "center" }}>
          <button type="submit" disabled={busy || !supabaseEnvReady}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
          <Link href="/" style={{ color: "var(--muted)" }}>
            Home
          </Link>
        </div>
      </form>
      </div>
    </div>
  );
}
