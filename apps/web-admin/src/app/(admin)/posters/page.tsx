"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useAdminAuth } from "@/components/admin/admin-auth-context";
import { listAdminPosterAssets, type AdminPosterAssetRow } from "@/lib/eventflow-api";

const LIMIT = 25;

export default function AdminPostersPage() {
  const { token } = useAdminAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const page = Math.max(1, parseInt(searchParams.get("page") ?? "1", 10) || 1);
  const offset = (page - 1) * LIMIT;

  const [rows, setRows] = useState<AdminPosterAssetRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loadErr, setLoadErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await listAdminPosterAssets(token, { limit: LIMIT, offset });
        if (!cancelled) {
          setRows(res.items);
          setTotal(res.total);
        }
      } catch (e: unknown) {
        if (!cancelled) setLoadErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, offset]);

  const pushPage = useCallback(
    (nextPage: number) => {
      const p = new URLSearchParams();
      if (nextPage > 1) p.set("page", String(nextPage));
      const qs = p.toString();
      router.push(qs ? `/posters?${qs}` : "/posters");
    },
    [router]
  );

  const totalPages = Math.max(1, Math.ceil(total / LIMIT));

  return (
    <div className="portal-card">
      <div className="portal-card-hd">
        <div className="portal-card-num">04</div>
        <div className="portal-card-title">Poster assets</div>
      </div>
      <div className="portal-card-bd">
        <p style={{ margin: "0 0 14px", fontSize: 12, color: "var(--portal-muted)" }}>
          Rows link into <code style={{ color: "inherit" }}>event_sources</code> for draft and scheduled-event association
          counts.
        </p>

        {loadErr ? <p className="portal-error">{loadErr}</p> : null}

        <div style={{ overflowX: "auto" }}>
          <table className="portal-table">
            <thead>
              <tr>
                <th>SHA256</th>
                <th>dhash</th>
                <th>Type</th>
                <th>Sources</th>
                <th>Drafts</th>
                <th>Events</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.poster_asset_id}>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 10, maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis" }}>
                    {r.content_sha256 ?? "—"}
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 10 }}>{r.dhash64}</td>
                  <td>{r.content_type}</td>
                  <td>{r.event_source_links}</td>
                  <td>{r.draft_links}</td>
                  <td>{r.scheduled_event_links}</td>
                  <td style={{ whiteSpace: "nowrap", fontSize: 11 }}>{new Date(r.created_at).toISOString().slice(0, 16)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p style={{ marginTop: 12, fontSize: 12, color: "var(--portal-muted)" }}>
          {total} total · page {page} / {totalPages}
        </p>
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button type="button" disabled={page <= 1} onClick={() => pushPage(page - 1)}>
            Previous
          </button>
          <button type="button" disabled={page >= totalPages} onClick={() => pushPage(page + 1)}>
            Next
          </button>
          <Link href="/" className="portal-link-back" style={{ marginLeft: "auto" }}>
            Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
