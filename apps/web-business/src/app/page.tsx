import Link from "next/link";

export default function HomePage() {
  return (
    <div className="marketing-wrap">
      <div className="card">
      <h1 style={{ marginTop: 0 }}>EventFlow business portal</h1>
      <p style={{ color: "var(--muted)" }}>
        Sign in with the same Supabase account as the mobile app, then manage community listings, business
        attachments, share aliases, and promo videos.
      </p>
      <p>
        <Link href="/login">Sign in</Link>
        {" · "}
        <Link href="/dashboard">Dashboard</Link>
      </p>
      </div>
    </div>
  );
}
