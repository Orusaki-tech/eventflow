"use client";

import { IconArrowRight, IconCalendar, IconCreditCard, IconPlus, IconTicket, IconVideo, IconBox, IconUsers, IconCoins, IconHandStop } from "@tabler/icons-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { usePortalAuth } from "@/components/portal/portal-auth-context";
import { getBusinessDashboard, listMineCommunityEvents, type DashboardResponse, type CommunityMineRow } from "@/lib/eventflow-api";

function minorToKes(amount: number) {
  return (amount / 100).toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function DashboardOverviewPage() {
  const { token } = usePortalAuth();
  const [dash, setDash] = useState<DashboardResponse | null>(null);
  const [listings, setListings] = useState<CommunityMineRow[]>([]);
  const [loadErr, setLoadErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const [d, mine] = await Promise.all([
          getBusinessDashboard(token),
          listMineCommunityEvents(token, 100),
        ]);
        if (!cancelled) { setDash(d); setListings(mine); }
      } catch (e: unknown) {
        if (!cancelled) setLoadErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  if (loadErr) return <p className="portal-error">{loadErr}</p>;
  if (!dash) return <p style={{ color: "#888", padding: 24 }}>Loading…</p>;

  return (
    <>
      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">01</div>
          <div className="portal-card-title">Revenue</div>
          <span className="portal-tag portal-tag-success">KES {minorToKes(dash.total_revenue_minor)}</span>
        </div>
        <div className="portal-card-bd">
          <div className="portal-grid4" style={{ marginBottom: 16 }}>
            <div className="portal-empty" style={{ textAlign: "left" }}>
              <div className="portal-lbl" style={{ marginBottom: 4, fontSize: 11 }}>Gross Revenue</div>
              <p style={{ fontSize: 20, fontWeight: 600, margin: 0, color: "var(--portal-fg-soft)" }}>KES {minorToKes(dash.total_revenue_minor)}</p>
            </div>
            <div className="portal-empty" style={{ textAlign: "left" }}>
              <div className="portal-lbl" style={{ marginBottom: 4, fontSize: 11 }}>Platform Fees</div>
              <p style={{ fontSize: 20, fontWeight: 600, margin: 0, color: "#b91c1c" }}>KES {minorToKes(dash.total_fees_minor)}</p>
            </div>
            <div className="portal-empty" style={{ textAlign: "left" }}>
              <div className="portal-lbl" style={{ marginBottom: 4, fontSize: 11 }}>Net Available</div>
              <p style={{ fontSize: 20, fontWeight: 600, margin: 0, color: "var(--portal-fg-soft)" }}>KES {minorToKes(dash.net_available_minor)}</p>
            </div>
            <div className="portal-empty" style={{ textAlign: "left" }}>
              <div className="portal-lbl" style={{ marginBottom: 4, fontSize: 11 }}>Tickets Sold</div>
              <p style={{ fontSize: 20, fontWeight: 600, margin: 0, color: "var(--portal-fg-soft)" }}>{dash.total_tickets_sold}</p>
            </div>
          </div>

          <div className="portal-grid4" style={{ marginBottom: 16 }}>
            <div className="portal-empty" style={{ textAlign: "left" }}>
              <div className="portal-lbl" style={{ marginBottom: 4, fontSize: 11 }}>WhatsApp Tap Balance</div>
              <p style={{ fontSize: 20, fontWeight: 600, margin: 0, color: "var(--portal-fg-soft)" }}>{dash.tap_balance}</p>
              <p style={{ margin: "4px 0 0", fontSize: 10, color: "#888" }}>Plan: {dash.tap_plan}</p>
            </div>
            <div className="portal-empty" style={{ textAlign: "left" }}>
              <div className="portal-lbl" style={{ marginBottom: 4, fontSize: 11 }}>Affiliate Earnings</div>
              <p style={{ fontSize: 20, fontWeight: 600, margin: 0, color: "var(--portal-fg-soft)" }}>KES {minorToKes(dash.affiliate_earnings_minor)}</p>
            </div>
          </div>

          <div className="portal-divider" />

          <div className="portal-lbl" style={{ marginBottom: 10 }}>
            Quick actions
          </div>
          <div className="portal-acts">
            <Link href="/listings/new" className="portal-act">
              <IconPlus size={12} stroke={2} /> New listing
            </Link>
            <Link href="/listings" className="portal-act">
              <IconCalendar size={12} stroke={2} /> All listings
            </Link>
            <Link href="/tap-packs" className="portal-act">
              <IconCoins size={12} stroke={2} /> Tap packs
            </Link>
            <Link href="/feed" className="portal-act">
              <IconVideo size={12} stroke={2} /> Feed videos
            </Link>
            <Link href="/products" className="portal-act">
              <IconBox size={12} stroke={2} /> Products
            </Link>
            <Link href="/affiliate-requests" className="portal-act">
              <IconUsers size={12} stroke={2} /> Affiliates
            </Link>
            <Link href="/payouts" className="portal-act">
              <IconHandStop size={12} stroke={2} /> Payouts
            </Link>
          </div>
        </div>
      </div>

      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">02</div>
          <div className="portal-card-title">Per-event breakdown</div>
          <span className="portal-tag portal-tag-info">All listings</span>
        </div>
        <div className="portal-card-bd">
          {dash.listings.length === 0 ? (
            <p style={{ fontSize: 12, color: "#888", margin: 0 }}>No ticket sales yet. Set up ticket types on your listings to start selling.</p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table className="portal-table">
                <thead>
                  <tr>
                    <th>Event</th>
                    <th>Date</th>
                    <th>Sold</th>
                    <th>Revenue</th>
                    <th>Fees</th>
                    <th>Checked in</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {dash.listings.map((l) => (
                    <tr key={l.community_event_id}>
                      <td style={{ fontWeight: 500 }}>{l.title}</td>
                      <td style={{ fontSize: 12, color: "#888" }}>{new Date(l.start_time).toLocaleDateString()}</td>
                      <td>{l.tickets_sold}</td>
                      <td>KES {minorToKes(l.revenue_minor)}</td>
                      <td style={{ color: "#b91c1c" }}>KES {minorToKes(l.fees_minor)}</td>
                      <td>{l.checked_in}</td>
                      <td>
                        <Link href={`/listings/${l.community_event_id}`} className="portal-link-back" style={{ fontSize: 11 }}>
                          Details <IconArrowRight size={11} />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">03</div>
          <div className="portal-card-title">Listings</div>
          <span className="portal-tag portal-tag-info">{listings.length} total</span>
        </div>
        <div className="portal-card-bd">
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {listings.map((l) => (
              <Link
                key={l.community_event_id}
                href={`/listings/${l.community_event_id}`}
                style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 12px", background: "#f5f5f5", borderRadius: 8, textDecoration: "none", color: "inherit" }}
              >
                <IconCalendar size={18} stroke={1.5} style={{ color: "#888", flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 500, fontSize: 13 }}>{l.title}</div>
                  <div style={{ fontSize: 11, color: "#888" }}>{new Date(l.start_time).toLocaleDateString()} • {l.venue}</div>
                </div>
                <IconArrowRight size={14} style={{ color: "#aaa", flexShrink: 0 }} />
              </Link>
            ))}
          </div>
        </div>
      </div>

      <Link href="/" className="portal-link-back">← Home</Link>
    </>
  );
}
