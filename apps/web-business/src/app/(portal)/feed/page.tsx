"use client";

import { IconPlus, IconTrash } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { usePortalAuth } from "@/components/portal/portal-auth-context";
import { listMyFeedVideos, publishFeedVideo, type FeedVideoRow } from "@/lib/eventflow-api";

export default function FeedVideosPage() {
  const { token } = usePortalAuth();
  const [videos, setVideos] = useState<FeedVideoRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [videoUri, setVideoUri] = useState("");
  const [thumbnailUri, setThumbnailUri] = useState("");

  const reload = async () => {
    try { setVideos(await listMyFeedVideos(token)); }
    catch (e: unknown) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const v = await listMyFeedVideos(token);
        if (!cancelled) setVideos(v);
      } catch (e: unknown) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  const publish = async () => {
    setErr(null); setStatus(null);
    try {
      if (!title.trim() || !videoUri.trim()) throw new Error("Title and video URI required");
      await publishFeedVideo(token, {
        title: title.trim(),
        video_uri: videoUri.trim(),
        thumbnail_uri: thumbnailUri.trim() || undefined,
      });
      setTitle(""); setVideoUri(""); setThumbnailUri("");
      setStatus("Video published for moderation.");
      await reload();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  if (loading) return <p style={{ color: "#888", padding: 24 }}>Loading…</p>;

  return (
    <>
      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">01</div>
          <div className="portal-card-title">Publish video</div>
          <span className="portal-tag portal-tag-post">POST</span>
        </div>
        <div className="portal-card-bd">
          <div className="portal-field">
            <div className="portal-lbl">Title</div>
            <input className="portal-inp" type="text" placeholder="My promo video" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="portal-field">
            <div className="portal-lbl">Video URI</div>
            <input className="portal-inp" type="url" placeholder="https://cdn.example.com/video.mp4" value={videoUri} onChange={(e) => setVideoUri(e.target.value)} />
          </div>
          <div className="portal-field">
            <div className="portal-lbl">Thumbnail URI (optional)</div>
            <input className="portal-inp" type="url" placeholder="https://cdn.example.com/thumb.jpg" value={thumbnailUri} onChange={(e) => setThumbnailUri(e.target.value)} />
          </div>
          {videoUri.trim() ? (
            <div style={{ marginTop: 8 }}>
              <video src={videoUri.trim()} controls style={{ maxWidth: "100%", maxHeight: 180, borderRadius: 6, background: "#000" }} />
            </div>
          ) : null}
          <div className="portal-acts" style={{ marginTop: 12 }}>
            <button type="button" className="portal-act" onClick={() => void publish()}>
              <IconPlus size={12} /> Publish
            </button>
          </div>
        </div>
      </div>

      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">02</div>
          <div className="portal-card-title">My feed videos</div>
          <span className="portal-tag portal-tag-info">{videos.length} videos</span>
        </div>
        <div className="portal-card-bd">
          {videos.length === 0 ? (
            <p style={{ fontSize: 12, color: "#888", margin: 0 }}>No videos published yet.</p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table className="portal-table">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Views</th>
                    <th>Taps</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {videos.map((v) => (
                    <tr key={v.video_id}>
                      <td style={{ fontWeight: 500 }}>{v.title}</td>
                      <td style={{ fontSize: 12 }}>{v.video_type}</td>
                      <td>
                        <span className={`portal-tag ${v.moderation_status === "approved" ? "portal-tag-success" : v.moderation_status === "rejected" ? "portal-tag-err" : "portal-tag-info"}`}>
                          {v.moderation_status}
                        </span>
                      </td>
                      <td>{v.views}</td>
                      <td>{v.whatsapp_taps}</td>
                      <td style={{ fontSize: 12, color: "#888" }}>{v.created_at ? new Date(v.created_at).toLocaleDateString() : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {status ? <p className="portal-status">{status}</p> : null}
      {err ? <p className="portal-error">{err}</p> : null}
    </>
  );
}
