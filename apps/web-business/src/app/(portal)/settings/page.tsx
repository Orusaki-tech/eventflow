"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { createSupabaseBrowserClient } from "@/lib/supabase-browser";

export default function SettingsPage() {
  const router = useRouter();
  const apiUrl = process.env.NEXT_PUBLIC_EVENTFLOW_API_URL ?? "http://localhost:8000";

  const signOut = async () => {
    const supabase = createSupabaseBrowserClient();
    await supabase.auth.signOut();
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
            <div className="portal-lbl">NEXT_PUBLIC_EVENTFLOW_API_URL</div>
            <input className="portal-inp" readOnly value={apiUrl} />
          </div>
          <p style={{ margin: 0, fontSize: 11, color: "var(--portal-muted)" }}>
            JWT is issued by Supabase; use the same account as the EventFlow mobile app.
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
