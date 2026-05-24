"use client";

import {
  IconDotsVertical,
  IconLayoutDashboard,
  IconLink,
  IconLogout,
  IconPhoto,
  IconSettings,
  IconShieldLock,
  IconCalendarEvent,
  IconBuildingStore,
  IconTicket,
  IconAlertTriangle,
  IconHandStop,
  IconVideo,
  IconCoin,
} from "@tabler/icons-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { createSupabaseBrowserClient } from "@/lib/supabase-browser";
import { getAdminMe } from "@/lib/eventflow-api";
import { AdminAuthProvider } from "./admin-auth-context";

type GatePhase = "loading" | "forbidden" | "gate_error" | "ready";

function formatBreadcrumb(pathname: string): { muted: string; rest: string } {
  if (pathname === "/") return { muted: "Admin", rest: "Overview" };
  if (pathname === "/businesses") return { muted: "Directory", rest: "Businesses" };
  if (pathname === "/listings") return { muted: "Directory", rest: "Community listings" };
  if (pathname === "/posters") return { muted: "Media", rest: "Poster assets" };
  if (pathname === "/shared-links") return { muted: "Moderation", rest: "Shared links" };
  if (pathname === "/orders") return { muted: "Ticketing", rest: "Orders" };
  if (pathname === "/claims") return { muted: "Ticketing", rest: "Claims" };
  if (pathname === "/payouts") return { muted: "Finance", rest: "Payouts" };
  if (pathname.startsWith("/claims/")) return { muted: "Ticketing", rest: "Claim detail" };
  if (pathname === "/video-moderation") return { muted: "Moderation", rest: "Feed videos" };
  if (pathname === "/platform-settings") return { muted: "System", rest: "Platform settings" };
  return { muted: "Admin", rest: "Console" };
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

export function AdminShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [phase, setPhase] = useState<GatePhase>("loading");
  const [token, setToken] = useState<string | null>(null);
  const [emailHint, setEmailHint] = useState<string | null>(null);
  const [gateError, setGateError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const supabase = createSupabaseBrowserClient();
        const { data } = await supabase.auth.getSession();
        const t = data.session?.access_token ?? null;
        const em = data.session?.user?.email ?? null;
        if (!t) {
          if (!cancelled) router.replace("/login");
          return;
        }
        try {
          await getAdminMe(t);
          if (!cancelled) {
            setToken(t);
            setEmailHint(em);
            setPhase("ready");
          }
        } catch (e: unknown) {
          const st = typeof e === "object" && e && "status" in e ? (e as { status?: number }).status : undefined;
          const msg = e instanceof Error ? e.message : String(e);
          if (!cancelled) {
            setToken(t);
            setEmailHint(em);
            if (st === 403) setPhase("forbidden");
            else {
              setGateError(msg);
              setPhase("gate_error");
            }
          }
        }
      } catch {
        if (!cancelled) router.replace("/login");
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

  if (phase === "loading" || token === null) {
    return (
      <div className="portal-root">
        <div className="portal-loading">Checking session…</div>
      </div>
    );
  }

  if (phase === "forbidden") {
    return (
      <div className="marketing-wrap">
        <div className="card">
          <h1 style={{ marginTop: 0 }}>Not an admin</h1>
          <p style={{ color: "var(--muted)" }}>
            You are signed in as <strong>{emailHint ?? "—"}</strong>, but this account is not allowed to use the admin
            console. Ask whoever runs EventFlow for your organization to grant operator access for your email, then refresh
            this page.
          </p>
          <button type="button" onClick={() => void onSignOut()}>
            Sign out
          </button>
        </div>
      </div>
    );
  }

  if (phase === "gate_error" && token) {
    return (
      <div className="marketing-wrap">
        <div className="card">
          <h1 style={{ marginTop: 0 }}>Could not verify admin</h1>
          <p style={{ color: "var(--muted)" }}>
            Signed in as <strong>{emailHint ?? "—"}</strong>. The admin check request failed:
          </p>
          <p className="error">{gateError ?? "Unknown error"}</p>
          <button type="button" onClick={() => void onSignOut()}>
            Sign out
          </button>
        </div>
      </div>
    );
  }

  return (
    <AdminAuthProvider token={token}>
      <div className="portal-root">
        <aside className="portal-sidebar">
          <div className="portal-logo">
            <div className="portal-logo-icon">
              <IconShieldLock size={16} stroke={2} />
            </div>
            <div>
              <div className="portal-logo-name">EventFlow</div>
              <div className="portal-logo-sub">Admin</div>
            </div>
          </div>
          <nav className="portal-nav" aria-label="Main navigation">
            <div className="portal-nav-grp">Overview</div>
            <Link href="/" className={navCls("/")}>
              <IconLayoutDashboard size={15} stroke={1.75} />
              Dashboard
            </Link>
            <div className="portal-nav-grp">Directory</div>
            <Link href="/businesses" className={navCls("/businesses")}>
              <IconBuildingStore size={15} stroke={1.75} />
              Businesses
            </Link>
            <Link href="/listings" className={navCls("/listings")}>
              <IconCalendarEvent size={15} stroke={1.75} />
              Listings
            </Link>
            <Link href="/posters" className={navCls("/posters")}>
              <IconPhoto size={15} stroke={1.75} />
              Posters
            </Link>
            <div className="portal-nav-grp">Moderation</div>
            <Link href="/shared-links" className={navCls("/shared-links")}>
              <IconLink size={15} stroke={1.75} />
              Shared links
            </Link>
            <Link href="/video-moderation" className={navCls("/video-moderation")}>
              <IconVideo size={15} stroke={1.75} />
              Videos
            </Link>
            <div className="portal-nav-grp">Ticketing</div>
            <Link href="/orders" className={navCls("/orders")}>
              <IconTicket size={15} stroke={1.75} />
              Orders
            </Link>
            <Link href="/claims" className={navCls("/claims", ["/claims/"])}>
              <IconAlertTriangle size={15} stroke={1.75} />
              Claims
            </Link>
            <div className="portal-nav-grp">Finance</div>
            <Link href="/payouts" className={navCls("/payouts")}>
              <IconHandStop size={15} stroke={1.75} />
              Payouts
            </Link>
            <div className="portal-nav-grp">System</div>
            <Link href="/platform-settings" className={navCls("/platform-settings")}>
              <IconCoin size={15} stroke={1.75} />
              Platform settings
            </Link>
          </nav>
          <div className="portal-sidebar-foot">
            <div className="portal-logo-icon" style={{ width: 28, height: 28, borderRadius: "50%", fontSize: 10 }}>
              <span style={{ fontWeight: 600 }}>{initials}</span>
            </div>
            <div className="portal-sidebar-foot-meta">
              <div className="portal-sidebar-foot-name">{emailHint ?? "Signed in"}</div>
              <div className="portal-sidebar-foot-role">Operator</div>
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
                  ? "API requests go through this site’s proxy"
                  : (process.env.NEXT_PUBLIC_EVENTFLOW_API_URL ?? "")
              }
            >
              <b>API</b> {apiPillText()}
            </div>
            <button type="button" className="portal-btn-signout" onClick={() => void onSignOut()}>
              <IconLogout size={13} stroke={2} />
              Sign out
            </button>
          </header>
          <div className="portal-content">{children}</div>
        </div>
      </div>
    </AdminAuthProvider>
  );
}
