"use client";

import { IconArrowRight, IconCalendar, IconCreditCard, IconPlus } from "@tabler/icons-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { usePortalAuth } from "@/components/portal/portal-auth-context";
import { listBusinesses, listMineCommunityEvents, type BusinessRow, type CommunityMineRow } from "@/lib/eventflow-api";

export default function DashboardOverviewPage() {
  const { token } = usePortalAuth();
  const [businesses, setBusinesses] = useState<BusinessRow[]>([]);
  const [listings, setListings] = useState<CommunityMineRow[]>([]);
  const [loadErr, setLoadErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const [biz, mine] = await Promise.all([listBusinesses(token), listMineCommunityEvents(token, 100)]);
        if (!cancelled) {
          setBusinesses(biz);
          setListings(mine);
        }
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
          <div className="portal-card-title">Overview</div>
          <span className="portal-tag portal-tag-info">Summary</span>
        </div>
        <div className="portal-card-bd">
          <p style={{ margin: "0 0 14px", fontSize: 12, color: "var(--portal-muted)" }}>
            Manage discovery listings, organizer businesses, and billing from the sidebar. Use the same Supabase account as
            EventFlow mobile.
          </p>
          {loadErr ? <p className="portal-error">{loadErr}</p> : null}
          <div className="portal-grid2">
            <div className="portal-empty" style={{ textAlign: "left" as const }}>
              <div className="portal-lbl" style={{ marginBottom: 8 }}>
                Businesses
              </div>
              <p style={{ fontSize: 22, fontWeight: 600, margin: "0 0 4px", color: "var(--portal-fg-soft)" }}>
                {businesses.length}
              </p>
              <p style={{ margin: 0, fontSize: 11, color: "#333" }}>
                <span style={{ color: "#484848" }}>Create additional profiles from mobile if needed.</span>
              </p>
              <Link href="/businesses" className="portal-link-back" style={{ marginTop: 10 }}>
                Manage <IconArrowRight size={13} />
              </Link>
            </div>
            <div className="portal-empty" style={{ textAlign: "left" as const }}>
              <div className="portal-lbl" style={{ marginBottom: 8 }}>
                Your listings
              </div>
              <p style={{ fontSize: 22, fontWeight: 600, margin: "0 0 4px", color: "var(--portal-fg-soft)" }}>
                {listings.length}
              </p>
              <p style={{ margin: 0, fontSize: 11, color: "#333" }}>
                <span style={{ color: "#484848" }}>Community events you published from this portal.</span>
              </p>
              <Link href="/listings" className="portal-link-back" style={{ marginTop: 10 }}>
                View all <IconArrowRight size={13} />
              </Link>
            </div>
          </div>

          <div className="portal-divider" />

          <div className="portal-lbl" style={{ marginBottom: 10 }}>
            Quick actions
          </div>
          <div className="portal-acts">
            <Link href="/listings/new" className="portal-act" style={{ textDecoration: "none" }}>
              <IconPlus size={12} stroke={2} />
              New listing
            </Link>
            <Link href="/listings" className="portal-act" style={{ textDecoration: "none" }}>
              <IconCalendar size={12} stroke={2} />
              All listings
            </Link>
            <Link href="/billing" className="portal-act" style={{ textDecoration: "none" }}>
              <IconCreditCard size={12} stroke={2} />
              Billing
            </Link>
          </div>
        </div>
      </div>

      <Link href="/" className="portal-link-back">
        ← Home
      </Link>
    </>
  );
}
