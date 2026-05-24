"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useAdminAuth } from "@/components/admin/admin-auth-context";
import { listAdminCommunityEvents, type AdminCommunityEventRow } from "@/lib/eventflow-api";

const LIMIT = 25;

export default function AdminListingsPage() {
  const { token } = useAdminAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const page = Math.max(1, parseInt(searchParams.get("page") ?? "1", 10) || 1);
  const q = searchParams.get("q") ?? "";
  const offset = (page - 1) * LIMIT;

  const [rows, setRows] = useState<AdminCommunityEventRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [searchDraft, setSearchDraft] = useState(q);

  useEffect(() => {
    setSearchDraft(q);
  }, [q]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await listAdminCommunityEvents(token, { limit: LIMIT, offset, q: q || undefined });
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
  }, [token, offset, q]);

  const pushQuery = useCallback(
    (next: { page?: number; q?: string }) => {
      const p = new URLSearchParams();
      const pg = next.page ?? page;
      const qq = next.q !== undefined ? next.q : q;
      if (pg > 1) p.set("page", String(pg));
      if (qq.trim()) p.set("q", qq.trim());
      const qs = p.toString();
      router.push(qs ? `/listings?${qs}` : "/listings");
    },
    [page, q, router]
  );

  const totalPages = Math.max(1, Math.ceil(total / LIMIT));

  return (
    <div className="portal-card">
      <div className="portal-card-hd">
        <div className="portal-card-num">03</div>
        <div className="portal-card-title">Community listings</div>
      </div>
      <div className="portal-card-bd">
        <form
          style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}
          onSubmit={(e) => {
            e.preventDefault();
            pushQuery({ page: 1, q: searchDraft });
          }}
        >
          <input
            type="search"
            placeholder="Search title or venue…"
            value={searchDraft}
            onChange={(e) => setSearchDraft(e.target.value)}
            style={{ flex: "1 1 200px", maxWidth: 360 }}
          />
          <button type="submit">Search</button>
          {q ? (
            <button type="button" className="portal-act" onClick={() => pushQuery({ page: 1, q: "" })}>
              Clear
            </button>
          ) : null}
        </form>

        {loadErr ? <p className="portal-error">{loadErr}</p> : null}

        <div style={{ overflowX: "auto" }}>
          <table className="portal-table">
            <thead>
              <tr>
                <th></th>
                <th>Title</th>
                <th>When</th>
                <th>Venue</th>
                <th>Source</th>
                <th>Author</th>
                <th>Business</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.community_event_id}>
                  <td style={{ padding: "4px 0" }}>
                    {r.poster_image_uri ? (
                      <img
                        src={r.poster_image_uri}
                        alt=""
                        style={{ width: 48, height: 48, borderRadius: 4, objectFit: "cover", background: "#222" }}
                      />
                    ) : (
                      <span style={{ color: "#555", fontSize: 10 }}>—</span>
                    )}
                  </td>
                  <td>{r.title}</td>
                  <td style={{ whiteSpace: "nowrap", fontSize: 11 }}>{new Date(r.start_time).toISOString().slice(0, 16)}</td>
                  <td>{r.venue}</td>
                  <td>{r.source}</td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{r.user_id}</td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>
                    {r.attached_business_id ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p style={{ marginTop: 12, fontSize: 12, color: "var(--portal-muted)" }}>
          {total} total · page {page} / {totalPages}
        </p>
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button type="button" disabled={page <= 1} onClick={() => pushQuery({ page: page - 1 })}>
            Previous
          </button>
          <button type="button" disabled={page >= totalPages} onClick={() => pushQuery({ page: page + 1 })}>
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
