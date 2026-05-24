"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { IconArrowRight } from "@tabler/icons-react";
import { useAdminAuth } from "@/components/admin/admin-auth-context";
import { listAdminClaims, type AdminClaimRow } from "@/lib/eventflow-api";

export default function AdminClaimsPage() {
  const { token } = useAdminAuth();
  const [claims, setClaims] = useState<AdminClaimRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const reload = async () => {
    setLoading(true); setErr(null);
    try { setClaims(await listAdminClaims(token, { limit: 50 })); }
    catch (e: unknown) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  };

  useEffect(() => { void reload(); }, [token]);

  return (
    <>
      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">01</div>
          <div className="portal-card-title">Claims</div>
          <span className="portal-tag portal-tag-info">{claims.length} shown</span>
        </div>
        <div className="portal-card-bd">
          {err ? <p className="portal-error">{err}</p> : null}
          {loading ? <p className="portal-status">Loading…</p> : null}
          {!loading && claims.length === 0 ? <p style={{ fontSize: 12, color: "#888" }}>No claims found.</p> : null}
          {claims.length > 0 ? (
            <div style={{ overflowX: "auto" }}>
              <table className="portal-table">
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Reason</th>
                    <th>Status</th>
                    <th>Order</th>
                    <th>Created</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {claims.map((c) => (
                    <tr key={c.claim_id}>
                      <td style={{ fontSize: 12 }}>{c.claim_type}</td>
                      <td style={{ fontSize: 12, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.reason ?? "—"}</td>
                      <td><span className={`portal-tag ${c.status === "open" ? "portal-tag-warn" : c.status === "resolved_approved" ? "portal-tag-success" : "portal-tag-err"}`}>{c.status}</span></td>
                      <td style={{ fontSize: 11, fontFamily: "var(--font-mono)" }}>{c.order_id?.slice(0, 8) ?? "—"}</td>
                      <td style={{ fontSize: 12, color: "#888" }}>{new Date(c.created_at).toLocaleDateString()}</td>
                      <td><Link href={`/claims/${c.claim_id}`} className="portal-link-back">Review <IconArrowRight size={11} /></Link></td>
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
