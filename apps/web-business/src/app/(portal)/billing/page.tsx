"use client";

import { IconReceipt } from "@tabler/icons-react";
import { useState } from "react";
import { usePortalAuth } from "@/components/portal/portal-auth-context";
import { postBillingCheckout } from "@/lib/eventflow-api";

export default function BillingPage() {
  const { token } = usePortalAuth();
  const [status, setStatus] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const runCheckout = async () => {
    setErr(null);
    setStatus(null);
    setBusy(true);
    const popup = window.open("", "_blank", "noopener,noreferrer");
    try {
      const out = await postBillingCheckout(token);
      setStatus(`Checkout URL issued (${out.provider}).`);
      if (out.checkout_url && popup) popup.location.href = out.checkout_url;
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
      popup?.close();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="portal-card">
      <div className="portal-card-hd">
        <div className="portal-card-num">01</div>
        <div className="portal-card-title">Billing stub</div>
        <span className="portal-tag portal-tag-post">POST</span>
      </div>
      <div className="portal-card-bd">
        <div className="portal-info-box">
          <IconReceipt size={16} stroke={1.5} color="#2e2e2e" />
          <div>
            <div className="portal-info-box-t">Checkout session</div>
            <div className="portal-info-box-s">Creates a Stripe-compatible checkout session for this account.</div>
          </div>
        </div>
        <div className="portal-acts">
          <button type="button" className="portal-act" disabled={busy} onClick={() => void runCheckout()}>
            <IconReceipt size={12} stroke={2} />
            <span className="portal-tag portal-tag-post" style={{ marginRight: 4 }}>
              POST
            </span>
            /billing/checkout-session
          </button>
        </div>
        {status ? <p className="portal-status">{status}</p> : null}
        {err ? <p className="portal-error">{err}</p> : null}
      </div>
    </div>
  );
}
