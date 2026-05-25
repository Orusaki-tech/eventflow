"use client";

import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useAdminAuth } from "@/components/admin/admin-auth-context";
import { listAdminClaims, resolveAdminClaim, type AdminClaimRow } from "@/lib/eventflow-api";

export default function ClaimDetailPage() {
  const { token } = useAdminAuth();
  const params = useParams();
  const id = typeof params.id === "string" ? params.id : "";
  const [claim, setClaim] = useState<AdminClaimRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    if (!id) return;
    setLoading(true);
    let cancelled = false;
    void (async () => {
      try {
        const claims = await listAdminClaims(token, { limit: 10000 });
        const found = claims.find((c) => c.claim_id === id);
        if (!cancelled) {
          if (found) setClaim(found);
          else throw new Error("Claim not found");
        }
      } catch (e: unknown) { if (!cancelled) setErr(e instanceof Error ? e.message : String(e)); }
      finally { if (!cancelled) setLoading(false); }
    })();
    return () => {
      cancelled = true;
      mountedRef.current = false;
    };
  }, [token, id]);

  const resolve = async (resolution: "resolved_approved" | "resolved_denied") => {
    if (!mountedRef.current) return;
    setBusy(true);
    setErr(null); setStatus(null);
    try {
      await resolveAdminClaim(token, id, {
        claim_type: resolution,
        admin_notes: reason.trim() || null,
      });
      if (mountedRef.current) setStatus(`Claim ${resolution}.`);
    } catch (e: unknown) { if (mountedRef.current) setErr(e instanceof Error ? e.message : String(e)); }
    finally { if (mountedRef.current) setBusy(false); }
  };

  if (!id) return <p className="portal-error">Invalid claim ID.</p>;
  if (loading) return <p className="portal-status">Loading…</p>;
  if (err) return <p className="portal-error">{err}</p>;
  if (!claim) return <p className="portal-error">Claim not found.</p>;

  return (
    <>
      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">01</div>
          <div className="portal-card-title">Claim {claim.claim_id.slice(0, 8)}</div>
          <span className={`portal-tag ${claim.status === "open" ? "portal-tag-warn" : claim.status === "resolved_approved" ? "portal-tag-success" : "portal-tag-err"}`}>{claim.status}</span>
        </div>
        <div className="portal-card-bd">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: 13, marginBottom: 16 }}>
            <div><span style={{ color: "#888" }}>Type:</span> {claim.claim_type}</div>
            <div><span style={{ color: "#888" }}>Order:</span> {claim.order_id ?? "—"}</div>
            <div style={{ gridColumn: "1 / -1" }}><span style={{ color: "#888" }}>Reason:</span> {claim.reason ?? "No reason provided."}</div>
            <div><span style={{ color: "#888" }}>Created:</span> {new Date(claim.created_at).toLocaleString()}</div>
            <div><span style={{ color: "#888" }}>Resolved:</span> {claim.resolved_at ? new Date(claim.resolved_at).toLocaleString() : "—"}</div>
            {claim.admin_notes ? (
              <div style={{ gridColumn: "1 / -1" }}><span style={{ color: "#888" }}>Admin notes:</span> {claim.admin_notes}</div>
            ) : null}
          </div>

          {claim.status === "open" ? (
            <>
              <div className="portal-field">
                <div className="portal-lbl">Resolution note</div>
                <textarea className="portal-inp" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Optional notes…" />
              </div>
              <div className="portal-acts" style={{ marginTop: 12 }}>
                <button type="button" className="portal-act" disabled={busy} onClick={() => void resolve("resolved_approved")} style={{ background: "#166534", color: "#fff" }}>
                  Approve & refund
                </button>
                <button type="button" className="portal-act" disabled={busy} onClick={() => void resolve("resolved_denied")} style={{ background: "#991b1b", color: "#fff" }}>
                  Deny
                </button>
              </div>
            </>
          ) : null}
        </div>
      </div>

      {status ? <p className="portal-status">{status}</p> : null}
      {err ? <p className="portal-error">{err}</p> : null}
    </>
  );
}
