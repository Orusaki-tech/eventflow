"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { createSupabaseBrowserClient } from "@/lib/supabase-browser";

const authConfigured =
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
    <div className="auth-shell">
      <div className="auth-card">
        <p className="auth-brand">EventFlow</p>
        <h1 className="auth-title">Welcome back</h1>
        <p className="auth-lede">
          Sign in with the same EventFlow account you use on your phone to manage listings, businesses, and media from the
          web.
        </p>
        {!authConfigured ? (
          <p className="error" style={{ marginBottom: "1rem" }}>
            Sign-in is not enabled on this deployment yet. Whoever hosts this app still needs to finish the hosting setup.
          </p>
        ) : null}
        <form className="auth-form" onSubmit={(e) => void onSubmit(e)}>
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
          <div className="auth-actions">
            <div className="auth-actions-row">
              <button type="submit" className="auth-submit" disabled={busy || !authConfigured}>
                {busy ? "Signing in…" : "Sign in"}
              </button>
              <Link href="/" style={{ fontSize: "0.9rem", color: "var(--muted)" }}>
                Home
              </Link>
            </div>
          </div>
        </form>
        <p className="auth-footer">
          New here? Create your account in the EventFlow mobile app first, then return to sign in on the web.
        </p>
      </div>
    </div>
  );
}
