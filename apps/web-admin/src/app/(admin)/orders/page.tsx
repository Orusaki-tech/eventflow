"use client";

import { useEffect, useState } from "react";
import { useAdminAuth } from "@/components/admin/admin-auth-context";
import { listAdminOrders, type AdminOrderRow } from "@/lib/eventflow-api";

function minorToKes(amount: number) {
  return (amount / 100).toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function AdminOrdersPage() {
  const { token } = useAdminAuth();
  const [orders, setOrders] = useState<AdminOrderRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const reload = async () => {
    setLoading(true); setErr(null);
    try { setOrders(await listAdminOrders(token, { limit: 50 })); }
    catch (e: unknown) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  };

  useEffect(() => { void reload(); }, [token]);

  return (
    <>
      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">01</div>
          <div className="portal-card-title">Orders</div>
          <span className="portal-tag portal-tag-info">{orders.length} shown</span>
        </div>
        <div className="portal-card-bd">
          {err ? <p className="portal-error">{err}</p> : null}
          {loading ? <p className="portal-status">Loading…</p> : null}
          {!loading && orders.length === 0 ? <p style={{ fontSize: 12, color: "#888" }}>No orders found.</p> : null}
          {orders.length > 0 ? (
            <div style={{ overflowX: "auto" }}>
              <table className="portal-table">
                <thead>
                  <tr>
                    <th>Event</th>
                    <th>User</th>
                    <th>Total</th>
                    <th>Fee</th>
                    <th>Provider</th>
                    <th>Status</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.map((o) => (
                    <tr key={o.order_id}>
                      <td style={{ fontSize: 12, maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{o.event_title}</td>
                      <td style={{ fontSize: 11, fontFamily: "var(--font-mono)" }}>{o.user_id.slice(0, 8)}…</td>
                      <td style={{ fontWeight: 500 }}>KES {minorToKes(o.total_minor)}</td>
                      <td style={{ color: "#b91c1c", fontSize: 12 }}>KES {minorToKes(o.fee_minor)}</td>
                      <td style={{ fontSize: 12 }}>{o.payment_provider ?? "—"}</td>
                      <td><span className={`portal-tag ${o.status === "paid" ? "portal-tag-success" : o.status === "pending" ? "portal-tag-warn" : "portal-tag-err"}`}>{o.status}</span></td>
                      <td style={{ fontSize: 12, color: "#888" }}>{new Date(o.created_at).toLocaleDateString()}</td>
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
