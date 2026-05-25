"use client";

import { useEffect, useState } from "react";
import { usePortalAuth } from "@/components/portal/portal-auth-context";
import { listAffiliateRequests, approveAffiliateRequest } from "@/lib/eventflow-api";

function minorToKes(amount: number) {
  return (amount / 100).toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function AffiliateRequestsPage() {
  const { token } = usePortalAuth();
  const [requests, setRequests] = useState<{ link_id: string; title: string; price_minor_units: number; seller_name: string; status: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const reload = async () => {
    try { setRequests(await listAffiliateRequests(token)); }
    catch (e: unknown) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(false); }
  };

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const r = await listAffiliateRequests(token);
        if (!cancelled) setRequests(r);
      } catch (e: unknown) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  const approve = async (linkId: string) => {
    setErr(null); setStatus(null);
    try {
      await approveAffiliateRequest(token, linkId, {
        commission_seller_percent: 80,
        commission_owner_percent: 10,
        commission_platform_percent: 10,
      });
      setStatus("Affiliate request approved.");
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
          <div className="portal-card-title">Affiliate requests</div>
          <span className="portal-tag portal-tag-info">Incoming</span>
        </div>
        <div className="portal-card-bd">
          <p style={{ margin: "0 0 12px", fontSize: 12, color: "var(--portal-muted)" }}>
            Other businesses want to sell their products alongside your event listings. Review and approve with default
            commission split (seller 80%, you 10%, platform 10%).
          </p>
          {requests.length === 0 ? (
            <p style={{ fontSize: 12, color: "#888", margin: 0 }}>No incoming affiliate requests yet.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {requests.map((r) => (
                <div key={r.link_id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 12px", background: "#f5f5f5", borderRadius: 8 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 500, fontSize: 13 }}>{r.title}</div>
                    <div style={{ fontSize: 11, color: "#888" }}>
                      KES {minorToKes(r.price_minor_units)} • by {r.seller_name}
                    </div>
                  </div>
                  {r.status === "pending" ? (
                    <button type="button" className="portal-act" onClick={() => void approve(r.link_id)}>
                      Approve
                    </button>
                  ) : (
                    <span className="portal-tag portal-tag-success">Approved</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {status ? <p className="portal-status">{status}</p> : null}
      {err ? <p className="portal-error">{err}</p> : null}
    </>
  );
}
