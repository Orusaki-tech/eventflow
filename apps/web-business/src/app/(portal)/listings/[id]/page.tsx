"use client";

import { IconPhoto, IconTrash, IconVideo, IconBrandWhatsapp, IconTicket, IconPlus, IconCheck, IconX } from "@tabler/icons-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { usePortalAuth } from "@/components/portal/portal-auth-context";
import {
  attachListingBusiness,
  deleteListingBusiness,
  deleteListingShareAlias,
  getMyCommunityEvent,
  listBusinesses,
  putListingShareAlias,
  registerEventVideo,
  listTicketTypes,
  bulkSetTicketTypes,
  getEventSales,
  type BusinessRow,
  type CommunityMineDetail,
  type TicketTypeRow,
} from "@/lib/eventflow-api";

function formatStart(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { dateStyle: "full", timeStyle: "short" });
  } catch {
    return iso;
  }
}

export default function ListingDetailPage() {
  const { token } = usePortalAuth();
  const params = useParams();
  const id = typeof params.id === "string" ? params.id : "";

  const [detail, setDetail] = useState<CommunityMineDetail | null>(null);
  const [myBiz, setMyBiz] = useState<BusinessRow[]>([]);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [attachBizId, setAttachBizId] = useState("");
  const [shareUrl, setShareUrl] = useState("");
  const [videoUri, setVideoUri] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ticketTypes, setTicketTypes] = useState<TicketTypeRow[]>([]);
  const [salesData, setSalesData] = useState<{ name: string; price_minor_units: number; sold: number; active: number; checked_in: number }[]>([]);
  const [ttEditor, setTtEditor] = useState<{ ticket_type_id?: string; name: string; price_minor_units: string; quantity_available: string; description: string }[]>([]);

  const reload = useCallback(async () => {
    if (!id) return;
    const [d, biz, tt, sales] = await Promise.all([
      getMyCommunityEvent(token, id),
      listBusinesses(token),
      listTicketTypes(token, id).catch(() => [] as TicketTypeRow[]),
      getEventSales(token, id).catch(() => []),
    ]);
    setDetail(d);
    setMyBiz(biz);
    setAttachBizId(d.business_id ?? "");
    setTicketTypes(tt);
    setSalesData(sales);
    if (tt.length > 0) {
      setTtEditor(tt.map(t => ({
        ticket_type_id: t.ticket_type_id,
        name: t.name,
        price_minor_units: String(t.price_minor_units),
        quantity_available: t.quantity_available != null ? String(t.quantity_available) : "",
        description: t.description ?? "",
      })));
    } else {
      setTtEditor([{ name: "", price_minor_units: "", quantity_available: "", description: "" }]);
    }
  }, [token, id]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      if (!id) return;
      try {
        await reload();
        if (cancelled) return;
      } catch (e: unknown) {
        if (!cancelled) setLoadErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, reload]);

  const run = async (fn: () => Promise<void>) => {
    setErr(null);
    setStatus(null);
    try {
      await fn();
      setStatus("Done.");
      await reload();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  if (!id) {
    return <p className="portal-error">Invalid listing id.</p>;
  }

  if (loadErr) {
    return <p className="portal-error">{loadErr}</p>;
  }

  if (!detail) {
    return <p className="portal-status">Loading…</p>;
  }

  return (
    <>
      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">01</div>
          <div className="portal-card-title">{detail.title}</div>
          <span className="portal-tag portal-tag-info">Listing</span>
        </div>
        <div className="portal-card-bd">
          <p style={{ margin: "0 0 6px", fontSize: 12, color: "var(--portal-muted)" }}>{formatStart(detail.start_time)}</p>
          <p style={{ margin: "0 0 6px", fontSize: 12 }}>{detail.venue}</p>
          <p
            style={{
              margin: 0,
              fontSize: 10,
              fontFamily: "var(--font-mono)",
              color: "var(--portal-muted-2)",
              wordBreak: "break-all",
            }}
          >
            {detail.community_event_id}
          </p>
          {detail.business_id ? (
            <p style={{ margin: "10px 0 0", fontSize: 11, color: "var(--portal-muted)" }}>
              Attached business:{" "}
              <span style={{ fontFamily: "var(--font-mono)" }}>
                {myBiz.find((b) => b.business_id === detail.business_id)?.name ?? detail.business_id}
              </span>
            </p>
          ) : null}
          {detail.poster_image_uri ? (
            <div style={{ marginTop: 12 }}>
              <img
                src={detail.poster_image_uri}
                alt="Poster"
                style={{
                  maxWidth: "100%",
                  maxHeight: 200,
                  borderRadius: 6,
                  objectFit: "contain",
                  background: "#000",
                }}
              />
            </div>
          ) : null}
          {detail.hero_video_uri ? (
            <div style={{ marginTop: 12 }}>
              <video
                src={detail.hero_video_uri}
                controls
                style={{
                  maxWidth: "100%",
                  maxHeight: 200,
                  borderRadius: 6,
                  background: "#000",
                }}
              />
            </div>
          ) : null}
        </div>
      </div>

      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">02</div>
          <div className="portal-card-title">Attach business</div>
          <span className="portal-tag portal-tag-put">PUT</span>
        </div>
        <div className="portal-card-bd">
          <div className="portal-field">
            <div className="portal-lbl">Business</div>
            <select
              className="portal-inp"
              value={attachBizId}
              onChange={(e) => setAttachBizId(e.target.value)}
            >
              <option value="">— None —</option>
              {myBiz.map((b) => (
                <option key={b.business_id} value={b.business_id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>
          <div className="portal-acts" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              type="button"
              className="portal-act"
              onClick={() =>
                void run(async () => {
                  if (!attachBizId.trim()) throw new Error("Select a business");
                  await attachListingBusiness(token, id, attachBizId.trim());
                })
              }
            >
              <span className="portal-tag portal-tag-put" style={{ marginRight: 4 }}>
                PUT
              </span>
              /listings/…/business
            </button>
            {detail.business_id ? (
              <button
                type="button"
                className="portal-act"
                onClick={() =>
                  void run(async () => {
                    await deleteListingBusiness(token, id);
                  })
                }
              >
                <IconTrash size={14} style={{ marginRight: 4 }} />
                Detach
              </button>
            ) : null}
          </div>
        </div>
      </div>

      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">03</div>
          <div className="portal-card-title">Canonical share URLs</div>
          <span className="portal-tag portal-tag-put">PUT</span>
        </div>
        <div className="portal-card-bd">
          <p style={{ margin: "0 0 12px", fontSize: 11, color: "var(--portal-muted)" }}>
            Register each URL people might paste (Instagram, Facebook, …). Matched imports skip AI parsing on mobile.
          </p>
          {detail.normalized_share_aliases.length ? (
            <ul style={{ margin: "0 0 14px", paddingLeft: 0, fontSize: 11, fontFamily: "var(--font-mono)", color: "#888", listStyle: "none" }}>
              {detail.normalized_share_aliases.map((u) => (
                <li key={u} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                  <span
                    title={u}
                    style={{
                      flex: 1,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      maxWidth: 480,
                    }}
                  >
                    {u}
                  </span>
                  <button
                    type="button"
                    className="portal-icon-btn"
                    title="Remove alias"
                    aria-label="Remove alias"
                    onClick={() =>
                      void run(async () => {
                        await deleteListingShareAlias(token, id, u);
                      })
                    }
                  >
                    <IconTrash size={11} stroke={1.5} />
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <div className="portal-empty" style={{ marginBottom: 14 }}>
              <p>No share aliases yet.</p>
            </div>
          )}
          <div className="portal-field">
            <div className="portal-lbl">
              Official share URL <span className="portal-lbl-hint">— add another</span>
            </div>
            <input
              className="portal-inp"
              type="url"
              placeholder="https://instagram.com/…"
              value={shareUrl}
              onChange={(e) => setShareUrl(e.target.value)}
            />
          </div>
          <div className="portal-acts">
            <button
              type="button"
              className="portal-act"
              onClick={() =>
                void run(async () => {
                  if (shareUrl.trim().length < 8) throw new Error("URL required");
                  await putListingShareAlias(token, id, shareUrl.trim());
                  setShareUrl("");
                })
              }
            >
              <span className="portal-tag portal-tag-put" style={{ marginRight: 4 }}>
                PUT
              </span>
              /listings/…/share-alias
            </button>
          </div>
        </div>
      </div>

      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">04</div>
          <div className="portal-card-title">Promo video</div>
          <span className="portal-tag portal-tag-info">Moderation</span>
        </div>
        <div className="portal-card-bd">
          <div className="portal-field">
            <div className="portal-lbl">
              Storage URI <span className="portal-lbl-hint">— https object URL after upload</span>
            </div>
            <input
              className="portal-inp"
              type="url"
              placeholder="https://cdn.example.com/v.mp4"
              value={videoUri}
              onChange={(e) => setVideoUri(e.target.value)}
            />
            {videoUri.trim() ? (
              <div style={{ marginTop: 8 }}>
                <video
                  src={videoUri.trim()}
                  controls
                  style={{
                    maxWidth: "100%",
                    maxHeight: 160,
                    borderRadius: 6,
                    background: "#000",
                  }}
                />
              </div>
            ) : null}
          </div>
          <div className="portal-acts">
            <button
              type="button"
              className="portal-act"
              onClick={() =>
                void run(async () => {
                  if (videoUri.trim().length < 8) throw new Error("Storage URI required");
                  await registerEventVideo(token, id, videoUri.trim());
                })
              }
            >
              <IconVideo size={12} stroke={2} />
              <span className="portal-tag portal-tag-post" style={{ marginRight: 4 }}>
                POST
              </span>
              /event-videos
            </button>
          </div>
        </div>
      </div>

      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">05</div>
          <div className="portal-card-title">Ticket types</div>
          <span className="portal-tag portal-tag-success">{ticketTypes.length} types</span>
        </div>
        <div className="portal-card-bd">
          {salesData.length > 0 ? (
            <div style={{ marginBottom: 16, overflowX: "auto" }}>
              <table className="portal-table" style={{ fontSize: 12 }}>
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Price</th>
                    <th>Sold</th>
                    <th>Active</th>
                    <th>Checked in</th>
                  </tr>
                </thead>
                <tbody>
                  {salesData.map((s, i) => (
                    <tr key={i}>
                      <td>{s.name}</td>
                      <td>KES {(s.price_minor_units / 100).toFixed(2)}</td>
                      <td>{s.sold}</td>
                      <td>{s.active}</td>
                      <td>{s.checked_in}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          {ticketTypes.length > 0 ? (
            <p style={{ fontSize: 11, color: "#888", marginBottom: 12 }}>
              Saved ticket types — modify below and save.
            </p>
          ) : null}

          {ttEditor.map((row, i) => (
            <div key={i} style={{ display: "flex", gap: 8, marginBottom: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
              <div style={{ flex: "1 1 150px", minWidth: 120 }}>
                <div className="portal-lbl" style={{ fontSize: 10 }}>Name</div>
                <input className="portal-inp" type="text" placeholder="e.g. General" value={row.name}
                  onChange={(e) => setTtEditor(ttEditor.map((r, j) => j === i ? { ...r, name: e.target.value } : r))} />
              </div>
              <div style={{ flex: "0 1 100px", minWidth: 80 }}>
                <div className="portal-lbl" style={{ fontSize: 10 }}>Price (cents)</div>
                <input className="portal-inp" type="number" placeholder="150000" value={row.price_minor_units}
                  onChange={(e) => setTtEditor(ttEditor.map((r, j) => j === i ? { ...r, price_minor_units: e.target.value } : r))} />
              </div>
              <div style={{ flex: "0 1 80px", minWidth: 60 }}>
                <div className="portal-lbl" style={{ fontSize: 10 }}>Qty (blank=∞)</div>
                <input className="portal-inp" type="number" placeholder="∞" value={row.quantity_available}
                  onChange={(e) => setTtEditor(ttEditor.map((r, j) => j === i ? { ...r, quantity_available: e.target.value } : r))} />
              </div>
              <div style={{ flex: "1 1 150px", minWidth: 120 }}>
                <div className="portal-lbl" style={{ fontSize: 10 }}>Description</div>
                <input className="portal-inp" type="text" placeholder="Optional" value={row.description}
                  onChange={(e) => setTtEditor(ttEditor.map((r, j) => j === i ? { ...r, description: e.target.value } : r))} />
              </div>
              {ttEditor.length > 1 ? (
                <button type="button" className="portal-icon-btn" title="Remove" aria-label="Remove"
                  onClick={() => setTtEditor(ttEditor.filter((_, j) => j !== i))}>
                  <IconX size={12} />
                </button>
              ) : null}
            </div>
          ))}
          <div className="portal-acts" style={{ marginTop: 8 }}>
            <button type="button" className="portal-act"
              onClick={() => setTtEditor([...ttEditor, { name: "", price_minor_units: "", quantity_available: "", description: "" }])}>
              <IconPlus size={12} /> Add type
            </button>
            <button type="button" className="portal-act"
              onClick={() => {
                const types = ttEditor.filter(t => t.name.trim() && t.price_minor_units.trim());
                for (const t of types) {
                  const price = parseFloat(t.price_minor_units);
                  if (isNaN(price) || price < 0) {
                    setErr(`Invalid price "${t.price_minor_units}" for "${t.name}"`);
                    return;
                  }
                  if (t.quantity_available.trim()) {
                    const qty = parseInt(t.quantity_available, 10);
                    if (isNaN(qty) || qty < 0) {
                      setErr(`Invalid quantity "${t.quantity_available}" for "${t.name}"`);
                      return;
                    }
                  }
                }
                void run(async () => {
                  await bulkSetTicketTypes(token, id, types.map(t => ({
                    ticket_type_id: t.ticket_type_id || null,
                    name: t.name.trim(),
                    price_minor_units: parseFloat(t.price_minor_units),
                    quantity_available: t.quantity_available.trim() ? parseInt(t.quantity_available, 10) : null,
                    description: t.description.trim() || null,
                  })));
                });
              }}>
              <IconCheck size={12} /> Save ticket types
            </button>
          </div>
        </div>
      </div>

      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">06</div>
          <div className="portal-card-title">WhatsApp</div>
          <span className="portal-tag portal-tag-info">Contact</span>
        </div>
        <div className="portal-card-bd">
          {detail.whatsapp_e164 ? (
            <div className="portal-info-box">
              <IconBrandWhatsapp size={16} stroke={1.5} color="#25D366" />
              <div>
                <div className="portal-info-box-t">WhatsApp number</div>
                <div className="portal-info-box-s">{detail.whatsapp_e164}</div>
              </div>
            </div>
          ) : (
            <div className="portal-empty">
              <p>No WhatsApp number set. Attach a business with a WhatsApp number to enable WhatsApp sharing for this listing.</p>
            </div>
          )}
          <p style={{ margin: "10px 0 0", fontSize: 10, color: "var(--portal-muted-2)" }}>
            Update the WhatsApp number from the{" "}
            <Link href="/businesses" style={{ color: "inherit", textDecoration: "underline" }}>Businesses</Link> page.
          </p>
        </div>
      </div>

      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">07</div>
          <div className="portal-card-title">Carousel</div>
          <span className="portal-tag portal-tag-get">GET</span>
        </div>
        <div className="portal-card-bd">
          <div className="portal-info-box">
            <IconPhoto size={16} stroke={1.5} color="#2e2e2e" />
            <div>
              <div className="portal-info-box-t">Listing carousel</div>
              <div className="portal-info-box-s">Poster + approved promo videos displayed in the discovery feed.</div>
            </div>
          </div>
          <div className="portal-acts">
            <Link href={`/listings/${id}/carousel`} className="portal-act" style={{ textDecoration: "none" }}>
              <IconPhoto size={12} stroke={2} /> View carousel
            </Link>
          </div>
        </div>
      </div>

      {status ? <p className="portal-status">{status}</p> : null}
      {err ? <p className="portal-error">{err}</p> : null}

      <Link href="/listings" className="portal-link-back">
        ← All listings
      </Link>
      <Link href="/dashboard" className="portal-link-back" style={{ marginLeft: 12 }}>
        Dashboard
      </Link>
    </>
  );
}
