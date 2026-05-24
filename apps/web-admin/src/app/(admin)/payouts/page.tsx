"use client";

import { useEffect, useState } from "react";
import { useAdminAuth } from "@/components/admin/admin-auth-context";
import { listAdminPayouts, processAdminPayout, type AdminPayoutRow } from "@/lib/eventflow-api";

function minorToKes(amount: number) {
  return (amount / 100).toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function AdminPayoutsPage() {
  const { token } = useAdminAuth();
  const [payouts, setPayouts] = useState<AdminPayoutRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const reload = async () => {
    setLoading(true); setErr(null);
    try { setPayouts(await listAdminPayouts(token, { limit: 50 })); }
    catch (e: unknown) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  };

  useEffect(() => { void reload(); }, [token]);

  const markPaid = async (payoutId: string) => {
    setErr(null); setStatus(null);
    try {
      await processAdminPayout(token, payoutId);
      setStatus(`Payout ${payoutId.slice(0, 8)} marked as paid.`);
      await reload();
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : String(e)); }
  };

  return (
    <>
      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">01</div>
          <div className="portal-card-title">Business payouts</div>
          <span className="portal-tag portal-tag-info">{payouts.length} shown</span>
        </div>
        <div className="portal-card-bd">
          {err ? <p className="portal-error">{err}</p> : null}
          {loading ? <p className="portal-status">Loading…</p> : null}
          {!loading && payouts.length === 0 ? <p style={{ fontSize: 12, color: "#888" }}>No payouts found.</p> : null}
          {payouts.length > 0 ? (
            <div style={{ overflowX: "auto" }}>
              <table className="portal-table">
                <thead>
                  <tr>
                    <th>Business</th>
                    <th>Gross</th>
                    <th>Fees</th>
                    <th>Net</th>
                    <th>Status</th>
                    <th>Reference</th>
                    <th>Date</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {payouts.map((p) => (
                    <tr key={p.payout_id}>
                      <td style={{ fontWeight: 500, fontSize: 12 }}>{p.business_name}</td>
                      <td style={{ fontSize: 12 }}>KES {minorToKes(p.gross_minor)}</td>
                      <td style={{ color: "#b91c1c", fontSize: 12 }}>KES {minorToKes(p.fees_minor)}</td>
                      <td style={{ fontWeight: 600 }}>KES {minorToKes(p.net_minor)}</td>
                      <td><span className={`portal-tag ${p.status === "paid" ? "portal-tag-success" : "portal-tag-warn"}`}>{p.status}</span></td>
                      <td style={{ fontSize: 11, fontFamily: "var(--font-mono)" }}>{p.reference ?? "—"}</td>
                      <td style={{ fontSize: 12, color: "#888" }}>{new Date(p.created_at).toLocaleDateString()}</td>
                      <td>
                        {p.status !== "paid" ? (
                          <button type="button" className="portal-act" style={{ fontSize: 11 }} onClick={() => void markPaid(p.payout_id)}>
                            Mark paid
                          </button>
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
