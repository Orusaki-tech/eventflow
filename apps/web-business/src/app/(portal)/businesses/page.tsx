"use client";

import { useEffect, useState } from "react";
import { usePortalAuth } from "@/components/portal/portal-auth-context";
import { listBusinesses, patchBusiness, type BusinessRow } from "@/lib/eventflow-api";

export default function BusinessesPage() {
  const { token } = usePortalAuth();
  const [rows, setRows] = useState<BusinessRow[]>([]);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [wa, setWa] = useState("");
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const biz = await listBusinesses(token);
        if (!cancelled) setRows(biz);
      } catch (e: unknown) {
        if (!cancelled) setLoadErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const startEdit = (b: BusinessRow) => {
    setEditingId(b.business_id);
    setName(b.name);
    setWa(b.whatsapp_e164 ?? "");
    setSaveErr(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setSaveErr(null);
  };

  const save = async () => {
    if (!editingId) return;
    setSaving(true);
    setSaveErr(null);
    try {
      const trimmedWa = wa.trim();
      await patchBusiness(token, editingId, {
        name: name.trim() || undefined,
        whatsapp_e164: trimmedWa.length ? trimmedWa : null,
      });
      const biz = await listBusinesses(token);
      setRows(biz);
      setEditingId(null);
    } catch (e: unknown) {
      setSaveErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">01</div>
          <div className="portal-card-title">Your businesses</div>
          <span className="portal-tag portal-tag-info">PATCH</span>
        </div>
        <div className="portal-card-bd">
          <p style={{ margin: "0 0 14px", fontSize: 12, color: "var(--portal-muted)" }}>
            Profiles tied to your account (often created from mobile). Copy <strong>business id</strong> when attaching a
            listing.
          </p>
          {loadErr ? <p className="portal-error">{loadErr}</p> : null}
          {!loadErr && rows.length === 0 ? (
            <div className="portal-empty">
              <p>
                No businesses yet. <span>Create one from the EventFlow mobile app.</span>
              </p>
            </div>
          ) : null}
          {rows.length > 0 ? (
            <div className="portal-table-wrap">
              <table className="portal-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>WhatsApp</th>
                    <th>Verified</th>
                    <th>Id</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((b) => (
                    <tr key={b.business_id}>
                      <td>{b.name}</td>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{b.whatsapp_e164 ?? "—"}</td>
                      <td>{b.verified ? "yes" : "no"}</td>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: 10, wordBreak: "break-all" }}>
                        {b.business_id}
                      </td>
                      <td>
                        {editingId === b.business_id ? (
                          <button type="button" className="portal-act" onClick={cancelEdit}>
                            Cancel
                          </button>
                        ) : (
                          <button type="button" className="portal-act" onClick={() => startEdit(b)}>
                            Edit
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          {editingId ? (
            <div style={{ marginTop: 18, paddingTop: 18, borderTop: "1px solid var(--portal-border)" }}>
              <div className="portal-field">
                <div className="portal-lbl">Name</div>
                <input className="portal-inp" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="portal-field">
                <div className="portal-lbl">WhatsApp E.164</div>
                <input className="portal-inp" value={wa} onChange={(e) => setWa(e.target.value)} placeholder="+254700000000" />
              </div>
              {saveErr ? <p className="portal-error">{saveErr}</p> : null}
              <div className="portal-acts">
                <button type="button" className="portal-act" disabled={saving} onClick={() => void save()}>
                  Save changes
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </>
  );
}
