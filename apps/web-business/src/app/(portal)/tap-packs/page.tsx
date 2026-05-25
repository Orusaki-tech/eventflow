"use client";

import { useEffect, useState } from "react";
import { usePortalAuth } from "@/components/portal/portal-auth-context";
import { getTapStatus, buyTapPack } from "@/lib/eventflow-api";

const PLANS = [
  { id: "starter", label: "Starter", taps: 10, price: 200 },
  { id: "growth", label: "Growth", taps: 50, price: 750 },
  { id: "pro", label: "Pro", taps: 200, price: 2500 },
  { id: "unlimited", label: "Unlimited", taps: null, price: 5000 },
] as const;

export default function TapPacksPage() {
  const { token } = usePortalAuth();
  const [tapStatus, setTapStatus] = useState<{ business_id: string; tap_balance: number; tap_plan: string; pricing: Record<string, { price_minor: number; taps?: number | null }> } | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const s = await getTapStatus(token);
        if (!cancelled) setTapStatus(s);
      } catch (e: unknown) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  const buy = async (plan: string) => {
    setErr(null); setStatus(null);
    try {
      const res = await buyTapPack(token, plan);
      setTapStatus(res);
      setStatus(`Purchased ${plan} plan. Balance: ${res.tap_balance} taps.`);
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
          <div className="portal-card-title">Tap packs</div>
          <span className="portal-tag portal-tag-info">WhatsApp taps</span>
        </div>
        <div className="portal-card-bd">
          {tapStatus && (
            <div className="portal-info-box" style={{ marginBottom: 16 }}>
              <div>
                <div className="portal-info-box-t">Current balance</div>
                <div className="portal-info-box-s" style={{ fontSize: 24, fontWeight: 600 }}>{tapStatus.tap_balance} taps</div>
                <p style={{ margin: "4px 0 0", fontSize: 11, color: "#888" }}>Plan: {tapStatus.tap_plan}</p>
              </div>
            </div>
          )}
          <div className="portal-grid4" style={{ gap: 12 }}>
            {PLANS.map((plan) => (
              <div key={plan.id} className="portal-empty" style={{ textAlign: "center", padding: 16 }}>
                <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>{plan.label}</div>
                <div style={{ fontSize: 22, fontWeight: 700, margin: "6px 0" }}>
                  KES {plan.price.toLocaleString()}
                </div>
                <div style={{ fontSize: 12, color: "#888", marginBottom: 10 }}>
                  {plan.taps ? `${plan.taps} taps` : "Unlimited taps / mo"}
                </div>
                <button type="button" className="portal-act"
                  disabled={tapStatus?.tap_plan === plan.id}
                  onClick={() => void buy(plan.id)}
                  style={tapStatus?.tap_plan === plan.id ? { opacity: 0.5, cursor: "default" } : {}}>
                  {tapStatus?.tap_plan === plan.id ? "Active" : "Buy"}
                </button>
              </div>
            ))}
          </div>
          {status ? <p className="portal-status" style={{ marginTop: 12 }}>{status}</p> : null}
          {err ? <p className="portal-error" style={{ marginTop: 12 }}>{err}</p> : null}
        </div>
      </div>
    </>
  );
}
