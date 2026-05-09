"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  attachListingBusiness,
  listBusinesses,
  postBillingCheckout,
  putListingShareAlias,
  registerEventVideo,
  upsertCommunityListing,
  type BusinessRow,
} from "@/lib/eventflow-api";
import { createSupabaseBrowserClient } from "@/lib/supabase-browser";

export default function DashboardPage() {
  const [token, setToken] = useState<string | null>(null);
  const [businesses, setBusinesses] = useState<BusinessRow[]>([]);
  const [loadErr, setLoadErr] = useState<string | null>(null);

  const [title, setTitle] = useState("My public listing");
  const [venue, setVenue] = useState("Venue address");
  const [startLocal, setStartLocal] = useState("");
  const [posterUri, setPosterUri] = useState("");
  const [listingId, setListingId] = useState("");
  const [attachBizId, setAttachBizId] = useState("");
  const [shareUrl, setShareUrl] = useState("");
  const [videoUri, setVideoUri] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const supabase = createSupabaseBrowserClient();
        const { data } = await supabase.auth.getSession();
        const t = data.session?.access_token ?? null;
        if (!cancelled) setToken(t);
        if (!t) return;
        const rows = await listBusinesses(t);
        if (!cancelled) setBusinesses(rows);
      } catch (e: unknown) {
        if (!cancelled) setLoadErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const run = async (fn: () => Promise<void>) => {
    setErr(null);
    setStatus(null);
    try {
      await fn();
      setStatus("Done.");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  if (!token) {
    return (
      <div className="card">
        <p>{loadErr ?? "Not signed in."}</p>
        <p>
          <Link href="/login">Sign in</Link>
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="card">
        <h1 style={{ marginTop: 0 }}>Dashboard</h1>
        <p style={{ color: "var(--muted)" }}>
          Same JWT as mobile · API {process.env.NEXT_PUBLIC_EVENTFLOW_API_URL ?? "http://localhost:8000"}
        </p>
        <button
          type="button"
          className="secondary"
          onClick={() =>
            void (async () => {
              const supabase = createSupabaseBrowserClient();
              await supabase.auth.signOut();
              window.location.href = "/login";
            })()
          }
        >
          Sign out
        </button>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Your businesses</h2>
        {businesses.length === 0 ? <p style={{ color: "var(--muted)" }}>No rows (create one from the mobile app).</p> : null}
        <ul style={{ paddingLeft: "1.25rem" }}>
          {businesses.map((b) => (
            <li key={b.business_id}>
              {b.name} — WhatsApp {b.whatsapp_e164 ?? "—"} — verified: {b.verified ? "yes" : "no"}
            </li>
          ))}
        </ul>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Publish community listing</h2>
        <label>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label>
          Venue
          <input value={venue} onChange={(e) => setVenue(e.target.value)} />
        </label>
        <label>
          Start (local datetime — stored as ISO from browser)
          <input type="datetime-local" value={startLocal} onChange={(e) => setStartLocal(e.target.value)} />
        </label>
        <label>
          Poster image URL (optional)
          <input value={posterUri} onChange={(e) => setPosterUri(e.target.value)} placeholder="https://..." />
        </label>
        <button
          type="button"
          style={{ marginTop: "0.75rem" }}
          onClick={() =>
            void run(async () => {
              if (!startLocal) throw new Error("Pick start date/time");
              const iso = new Date(startLocal).toISOString();
              const res = await upsertCommunityListing(token, {
                source: "portal",
                title: title.trim(),
                venue: venue.trim(),
                start_time: iso,
                description: null,
                poster_image_uri: posterUri.trim() || null,
              });
              setListingId(res.community_event_id);
            })
          }
        >
          POST /discovery/community-events
        </button>
        {listingId ? (
          <p style={{ color: "var(--muted)", wordBreak: "break-all" }}>
            Last listing id: <code>{listingId}</code>
          </p>
        ) : null}
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Attach business + canonical share URL</h2>
        <label>
          Community event id
          <input value={listingId} onChange={(e) => setListingId(e.target.value)} placeholder="uuid" />
        </label>
        <label>
          Business id
          <input value={attachBizId} onChange={(e) => setAttachBizId(e.target.value)} placeholder="uuid" />
        </label>
        <button
          type="button"
          style={{ marginTop: "0.75rem" }}
          onClick={() =>
            void run(async () => {
              if (!listingId.trim() || !attachBizId.trim()) throw new Error("Listing id and business id required");
              await attachListingBusiness(token, listingId.trim(), attachBizId.trim());
            })
          }
        >
          PUT /listings/…/business
        </button>
        <label style={{ marginTop: "1rem" }}>
          Official share URL (skips Gemini on mobile when matched)
          <input value={shareUrl} onChange={(e) => setShareUrl(e.target.value)} placeholder="https://instagram.com/..." />
        </label>
        <button
          type="button"
          style={{ marginTop: "0.5rem" }}
          onClick={() =>
            void run(async () => {
              if (!listingId.trim() || shareUrl.trim().length < 8) throw new Error("Listing id + URL required");
              await putListingShareAlias(token, listingId.trim(), shareUrl.trim());
            })
          }
        >
          PUT /listings/…/share-alias
        </button>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Promo video (pending moderation)</h2>
        <label>
          Storage URI (https object URL after upload)
          <input value={videoUri} onChange={(e) => setVideoUri(e.target.value)} placeholder="https://cdn.example.com/v.mp4" />
        </label>
        <button
          type="button"
          style={{ marginTop: "0.75rem" }}
          onClick={() =>
            void run(async () => {
              if (!listingId.trim() || videoUri.trim().length < 8) throw new Error("Listing id + storage URI required");
              await registerEventVideo(token, listingId.trim(), videoUri.trim());
            })
          }
        >
          POST /event-videos
        </button>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Billing stub</h2>
        <button
          type="button"
          onClick={() =>
            void run(async () => {
              await postBillingCheckout(token);
            })
          }
        >
          POST /billing/checkout-session
        </button>
      </div>

      {status ? <p style={{ color: "var(--muted)" }}>{status}</p> : null}
      {err ? <p className="error">{err}</p> : null}

      <p>
        <Link href="/">Home</Link>
      </p>
    </div>
  );
}
