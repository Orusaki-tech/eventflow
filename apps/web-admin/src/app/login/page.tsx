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
      router.push("/");
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
        <h1 className="auth-title">Admin sign in</h1>
        <p className="auth-lede">
          Enter the operator email and password you were given. If you cannot access the console after signing in, contact
          whoever manages EventFlow for your organization.
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
            <button type="submit" className="auth-submit" disabled={busy || !authConfigured}>
              {busy ? "Signing in…" : "Sign in"}
            </button>
          </div>
        </form>
        <p className="auth-footer">
          <Link href="/">Open the console</Link>
          <span style={{ opacity: 0.85 }}> — you must be signed in.</span>
        </p>
      </div>
    </div>
  );
}
