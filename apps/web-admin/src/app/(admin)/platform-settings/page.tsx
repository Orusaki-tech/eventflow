"use client";

import { useCallback, useEffect, useState } from "react";
import { useAdminAuth } from "@/components/admin/admin-auth-context";
import { listPlatformSettings, updatePlatformSetting, type PlatformSettingsRow } from "@/lib/eventflow-api";

export default function PlatformSettingsPage() {
  const { token } = useAdminAuth();
  const [settings, setSettings] = useState<PlatformSettingsRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [editKey, setEditKey] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      setSettings(await listPlatformSettings(token));
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const save = async (key: string) => {
    setSaving(true);
    setErr(null); setStatus(null);
    try {
      let parsed: Record<string, unknown>;
      try { parsed = JSON.parse(editValue); }
      catch { throw new Error("Invalid JSON"); }
      await updatePlatformSetting(token, key, parsed);
      setStatus(`"${key}" updated.`);
      setEditKey(null);
      await reload();
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setSaving(false); }
  };

  if (loading) return <p className="portal-status">Loading…</p>;

  return (
    <>
      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">01</div>
          <div className="portal-card-title">Platform settings</div>
          <span className="portal-tag portal-tag-put">PUT</span>
        </div>
        <div className="portal-card-bd">
          <p style={{ margin: "0 0 12px", fontSize: 12, color: "var(--portal-muted)" }}>
            Configure platform-level settings stored as JSONB key/value pairs.
          </p>
          {err ? <p className="portal-error">{err}</p> : null}
          {settings.length === 0 ? <p style={{ fontSize: 12, color: "#888" }}>No settings found. Seed data should populate defaults on migration.</p> : null}
          {settings.map((s) => (
            <div key={s.key} style={{ marginBottom: 16, padding: 12, background: "#f5f5f5", borderRadius: 8 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                <div><strong style={{ fontSize: 13 }}>{s.key}</strong> <span style={{ fontSize: 11, color: "#888" }}>updated {new Date(s.updated_at).toLocaleDateString()}</span></div>
                {editKey === s.key ? (
                  <button type="button" className="portal-act" style={{ fontSize: 11 }} onClick={() => setEditKey(null)}>Cancel</button>
                ) : (
                  <button type="button" className="portal-act" style={{ fontSize: 11 }} onClick={() => { setEditKey(s.key); setEditValue(JSON.stringify(s.value, null, 2)); }}>Edit</button>
                )}
              </div>
              {editKey === s.key ? (
                <div>
                  <textarea className="portal-inp" rows={6} value={editValue} onChange={(e) => setEditValue(e.target.value)} style={{ fontSize: 11, fontFamily: "var(--font-mono)" }} />
                  <div className="portal-acts" style={{ marginTop: 8 }}>
                    <button type="button" className="portal-act" disabled={saving} onClick={() => void save(s.key)}>Save</button>
                  </div>
                </div>
              ) : (
                <pre style={{ fontSize: 11, fontFamily: "var(--font-mono)", margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{JSON.stringify(s.value, null, 2)}</pre>
              )}
            </div>
          ))}
        </div>
      </div>

      {status ? <p className="portal-status">{status}</p> : null}
    </>
  );
}
