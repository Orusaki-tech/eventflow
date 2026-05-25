"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { createSupabaseBrowserClient } from "@/lib/supabase-browser";

export default function SettingsPage() {
  const router = useRouter();
  const proxied = process.env.NEXT_PUBLIC_EVENTFLOW_API_PROXY === "1";
  const apiUrl = proxied
    ? "Same origin — requests use this site’s API proxy"
    : (process.env.NEXT_PUBLIC_EVENTFLOW_API_URL ?? "http://localhost:8000");

  const signOut = async () => {
    try {
      const supabase = createSupabaseBrowserClient();
      await supabase.auth.signOut();
    } catch (e: unknown) {
      console.error("signOut failed", e);
    }
    router.replace("/login");
    router.refresh();
  };

  return (
    <>
      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">01</div>
          <div className="portal-card-title">Environment</div>
          <span className="portal-tag portal-tag-info">Read-only</span>
        </div>
        <div className="portal-card-bd">
          <div className="portal-field">
            <div className="portal-lbl">{proxied ? "API routing" : "API base URL"}</div>
            <input className="portal-inp" readOnly value={apiUrl} />
          </div>
          {proxied ? (
            <p style={{ margin: "0 0 8px", fontSize: 11, color: "var(--portal-muted)" }}>
              Secure pages cannot call non-HTTPS backends directly. With proxy mode on, this portal reaches your API through
              the same hostname you are using now.
            </p>
          ) : null}
          <p style={{ margin: 0, fontSize: 11, color: "var(--portal-muted)" }}>
            Use one EventFlow account on mobile and here so listings and businesses stay in sync.
          </p>
        </div>
      </div>

      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">02</div>
          <div className="portal-card-title">Session</div>
        </div>
        <div className="portal-card-bd">
          <div className="portal-acts" style={{ marginTop: 0 }}>
            <button type="button" className="portal-btn-signout" onClick={() => void signOut()}>
              Sign out everywhere on this browser
            </button>
          </div>
        </div>
      </div>

      <Link href="/" className="portal-link-back">
        ← Home
      </Link>
    </>
  );
}
