"use client";

import { IconPlus } from "@tabler/icons-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { usePortalAuth } from "@/components/portal/portal-auth-context";
import { listMineCommunityEvents, type CommunityMineRow } from "@/lib/eventflow-api";

function formatStart(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return iso;
  }
}

export default function ListingsIndexPage() {
  const { token } = usePortalAuth();
  const [rows, setRows] = useState<CommunityMineRow[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const mine = await listMineCommunityEvents(token, 100);
        if (!cancelled) setRows(mine);
      } catch (e: unknown) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <>
      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">01</div>
          <div className="portal-card-title">Your listings</div>
          <Link href="/listings/new" className="portal-tag portal-tag-post" style={{ textDecoration: "none" }}>
            New
          </Link>
        </div>
        <div className="portal-card-bd">
          <div className="portal-acts" style={{ marginTop: 0 }}>
            <Link href="/listings/new" className="portal-act" style={{ textDecoration: "none" }}>
              <IconPlus size={12} stroke={2} />
              Publish listing
            </Link>
          </div>
          {err ? <p className="portal-error">{err}</p> : null}
          {!err && rows.length === 0 ? (
            <div className="portal-empty" style={{ marginTop: 14 }}>
              <p>
                No listings yet. <span>Create one to appear in discovery.</span>
              </p>
            </div>
          ) : null}
          {rows.length > 0 ? (
            <div className="portal-table-wrap" style={{ marginTop: 14 }}>
              <table className="portal-table">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Start</th>
                    <th>Venue</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.community_event_id}>
                      <td>
                        <Link href={`/listings/${r.community_event_id}`} style={{ fontWeight: 500 }}>
                          {r.title}
                        </Link>
                      </td>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--portal-muted)" }}>
                        {formatStart(r.start_time)}
                      </td>
                      <td>{r.venue}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </div>
    </>
  );
}
