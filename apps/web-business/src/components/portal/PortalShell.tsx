"use client";

import {
  IconBell,
  IconBuildingStore,
  IconCalendar,
  IconCalendarEvent,
  IconCreditCard,
  IconDotsVertical,
  IconLayoutDashboard,
  IconLogout,
  IconSettings,
} from "@tabler/icons-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { createSupabaseBrowserClient } from "@/lib/supabase-browser";
import { PortalAuthProvider } from "./portal-auth-context";

function formatBreadcrumb(pathname: string): { muted: string; rest: string } {
  if (pathname === "/dashboard") return { muted: "Dashboard", rest: "Overview" };
  if (pathname === "/listings") return { muted: "Listings", rest: "All listings" };
  if (pathname === "/listings/new") return { muted: "Listings", rest: "New listing" };
  if (pathname.startsWith("/listings/")) return { muted: "Listings", rest: "Listing detail" };
  if (pathname === "/businesses") return { muted: "Businesses", rest: "Your businesses" };
  if (pathname === "/billing") return { muted: "Billing", rest: "Checkout" };
  if (pathname === "/settings") return { muted: "Settings", rest: "Environment & account" };
  return { muted: "EventFlow", rest: "Studio" };
}

function apiPillText(): string {
  if (process.env.NEXT_PUBLIC_EVENTFLOW_API_PROXY === "1") {
    return "proxy → upstream";
  }
  const raw = process.env.NEXT_PUBLIC_EVENTFLOW_API_URL ?? "http://localhost:8000";
  try {
    const u = new URL(raw);
    return `${u.hostname}${u.port ? `:${u.port}` : ""}`;
  } catch {
    return raw.replace(/^https?:\/\//, "").slice(0, 48);
  }
}

export function PortalShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [emailHint, setEmailHint] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const supabase = createSupabaseBrowserClient();
        const { data } = await supabase.auth.getSession();
        const t = data.session?.access_token ?? null;
        const em = data.session?.user?.email ?? null;
        if (!cancelled) {
          setToken(t);
          setEmailHint(em);
          setLoading(false);
          if (!t) router.replace("/login");
        }
      } catch {
        if (!cancelled) {
          setToken(null);
          setLoading(false);
          router.replace("/login");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  const crumb = useMemo(() => formatBreadcrumb(pathname), [pathname]);

  const navCls = (href: string, activePrefixes?: string[]) => {
    const active =
      pathname === href ||
      (activePrefixes?.some((p) => pathname.startsWith(p)) ?? false);
    return `portal-nav-item ${active ? "on" : ""}`;
  };

  const initials = useMemo(() => {
    if (!emailHint) return "?";
    const part = emailHint.split("@")[0] ?? "?";
    return part.slice(0, 2).toUpperCase();
  }, [emailHint]);

  const onSignOut = async () => {
    const supabase = createSupabaseBrowserClient();
    await supabase.auth.signOut();
    router.replace("/login");
    router.refresh();
  };

  if (loading) {
    return (
      <div className="portal-root">
        <div className="portal-loading">Loading session…</div>
      </div>
    );
  }

  if (!token) {
    return null;
  }

  return (
    <PortalAuthProvider token={token}>
      <div className="portal-root">
        <aside className="portal-sidebar">
          <div className="portal-logo">
            <div className="portal-logo-icon">
              <IconCalendarEvent size={16} stroke={2} />
            </div>
            <div>
              <div className="portal-logo-name">EventFlow</div>
              <div className="portal-logo-sub">Studio</div>
            </div>
          </div>
          <nav className="portal-nav" aria-label="Main navigation">
            <div className="portal-nav-grp">Overview</div>
            <Link href="/dashboard" className={navCls("/dashboard")}>
              <IconLayoutDashboard size={15} stroke={1.75} />
              Dashboard
            </Link>
            <Link href="/listings" className={navCls("/listings", ["/listings/"])}>
              <IconCalendar size={15} stroke={1.75} />
              Listings
            </Link>
            <div className="portal-nav-grp">Manage</div>
            <Link href="/businesses" className={navCls("/businesses")}>
              <IconBuildingStore size={15} stroke={1.75} />
              Businesses
            </Link>
            <Link href="/billing" className={navCls("/billing")}>
              <IconCreditCard size={15} stroke={1.75} />
              Billing
            </Link>
            <div className="portal-nav-grp">System</div>
            <Link href="/settings" className={navCls("/settings")}>
              <IconSettings size={15} stroke={1.75} />
              Settings
            </Link>
          </nav>
          <div className="portal-sidebar-foot">
            <div className="portal-logo-icon" style={{ width: 28, height: 28, borderRadius: "50%", fontSize: 10 }}>
              <span style={{ fontWeight: 600 }}>{initials}</span>
            </div>
            <div className="portal-sidebar-foot-meta">
              <div className="portal-sidebar-foot-name">{emailHint ?? "Signed in"}</div>
              <div className="portal-sidebar-foot-role">Organizer</div>
            </div>
            <IconDotsVertical size={13} color="#333" style={{ flexShrink: 0 }} aria-hidden />
          </div>
        </aside>

        <div className="portal-main">
          <header className="portal-topbar">
            <div className="portal-topbar-title">
              <span className="portal-topbar-title-muted">{crumb.muted}</span>/ {crumb.rest}
            </div>
            <div
              className="portal-topbar-pill"
              title={
                process.env.NEXT_PUBLIC_EVENTFLOW_API_PROXY === "1"
                  ? "Requests use /api/eventflow proxy (see EVENTFLOW_UPSTREAM_URL on server)"
                  : (process.env.NEXT_PUBLIC_EVENTFLOW_API_URL ?? "")
              }
            >
              <b>API</b> {apiPillText()}
            </div>
            <button type="button" className="portal-icon-btn" title="Notifications (coming soon)" aria-label="Notifications (coming soon)">
              <IconBell size={14} stroke={1.5} />
            </button>
            <button type="button" className="portal-btn-signout" onClick={() => void onSignOut()}>
              <IconLogout size={13} stroke={2} />
              Sign out
            </button>
          </header>
          <div className="portal-content">{children}</div>
        </div>
      </div>
    </PortalAuthProvider>
  );
}
