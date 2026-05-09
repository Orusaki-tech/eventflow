"use client";

import { IconVideo } from "@tabler/icons-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { usePortalAuth } from "@/components/portal/portal-auth-context";
import {
  attachListingBusiness,
  getMyCommunityEvent,
  putListingShareAlias,
  registerEventVideo,
  type CommunityMineDetail,
} from "@/lib/eventflow-api";

function formatStart(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { dateStyle: "full", timeStyle: "short" });
  } catch {
    return iso;
  }
}

export default function ListingDetailPage() {
  const { token } = usePortalAuth();
  const params = useParams();
  const id = typeof params.id === "string" ? params.id : "";

  const [detail, setDetail] = useState<CommunityMineDetail | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [attachBizId, setAttachBizId] = useState("");
  const [shareUrl, setShareUrl] = useState("");
  const [videoUri, setVideoUri] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!id) return;
    const d = await getMyCommunityEvent(token, id);
    setDetail(d);
  }, [token, id]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      if (!id) return;
      try {
        await reload();
      } catch (e: unknown) {
        if (!cancelled) setLoadErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, reload]);

  const run = async (fn: () => Promise<void>) => {
    setErr(null);
    setStatus(null);
    try {
      await fn();
      setStatus("Done.");
      await reload();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  if (!id) {
    return <p className="portal-error">Invalid listing id.</p>;
  }

  if (loadErr) {
    return <p className="portal-error">{loadErr}</p>;
  }

  if (!detail) {
    return <p className="portal-status">Loading…</p>;
  }

  return (
    <>
      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">01</div>
          <div className="portal-card-title">{detail.title}</div>
          <span className="portal-tag portal-tag-info">Listing</span>
        </div>
        <div className="portal-card-bd">
          <p style={{ margin: "0 0 6px", fontSize: 12, color: "var(--portal-muted)" }}>{formatStart(detail.start_time)}</p>
          <p style={{ margin: "0 0 6px", fontSize: 12 }}>{detail.venue}</p>
          <p
            style={{
              margin: 0,
              fontSize: 10,
              fontFamily: "var(--font-mono)",
              color: "var(--portal-muted-2)",
              wordBreak: "break-all",
            }}
          >
            {detail.community_event_id}
          </p>
          {detail.business_id ? (
            <p style={{ margin: "10px 0 0", fontSize: 11, color: "var(--portal-muted)" }}>
              Attached business:{" "}
              <span style={{ fontFamily: "var(--font-mono)" }}>{detail.business_id}</span>
            </p>
          ) : null}
        </div>
      </div>

      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">02</div>
          <div className="portal-card-title">Attach business</div>
          <span className="portal-tag portal-tag-put">PUT</span>
        </div>
        <div className="portal-card-bd">
          <div className="portal-field">
            <div className="portal-lbl">Business id</div>
            <input
              className="portal-inp"
              placeholder="uuid"
              value={attachBizId}
              onChange={(e) => setAttachBizId(e.target.value)}
            />
          </div>
          <div className="portal-acts">
            <button
              type="button"
              className="portal-act"
              onClick={() =>
                void run(async () => {
                  if (!attachBizId.trim()) throw new Error("Business id required");
                  await attachListingBusiness(token, id, attachBizId.trim());
                })
              }
            >
              <span className="portal-tag portal-tag-put" style={{ marginRight: 4 }}>
                PUT
              </span>
              /listings/…/business
            </button>
          </div>
        </div>
      </div>

      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">03</div>
          <div className="portal-card-title">Canonical share URLs</div>
          <span className="portal-tag portal-tag-put">PUT</span>
        </div>
        <div className="portal-card-bd">
          <p style={{ margin: "0 0 12px", fontSize: 11, color: "var(--portal-muted)" }}>
            Register each URL people might paste (Instagram, Facebook, …). Matched imports skip AI parsing on mobile.
          </p>
          {detail.normalized_share_aliases.length ? (
            <ul style={{ margin: "0 0 14px", paddingLeft: "1.1rem", fontSize: 11, fontFamily: "var(--font-mono)", color: "#888" }}>
              {detail.normalized_share_aliases.map((u) => (
                <li key={u} style={{ wordBreak: "break-all" }}>
                  {u}
                </li>
              ))}
            </ul>
          ) : (
            <div className="portal-empty" style={{ marginBottom: 14 }}>
              <p>No share aliases yet.</p>
            </div>
          )}
          <div className="portal-field">
            <div className="portal-lbl">
              Official share URL <span className="portal-lbl-hint">— add another</span>
            </div>
            <input
              className="portal-inp"
              type="url"
              placeholder="https://instagram.com/…"
              value={shareUrl}
              onChange={(e) => setShareUrl(e.target.value)}
            />
          </div>
          <div className="portal-acts">
            <button
              type="button"
              className="portal-act"
              onClick={() =>
                void run(async () => {
                  if (shareUrl.trim().length < 8) throw new Error("URL required");
                  await putListingShareAlias(token, id, shareUrl.trim());
                  setShareUrl("");
                })
              }
            >
              <span className="portal-tag portal-tag-put" style={{ marginRight: 4 }}>
                PUT
              </span>
              /listings/…/share-alias
            </button>
          </div>
        </div>
      </div>

      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">04</div>
          <div className="portal-card-title">Promo video</div>
          <span className="portal-tag portal-tag-info">Moderation</span>
        </div>
        <div className="portal-card-bd">
          <div className="portal-field">
            <div className="portal-lbl">
              Storage URI <span className="portal-lbl-hint">— https object URL after upload</span>
            </div>
            <input
              className="portal-inp"
              type="url"
              placeholder="https://cdn.example.com/v.mp4"
              value={videoUri}
              onChange={(e) => setVideoUri(e.target.value)}
            />
          </div>
          <div className="portal-acts">
            <button
              type="button"
              className="portal-act"
              onClick={() =>
                void run(async () => {
                  if (videoUri.trim().length < 8) throw new Error("Storage URI required");
                  await registerEventVideo(token, id, videoUri.trim());
                })
              }
            >
              <IconVideo size={12} stroke={2} />
              <span className="portal-tag portal-tag-post" style={{ marginRight: 4 }}>
                POST
              </span>
              /event-videos
            </button>
          </div>
        </div>
      </div>

      {status ? <p className="portal-status">{status}</p> : null}
      {err ? <p className="portal-error">{err}</p> : null}

      <Link href="/listings" className="portal-link-back">
        ← All listings
      </Link>
      <Link href="/dashboard" className="portal-link-back" style={{ marginLeft: 12 }}>
        Dashboard
      </Link>
    </>
  );
}
