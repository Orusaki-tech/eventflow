"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { IconArrowRight, IconTicket, IconAlertTriangle, IconHandStop, IconVideo, IconSettings } from "@tabler/icons-react";
import { useAdminAuth } from "@/components/admin/admin-auth-context";
import { getAdminSummaryV3 } from "@/lib/eventflow-api";

function minorToKes(amount: number) {
  return (amount / 100).toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function AdminDashboardPage() {
  const { token } = useAdminAuth();
  const [summary, setSummary] = useState<{
    businesses: number;
    community_events: number;
    poster_assets: number;
    event_drafts: number;
    distinct_active_user_ids: number;
  } | null>(null);
  const [v3, setV3] = useState<{
    total_orders: number;
    total_revenue_minor: number;
    pending_claims: number;
    pending_payouts: number;
    pending_videos: number;
  } | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const result = await getAdminSummaryV3(token);
        if (!cancelled) {
          setSummary(result);
          setV3({
            total_orders: result.total_orders ?? 0,
            total_revenue_minor: result.total_revenue_minor ?? 0,
            pending_claims: result.pending_claims ?? 0,
            pending_payouts: result.pending_payouts ?? 0,
            pending_videos: result.pending_videos ?? 0,
          });
        }
      } catch (e: unknown) {
        if (!cancelled) setLoadErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  return (
    <>
      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">01</div>
          <div className="portal-card-title">Directory summary</div>
          <span className="portal-tag portal-tag-info">Read-only</span>
        </div>
        <div className="portal-card-bd">
          <p style={{ margin: "0 0 14px", fontSize: 12, color: "var(--portal-muted)" }}>
            Coarse counts across Postgres.
          </p>
          {loadErr ? <p className="portal-error">{loadErr}</p> : null}
          {summary ? (
            <div className="portal-grid2">
              <MetricCard label="Businesses" value={summary.businesses} href="/businesses" />
              <MetricCard label="Community listings" value={summary.community_events} href="/listings" />
              <MetricCard label="Poster assets" value={summary.poster_assets} href="/posters" />
              <MetricCard label="Event drafts" value={summary.event_drafts} href="/" />
              <div className="portal-empty" style={{ gridColumn: "1 / -1", textAlign: "left" as const }}>
                <div className="portal-lbl" style={{ marginBottom: 8 }}>
                  Active user ids (derived)
                </div>
                <p style={{ fontSize: 22, fontWeight: 600, margin: "0 0 4px", color: "var(--portal-fg-soft)" }}>
                  {summary.distinct_active_user_ids}
                </p>
              </div>
            </div>
          ) : !loadErr ? (
            <div className="portal-loading" style={{ minHeight: 120 }}>
              Loading summary…
            </div>
          ) : null}
        </div>
      </div>

      {v3 ? (
        <div className="portal-card">
          <div className="portal-card-hd">
            <div className="portal-card-num">02</div>
            <div className="portal-card-title">Ticketing overview</div>
            <span className="portal-tag portal-tag-success">v3</span>
          </div>
          <div className="portal-card-bd">
            <div className="portal-grid4" style={{ marginBottom: 16 }}>
              <div className="portal-empty" style={{ textAlign: "left" }}>
                <div className="portal-lbl" style={{ marginBottom: 4, fontSize: 11 }}>Total Orders</div>
                <p style={{ fontSize: 20, fontWeight: 600, margin: 0, color: "var(--portal-fg-soft)" }}>{v3.total_orders}</p>
                <Link href="/orders" className="portal-link-back" style={{ marginTop: 6 }}>View <IconArrowRight size={11} /></Link>
              </div>
              <div className="portal-empty" style={{ textAlign: "left" }}>
                <div className="portal-lbl" style={{ marginBottom: 4, fontSize: 11 }}>Total Revenue</div>
                <p style={{ fontSize: 20, fontWeight: 600, margin: 0, color: "var(--portal-fg-soft)" }}>KES {minorToKes(v3.total_revenue_minor)}</p>
              </div>
              <div className="portal-empty" style={{ textAlign: "left" }}>
                <div className="portal-lbl" style={{ marginBottom: 4, fontSize: 11 }}>Pending Claims</div>
                <p style={{ fontSize: 20, fontWeight: 600, margin: 0, color: v3.pending_claims > 0 ? "#b91c1c" : "var(--portal-fg-soft)" }}>{v3.pending_claims}</p>
                <Link href="/claims" className="portal-link-back" style={{ marginTop: 6 }}>Review <IconArrowRight size={11} /></Link>
              </div>
              <div className="portal-empty" style={{ textAlign: "left" }}>
                <div className="portal-lbl" style={{ marginBottom: 4, fontSize: 11 }}>Pending Payouts</div>
                <p style={{ fontSize: 20, fontWeight: 600, margin: 0, color: v3.pending_payouts > 0 ? "#b91c1c" : "var(--portal-fg-soft)" }}>{v3.pending_payouts}</p>
                <Link href="/payouts" className="portal-link-back" style={{ marginTop: 6 }}>Process <IconArrowRight size={11} /></Link>
              </div>
            </div>
            <div className="portal-grid2">
              <div className="portal-empty" style={{ textAlign: "left" }}>
                <div className="portal-lbl" style={{ marginBottom: 4, fontSize: 11 }}>Pending Video Moderation</div>
                <p style={{ fontSize: 20, fontWeight: 600, margin: 0, color: v3.pending_videos > 0 ? "#b91c1c" : "var(--portal-fg-soft)" }}>{v3.pending_videos}</p>
                <Link href="/video-moderation" className="portal-link-back" style={{ marginTop: 6 }}>Moderate <IconArrowRight size={11} /></Link>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      <div className="portal-card">
        <div className="portal-card-hd">
          <div className="portal-card-num">03</div>
          <div className="portal-card-title">Quick links</div>
          <span className="portal-tag portal-tag-info">Actions</span>
        </div>
        <div className="portal-card-bd">
          <div className="portal-acts">
            <Link href="/orders" className="portal-act"><IconTicket size={12} /> Orders</Link>
            <Link href="/claims" className="portal-act"><IconAlertTriangle size={12} /> Claims</Link>
            <Link href="/payouts" className="portal-act"><IconHandStop size={12} /> Payouts</Link>
            <Link href="/video-moderation" className="portal-act"><IconVideo size={12} /> Video moderation</Link>
            <Link href="/platform-settings" className="portal-act"><IconSettings size={12} /> Platform settings</Link>
          </div>
        </div>
      </div>
    </>
  );
}

function MetricCard({ label, value, href }: { label: string; value: number; href: string }) {
  return (
    <div className="portal-empty" style={{ textAlign: "left" as const }}>
      <div className="portal-lbl" style={{ marginBottom: 8 }}>{label}</div>
      <p style={{ fontSize: 22, fontWeight: 600, margin: "0 0 4px", color: "var(--portal-fg-soft)" }}>{value}</p>
      <Link href={href} className="portal-link-back" style={{ marginTop: 10 }}>
        Browse <IconArrowRight size={13} />
      </Link>
    </div>
  );
}
