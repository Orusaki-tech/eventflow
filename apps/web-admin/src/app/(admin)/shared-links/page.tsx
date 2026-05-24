"use client";

import { IconCheck, IconCircleCheck, IconCircleX, IconClock, IconX } from "@tabler/icons-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useAdminAuth } from "@/components/admin/admin-auth-context";
import {
  listAdminSharedLinkListings,
  putAdminSharedLinkListing,
  type AdminSharedLinkListingRow,
} from "@/lib/eventflow-api";

const LIMIT = 25;

function utcToInput(iso: string | null | undefined): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    const pad = (n: number) => n.toString().padStart(2, "0");
    return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
  } catch { return ""; }
}

function inputToUtc(value: string): string {
  if (!value) return "";
  try {
    const d = new Date(value + "Z");
    return isNaN(d.getTime()) ? "" : d.toISOString();
  } catch { return ""; }
}

function statusIcon(s: string) {
  switch (s) {
    case "approved": return <IconCircleCheck size={14} stroke={1.5} style={{ color: "#2b7a2b" }} />;
    case "rejected": return <IconCircleX size={14} stroke={1.5} style={{ color: "#b33" }} />;
    default: return <IconClock size={14} stroke={1.5} style={{ color: "#b08500" }} />;
  }
}

export default function AdminSharedLinksPage() {
  const { token } = useAdminAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const page = Math.max(1, parseInt(searchParams.get("page") ?? "1", 10) || 1);
  const q = searchParams.get("q") ?? "";
  const rawStatus = searchParams.get("status");
  const statusFilter = rawStatus && ["pending", "approved", "rejected"].includes(rawStatus) ? rawStatus : "pending";
  const offset = (page - 1) * LIMIT;

  const [rows, setRows] = useState<AdminSharedLinkListingRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [searchDraft, setSearchDraft] = useState(q);
  const [editingUrl, setEditingUrl] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editVenue, setEditVenue] = useState("");
  const [editStart, setEditStart] = useState("");
  const [editPrice, setEditPrice] = useState("");

  useEffect(() => {
    setSearchDraft(q);
  }, [q]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await listAdminSharedLinkListings(token, {
          limit: LIMIT,
          offset,
          q: q || undefined,
          status: statusFilter || undefined,
        });
        if (!cancelled) {
          setRows(res.items);
          setTotal(res.total);
        }
      } catch (e: unknown) {
        if (!cancelled) setLoadErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, offset, q, statusFilter]);

  const pushQuery = useCallback(
    (next: { page?: number; q?: string; status?: string }) => {
      const p = new URLSearchParams();
      const pg = next.page ?? page;
      const qq = next.q !== undefined ? next.q : q;
      const st = next.status !== undefined ? next.status : statusFilter;
      if (pg > 1) p.set("page", String(pg));
      if (qq.trim()) p.set("q", qq.trim());
      if (st && st !== "pending") p.set("status", st);
      const qs = p.toString();
      router.push(qs ? `/shared-links?${qs}` : "/shared-links");
    },
    [page, q, statusFilter, router]
  );

  const openEditor = (r: AdminSharedLinkListingRow) => {
    setEditingUrl(r.normalized_url);
    setEditTitle((r.cached_payload?.title as string) ?? "");
    setEditVenue((r.cached_payload?.venue as string) ?? "");
    setEditStart(utcToInput(r.cached_payload?.start_time as string));
    setEditPrice((r.cached_payload?.price as string) ?? "");
  };

  const closeEditor = () => {
    setEditingUrl(null);
  };

  const saveEdit = async (url: string, newStatus?: string) => {
    setBusyId(url);
    try {
      await putAdminSharedLinkListing(token, {
        url,
        title: editTitle,
        venue: editVenue,
        start_time: editStart,
        price: editPrice,
        status: newStatus ?? null,
      });
      const res = await listAdminSharedLinkListings(token, {
        limit: LIMIT,
        offset,
        q: q || undefined,
        status: statusFilter || undefined,
      });
      setRows(res.items);
      setTotal(res.total);
      setEditingUrl(null);
    } catch (e: unknown) {
      setLoadErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / LIMIT));

  return (
    <div className="portal-card">
      <div className="portal-card-hd">
        <div className="portal-card-num">05</div>
        <div className="portal-card-title">Shared links</div>
      </div>
      <div className="portal-card-bd">
        <p style={{ margin: "0 0 14px", fontSize: 12, color: "var(--portal-muted)" }}>
          Model-parsed URL data awaiting review. Approved links skip AI parsing and serve the
          admin-edited details directly.
        </p>

        <form
          style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}
          onSubmit={(e) => {
            e.preventDefault();
            pushQuery({ page: 1, q: searchDraft });
          }}
        >
          <input
            type="search"
            placeholder="Search URL…"
            value={searchDraft}
            onChange={(e) => setSearchDraft(e.target.value)}
            style={{ flex: "1 1 240px", maxWidth: 400 }}
          />
          <button type="submit">Search</button>
          {q ? (
            <button type="button" className="portal-act" onClick={() => pushQuery({ page: 1, q: "" })}>
              Clear
            </button>
          ) : null}
          <div style={{ display: "flex", gap: 4, marginLeft: "auto" }}>
            {(["pending", "approved", "rejected"] as const).map((s) => (
              <button
                key={s}
                type="button"
                className={`portal-tag ${statusFilter === s ? "portal-tag-info" : ""}`}
                style={{
                  cursor: "pointer",
                  opacity: statusFilter === s ? 1 : 0.5,
                  textTransform: "capitalize",
                }}
                onClick={() => pushQuery({ page: 1, status: s })}
              >
                {statusIcon(s)} {s}
              </button>
            ))}
          </div>
        </form>

        {loadErr ? <p className="portal-error">{loadErr}</p> : null}

        <div style={{ overflowX: "auto" }}>
          <table className="portal-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Raw URL</th>
                <th>Normalized URL</th>
                <th>Title</th>
                <th>Venue</th>
                <th>Start (UTC)</th>
                <th>Price</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.normalized_url}>
                  <td style={{ whiteSpace: "nowrap" }}>{statusIcon(r.status)}</td>
                  <td
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 10,
                      maxWidth: 260,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    title={r.source_url_raw ?? ""}
                  >
                    {r.source_url_raw ?? "—"}
                  </td>
                  <td
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 10,
                      maxWidth: 200,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    title={r.normalized_url}
                  >
                    {r.normalized_url}
                  </td>
                  {editingUrl === r.normalized_url ? (
                    <>
                      <td>
                        <input
                          className="portal-inp"
                          style={{ fontSize: 11, width: 140 }}
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                        />
                      </td>
                      <td>
                        <input
                          className="portal-inp"
                          style={{ fontSize: 11, width: 120 }}
                          value={editVenue}
                          onChange={(e) => setEditVenue(e.target.value)}
                        />
                      </td>
                      <td>
                        <input
                          className="portal-inp"
                          type="datetime-local"
                          style={{ fontSize: 11, width: 170 }}
                          value={editStart}
                          onChange={(e) => setEditStart(inputToUtc(e.target.value))}
                        />
                      </td>
                      <td>
                        <input
                          className="portal-inp"
                          style={{ fontSize: 11, width: 80 }}
                          value={editPrice}
                          onChange={(e) => setEditPrice(e.target.value)}
                        />
                      </td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        <div style={{ display: "flex", gap: 4 }}>
                          <button
                            type="button"
                            className="portal-act"
                            disabled={busyId === r.normalized_url}
                            onClick={() => { if (confirm("Approve this link? It will be used for future URL matching.")) void saveEdit(r.normalized_url, "approved"); }}
                            title="Approve"
                          >
                            <IconCheck size={13} />
                          </button>
                          <button
                            type="button"
                            className="portal-act"
                            disabled={busyId === r.normalized_url}
                            onClick={() => { if (confirm("Reject this link? Users sharing this URL will be asked to enter details manually.")) void saveEdit(r.normalized_url, "rejected"); }}
                            title="Reject"
                          >
                            <IconX size={13} style={{ color: "#b33" }} />
                          </button>
                          <button
                            type="button"
                            className="portal-act"
                            disabled={busyId === r.normalized_url}
                            onClick={closeEditor}
                            title="Cancel"
                          >
                            Cancel
                          </button>
                        </div>
                      </td>
                    </>
                  ) : (
                    <>
                      <td
                        style={{ fontSize: 11, cursor: "pointer", maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                        onClick={() => openEditor(r)}
                        title={r.cached_payload?.title as string ?? ""}
                      >
                        {(r.cached_payload?.title as string) ?? "—"}
                      </td>
                      <td
                        style={{ fontSize: 11, cursor: "pointer" }}
                        onClick={() => openEditor(r)}
                      >
                        {(r.cached_payload?.venue as string) ?? "—"}
                      </td>
                      <td
                        style={{ fontSize: 11, cursor: "pointer", whiteSpace: "nowrap" }}
                        onClick={() => openEditor(r)}
                      >
                        {r.cached_payload?.start_time
                          ? utcToInput(r.cached_payload.start_time as string)
                          : "—"}
                      </td>
                      <td
                        style={{ fontSize: 11, cursor: "pointer" }}
                        onClick={() => openEditor(r)}
                      >
                        {(r.cached_payload?.price as string) ?? "—"}
                      </td>
                      <td style={{ whiteSpace: "nowrap", fontSize: 11 }}>{new Date(r.updated_at).toISOString().slice(0, 16)}</td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p style={{ marginTop: 12, fontSize: 12, color: "var(--portal-muted)" }}>
          {total} total · page {page} / {totalPages}
        </p>
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <button type="button" disabled={page <= 1} onClick={() => pushQuery({ page: page - 1 })}>
            Previous
          </button>
          <button type="button" disabled={page >= totalPages} onClick={() => pushQuery({ page: page + 1 })}>
            Next
          </button>
          <Link href="/" className="portal-link-back" style={{ marginLeft: "auto" }}>
            Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
