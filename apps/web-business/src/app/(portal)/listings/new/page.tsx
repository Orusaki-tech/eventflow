"use client";

import { IconSend } from "@tabler/icons-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { usePortalAuth } from "@/components/portal/portal-auth-context";
import { upsertCommunityListing } from "@/lib/eventflow-api";

export default function NewListingPage() {
  const { token } = usePortalAuth();
  const router = useRouter();
  const [title, setTitle] = useState("My public listing");
  const [venue, setVenue] = useState("Venue address");
  const [startLocal, setStartLocal] = useState("");
  const [posterUri, setPosterUri] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setErr(null);
    setStatus(null);
    if (!startLocal) {
      setErr("Pick start date/time");
      return;
    }
    setBusy(true);
    try {
      const iso = new Date(startLocal).toISOString();
      const res = await upsertCommunityListing(token, {
        source: "portal",
        title: title.trim(),
        venue: venue.trim(),
        start_time: iso,
        description: null,
        poster_image_uri: posterUri.trim() || null,
      });
      setStatus("Published.");
      router.push(`/listings/${res.community_event_id}`);
      router.refresh();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">01</div>
          <div className="portal-card-title">Publish community listing</div>
          <span className="portal-tag portal-tag-post">POST</span>
        </div>
        <div className="portal-card-bd">
          <div className="portal-field">
            <div className="portal-lbl">Title</div>
            <input className="portal-inp" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="portal-field">
            <div className="portal-lbl">Venue</div>
            <input className="portal-inp" value={venue} onChange={(e) => setVenue(e.target.value)} />
          </div>
          <div className="portal-grid2">
            <div className="portal-field">
              <div className="portal-lbl">
                Start <span className="portal-lbl-hint">— local datetime, ISO on save</span>
              </div>
              <input
                className="portal-inp"
                type="datetime-local"
                value={startLocal}
                onChange={(e) => setStartLocal(e.target.value)}
              />
            </div>
            <div className="portal-field">
              <div className="portal-lbl">
                Poster image URL <span className="portal-lbl-hint">— optional</span>
              </div>
              <input
                className="portal-inp"
                type="url"
                placeholder="https://…"
                value={posterUri}
                onChange={(e) => setPosterUri(e.target.value)}
              />
              {posterUri.trim() ? (
                <img
                  src={posterUri.trim()}
                  alt="Poster preview"
                  style={{
                    marginTop: 8,
                    maxWidth: "100%",
                    maxHeight: 160,
                    borderRadius: 6,
                    objectFit: "contain",
                    background: "#000",
                  }}
                />
              ) : null}
            </div>
          </div>
          <div className="portal-acts">
            <button type="button" className="portal-act" disabled={busy} onClick={() => void submit()}>
              <IconSend size={12} stroke={2} />
              <span className="portal-tag portal-tag-post" style={{ marginRight: 4 }}>
                POST
              </span>
              /discovery/community-events
            </button>
          </div>
          {status ? <p className="portal-status">{status}</p> : null}
          {err ? <p className="portal-error">{err}</p> : null}
        </div>
      </div>
      <Link href="/listings" className="portal-link-back">
        ← All listings
      </Link>
    </>
  );
}
