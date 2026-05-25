"use client";

import { useEffect, useState } from "react";
import { usePortalAuth } from "@/components/portal/portal-auth-context";
import { getPayoutSettings, updatePayoutSettings, listPayouts, requestPayout, type PayoutSettings, type PayoutRow } from "@/lib/eventflow-api";

function minorToKes(amount: number) {
  return (amount / 100).toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function PayoutsPage() {
  const { token } = usePortalAuth();
  const [settings, setSettings] = useState<PayoutSettings | null>(null);
  const [payouts, setPayouts] = useState<PayoutRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [method, setMethod] = useState("mpesa_till");
  const [till, setTill] = useState("");
  const [paybill, setPaybill] = useState("");
  const [bankName, setBankName] = useState("");
  const [freq, setFreq] = useState("manual");
  const [minPayout, setMinPayout] = useState("50000");

  const reload = async () => {
    try {
      const [s, p] = await Promise.all([
        getPayoutSettings(token),
        listPayouts(token),
      ]);
      setSettings(s);
      setPayouts(p);
      setMethod(s.payout_method);
      setTill(s.mpesa_till_number ?? "");
      setPaybill(s.mpesa_paybill_number ?? "");
      setBankName(s.bank_name ?? "");
      setFreq(s.payout_frequency);
      setMinPayout(String(s.minimum_payout_minor));
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const [s, p] = await Promise.all([
          getPayoutSettings(token),
          listPayouts(token),
        ]);
        if (!cancelled) {
          setSettings(s);
          setPayouts(p);
          setMethod(s.payout_method);
          setTill(s.mpesa_till_number ?? "");
          setPaybill(s.mpesa_paybill_number ?? "");
          setBankName(s.bank_name ?? "");
          setFreq(s.payout_frequency);
          setMinPayout(String(s.minimum_payout_minor));
        }
      } catch (e: unknown) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  const saveSettings = async () => {
    setErr(null); setStatus(null);
    try {
      await updatePayoutSettings(token, {
        payout_method: method as PayoutSettings["payout_method"],
        mpesa_till_number: till || null,
        mpesa_paybill_number: paybill || null,
        bank_name: bankName || null,
        payout_frequency: freq as PayoutSettings["payout_frequency"],
        minimum_payout_minor: parseInt(minPayout) || 50000,
      });
      setStatus("Payout settings saved.");
      await reload();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  const reqPayout = async () => {
    setErr(null); setStatus(null);
    try {
      const r = await requestPayout(token);
      setStatus(`Payout requested: KES ${minorToKes(r.amount_minor)} (${r.status})`);
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
          <div className="portal-card-title">Payout settings</div>
          <span className="portal-tag portal-tag-put">PUT</span>
        </div>
        <div className="portal-card-bd">
          <div className="portal-field">
            <div className="portal-lbl">Payout method</div>
            <select className="portal-inp" value={method} onChange={(e) => setMethod(e.target.value)}>
              <option value="mpesa_till">M-Pesa Till</option>
              <option value="mpesa_paybill">M-Pesa Paybill</option>
              <option value="bank">Bank Transfer</option>
            </select>
          </div>
          {method === "mpesa_till" && (
            <div className="portal-field">
              <div className="portal-lbl">Till number</div>
              <input className="portal-inp" type="text" placeholder="123456" value={till} onChange={(e) => setTill(e.target.value)} />
            </div>
          )}
          {method === "mpesa_paybill" && (
            <>
              <div className="portal-field">
                <div className="portal-lbl">Paybill number</div>
                <input className="portal-inp" type="text" placeholder="123456" value={paybill} onChange={(e) => setPaybill(e.target.value)} />
              </div>
            </>
          )}
          {method === "bank" && (
            <div className="portal-field">
              <div className="portal-lbl">Bank name</div>
              <input className="portal-inp" type="text" placeholder="Equity Bank" value={bankName} onChange={(e) => setBankName(e.target.value)} />
            </div>
          )}
          <div className="portal-field">
            <div className="portal-lbl">Payout frequency</div>
            <select className="portal-inp" value={freq} onChange={(e) => setFreq(e.target.value)}>
              <option value="manual">Manual (request per payout)</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
          <div className="portal-field">
            <div className="portal-lbl">Minimum payout (minor units, KES 500 = 50000)</div>
            <input className="portal-inp" type="number" value={minPayout} onChange={(e) => setMinPayout(e.target.value)} />
          </div>
          <div className="portal-acts" style={{ marginTop: 12 }}>
            <button type="button" className="portal-act" onClick={() => void saveSettings()}>
              Save settings
            </button>
          </div>
        </div>
      </div>

      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">02</div>
          <div className="portal-card-title">Request payout</div>
          <span className="portal-tag portal-tag-post">POST</span>
        </div>
        <div className="portal-card-bd">
          <p style={{ margin: "0 0 12px", fontSize: 12, color: "var(--portal-muted)" }}>
            Submit a payout request for your available balance. An admin will review and process it.
          </p>
          <div className="portal-acts">
            <button type="button" className="portal-act" onClick={() => void reqPayout()}>
              Request payout
            </button>
          </div>
        </div>
      </div>

      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">03</div>
          <div className="portal-card-title">Payout history</div>
          <span className="portal-tag portal-tag-info">{payouts.length} payouts</span>
        </div>
        <div className="portal-card-bd">
          {payouts.length === 0 ? (
            <p style={{ fontSize: 12, color: "#888", margin: 0 }}>No payout requests yet.</p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table className="portal-table">
                <thead>
                  <tr>
                    <th>Period</th>
                    <th>Gross</th>
                    <th>Fees</th>
                    <th>Net</th>
                    <th>Status</th>
                    <th>Reference</th>
                    <th>Paid at</th>
                  </tr>
                </thead>
                <tbody>
                  {payouts.map((p) => (
                    <tr key={p.payout_id}>
                      <td style={{ fontSize: 12 }}>{new Date(p.period_start).toLocaleDateString()} – {new Date(p.period_end).toLocaleDateString()}</td>
                      <td>KES {minorToKes(p.gross_minor_units)}</td>
                      <td style={{ color: "#b91c1c" }}>KES {minorToKes(p.fees_minor_units)}</td>
                      <td style={{ fontWeight: 600 }}>KES {minorToKes(p.net_minor_units)}</td>
                      <td><span className={`portal-tag ${p.status === "paid" ? "portal-tag-success" : p.status === "processing" ? "portal-tag-info" : "portal-tag-warn"}`}>{p.status}</span></td>
                      <td style={{ fontSize: 11, fontFamily: "var(--font-mono)" }}>{p.payment_reference ?? "—"}</td>
                      <td style={{ fontSize: 12 }}>{p.paid_at ? new Date(p.paid_at).toLocaleDateString() : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {status ? <p className="portal-status">{status}</p> : null}
      {err ? <p className="portal-error">{err}</p> : null}
    </>
  );
}
