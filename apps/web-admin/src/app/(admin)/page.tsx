"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { IconArrowRight } from "@tabler/icons-react";
import { useAdminAuth } from "@/components/admin/admin-auth-context";
import { getAdminSummary, type AdminSummaryResponse } from "@/lib/eventflow-api";

export default function AdminDashboardPage() {
  const { token } = useAdminAuth();
  const [summary, setSummary] = useState<AdminSummaryResponse | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const s = await getAdminSummary(token);
        if (!cancelled) setSummary(s);
      } catch (e: unknown) {
        if (!cancelled) setLoadErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
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
            Coarse counts across Postgres. User metric is a derived union of listing authors, draft authors, and business
            owners — not a full CRM profile.
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
                <p style={{ margin: 0, fontSize: 11, color: "#484848" }}>
                  Distinct ids from community_events, event_drafts, and business owners.
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
    </>
  );
}

function MetricCard({ label, value, href }: { label: string; value: number; href: string }) {
  return (
    <div className="portal-empty" style={{ textAlign: "left" as const }}>
      <div className="portal-lbl" style={{ marginBottom: 8 }}>
        {label}
      </div>
      <p style={{ fontSize: 22, fontWeight: 600, margin: "0 0 4px", color: "var(--portal-fg-soft)" }}>{value}</p>
      <Link href={href} className="portal-link-back" style={{ marginTop: 10 }}>
        Browse <IconArrowRight size={13} />
      </Link>
    </div>
  );
}
