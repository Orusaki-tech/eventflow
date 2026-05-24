"use client";

import { useEffect, useState } from "react";
import { useAdminAuth } from "@/components/admin/admin-auth-context";
import { listAdminFeedVideos, moderateAdminFeedVideo, type AdminFeedVideoRow } from "@/lib/eventflow-api";

export default function VideoModerationPage() {
  const { token } = useAdminAuth();
  const [videos, setVideos] = useState<AdminFeedVideoRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const reload = async () => {
    setLoading(true); setErr(null);
    try { setVideos(await listAdminFeedVideos(token, { limit: 50 })); }
    catch (e: unknown) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  };

  useEffect(() => { void reload(); }, [token]);

  const moderate = async (videoId: string, moderation_status: "approved" | "rejected") => {
    setErr(null); setStatus(null);
    try {
      await moderateAdminFeedVideo(token, videoId, { moderation_status });
      setStatus(`Video ${videoId.slice(0, 8)} ${moderation_status}.`);
      await reload();
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : String(e)); }
  };

  return (
    <>
      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">01</div>
          <div className="portal-card-title">Feed video moderation</div>
          <span className="portal-tag portal-tag-info">{videos.length} shown</span>
        </div>
        <div className="portal-card-bd">
          {err ? <p className="portal-error">{err}</p> : null}
          {loading ? <p className="portal-status">Loading…</p> : null}
          {!loading && videos.length === 0 ? <p style={{ fontSize: 12, color: "#888" }}>No videos found.</p> : null}
          {videos.length > 0 ? (
            <div style={{ overflowX: "auto" }}>
              <table className="portal-table">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Business</th>
                    <th>Status</th>
                    <th>Views</th>
                    <th>Date</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {videos.map((v) => (
                    <tr key={v.video_id}>
                      <td style={{ fontWeight: 500, fontSize: 12, maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{v.title}</td>
                      <td style={{ fontSize: 12 }}>{v.business_name ?? "—"}</td>
                      <td><span className={`portal-tag ${v.moderation_status === "approved" ? "portal-tag-success" : v.moderation_status === "rejected" ? "portal-tag-err" : "portal-tag-warn"}`}>{v.moderation_status}</span></td>
                      <td>{v.views}</td>
                      <td style={{ fontSize: 12, color: "#888" }}>{new Date(v.created_at).toLocaleDateString()}</td>
                      <td>
                        {v.moderation_status === "pending" ? (
                          <div style={{ display: "flex", gap: 6 }}>
                            <button type="button" className="portal-act" style={{ fontSize: 11, background: "#166534", color: "#fff" }} onClick={() => void moderate(v.video_id, "approved")}>Approve</button>
                            <button type="button" className="portal-act" style={{ fontSize: 11, background: "#991b1b", color: "#fff" }} onClick={() => void moderate(v.video_id, "rejected")}>Reject</button>
                          </div>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </div>

      {status ? <p className="portal-status">{status}</p> : null}
    </>
  );
}
