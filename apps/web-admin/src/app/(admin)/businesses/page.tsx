"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useAdminAuth } from "@/components/admin/admin-auth-context";
import { listAdminBusinesses, type AdminBusinessRow } from "@/lib/eventflow-api";

const LIMIT = 25;

export default function AdminBusinessesPage() {
  const { token } = useAdminAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const page = Math.max(1, parseInt(searchParams.get("page") ?? "1", 10) || 1);
  const q = searchParams.get("q") ?? "";
  const offset = (page - 1) * LIMIT;

  const [rows, setRows] = useState<AdminBusinessRow[]>([]);
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
        const res = await listAdminBusinesses(token, { limit: LIMIT, offset, q: q || undefined });
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
      router.push(qs ? `/businesses?${qs}` : "/businesses");
    },
    [page, q, router]
  );

  const totalPages = Math.max(1, Math.ceil(total / LIMIT));

  return (
    <div className="portal-card">
      <div className="portal-card-hd">
        <div className="portal-card-num">02</div>
        <div className="portal-card-title">Businesses</div>
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
            placeholder="Search name…"
            value={searchDraft}
            onChange={(e) => setSearchDraft(e.target.value)}
            style={{ flex: "1 1 200px", maxWidth: 320 }}
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
                <th>Name</th>
                <th>Owner</th>
                <th>Verified</th>
                <th>WhatsApp</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.business_id}>
                  <td>{r.name}</td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{r.owner_user_id}</td>
                  <td>{r.verified ? "yes" : "no"}</td>
                  <td style={{ color: "var(--portal-muted)" }}>{r.whatsapp_e164 ?? "—"}</td>
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
