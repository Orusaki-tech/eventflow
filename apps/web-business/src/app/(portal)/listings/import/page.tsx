"use client";

import { IconArrowLeft, IconArrowRight, IconLink, IconSend } from "@tabler/icons-react";
import Link from "next/link";
import { useState } from "react";
import { usePortalAuth } from "@/components/portal/portal-auth-context";
import { mediaUrl, putListingShareAlias, shareUrl, upsertCommunityListing, type ShareUrlResult } from "@/lib/eventflow-api";

export default function ImportListingPage() {
  const { token } = usePortalAuth();
  const [url, setUrl] = useState("");
  const [parsed, setParsed] = useState<ShareUrlResult | null>(null);
  const [title, setTitle] = useState("");
  const [venue, setVenue] = useState("");
  const [startLocal, setStartLocal] = useState("");
  const [step, setStep] = useState<"input" | "preview" | "done">("input");
  const [status, setStatus] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [createdId, setCreatedId] = useState<string | null>(null);

  const handleParse = async () => {
    setErr(null); setStatus(null);
    if (!url.trim()) { setErr("Enter a URL"); return; }
    setBusy(true);
    try {
      const result = await shareUrl(token, url.trim());
      setParsed(result);
      setTitle(result.title);
      setVenue(result.venue);
      if (result.start_time) {
        const d = new Date(result.start_time);
        setStartLocal(d.toISOString().slice(0, 16));
      }
      setStep("preview");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const handleImport = async () => {
    setErr(null); setStatus(null);
    if (!title.trim() || !startLocal) { setErr("Title and start time are required"); return; }
    setBusy(true);
    try {
      const iso = new Date(startLocal).toISOString();
      const posterUri = parsed?.poster_asset_id ? mediaUrl(parsed.poster_asset_id, "poster") : null;
      const listing = await upsertCommunityListing(token, {
        source: "imported",
        title: title.trim(),
        venue: venue.trim(),
        start_time: iso,
        description: null,
        poster_image_uri: posterUri,
      });
      await putListingShareAlias(token, listing.community_event_id, url.trim());
      setCreatedId(listing.community_event_id);
      setStep("done");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const posterSrc = parsed?.poster_asset_id
    ? mediaUrl(parsed.poster_asset_id, "poster")
    : null;

  return (
    <>
      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">01</div>
          <div className="portal-card-title">Import from URL</div>
          <span className="portal-tag portal-tag-info">Wizard</span>
        </div>
        <div className="portal-card-bd">
          <p style={{ margin: "0 0 14px", fontSize: 12, color: "var(--portal-muted)" }}>
            Paste a shared event URL (Facebook, Eventbrite, Instagram, etc.) to parse it and create a community listing.
            The URL will be registered as a share alias so future shares resolve directly to this listing.
          </p>

          {step === "input" && (
            <div className="portal-field">
              <div className="portal-lbl">Event URL</div>
              <div style={{ display: "flex", gap: 8 }}>
                <input
                  className="portal-inp"
                  type="url"
                  placeholder="https://facebook.com/events/..."
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") void handleParse(); }}
                  style={{ flex: 1 }}
                />
                <button type="button" className="portal-act" disabled={busy} onClick={() => void handleParse()}>
                  <IconLink size={12} stroke={2} />
                  {busy ? "Parsing..." : "Parse"}
                </button>
              </div>
            </div>
          )}

          {step === "preview" && parsed && (
            <>
              <div className="portal-info-box" style={{ marginBottom: 14 }}>
                <IconArrowRight size={16} stroke={1.5} color="#2e2e2e" />
                <div>
                  <div className="portal-info-box-t">Parsed from URL</div>
                  <div className="portal-info-box-s" style={{ wordBreak: "break-all" }}>{parsed.source_url_raw}</div>
                </div>
              </div>

              {posterSrc && (
                <div style={{ marginBottom: 14 }}>
                  <div className="portal-lbl" style={{ marginBottom: 6 }}>Preview image</div>
                  <img
                    src={posterSrc}
                    alt="Preview"
                    style={{ maxWidth: "100%", maxHeight: 240, borderRadius: 8, objectFit: "cover" }}
                  />
                </div>
              )}

              <div className="portal-field">
                <div className="portal-lbl">Title</div>
                <input className="portal-inp" value={title} onChange={(e) => setTitle(e.target.value)} />
              </div>
              <div className="portal-field">
                <div className="portal-lbl">Venue</div>
                <input className="portal-inp" value={venue} onChange={(e) => setVenue(e.target.value)} />
              </div>
              <div className="portal-field">
                <div className="portal-lbl">Start time</div>
                <input
                  className="portal-inp"
                  type="datetime-local"
                  value={startLocal}
                  onChange={(e) => setStartLocal(e.target.value)}
                />
              </div>

              <div className="portal-divider" />
              <div className="portal-acts">
                <button type="button" className="portal-act" onClick={() => setStep("input")}>
                  <IconArrowLeft size={12} stroke={2} /> Back
                </button>
                <button type="button" className="portal-act" disabled={busy} onClick={() => void handleImport()}>
                  <IconSend size={12} stroke={2} />
                  {busy ? "Importing..." : "Import as listing"}
                </button>
              </div>
            </>
          )}

          {step === "done" && createdId && (
            <div className="portal-info-box">
              <IconArrowRight size={16} stroke={1.5} color="#2e2e2e" />
              <div>
                <div className="portal-info-box-t">Listing created</div>
                <div className="portal-info-box-s">
                  The event has been imported and the URL is registered as a share alias.
                </div>
              </div>
            </div>
          )}

          {err && <p className="portal-error">{err}</p>}
          {status && <p className="portal-status">{status}</p>}

          {step === "done" && createdId && (
            <div className="portal-acts">
              <Link href={`/listings/${createdId}`} className="portal-act" style={{ textDecoration: "none" }}>
                <IconArrowRight size={12} stroke={2} /> View listing
              </Link>
              <Link href="/listings" className="portal-act" style={{ textDecoration: "none" }}>
                All listings
              </Link>
            </div>
          )}
        </div>
      </div>
      <Link href="/listings" className="portal-link-back">← All listings</Link>
    </>
  );
}
