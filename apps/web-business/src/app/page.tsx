import Link from "next/link";

export default function HomePage() {
  return (
    <div className="auth-shell">
      <div className="auth-card" style={{ maxWidth: 440 }}>
        <p className="auth-brand">EventFlow</p>
        <h1 className="auth-title">Business portal</h1>
        <p className="auth-lede" style={{ marginBottom: "1.75rem" }}>
          Sign in with the same EventFlow account you use on your phone. From here you can manage community listings,
          business attachments, share aliases, and promo videos.
        </p>
        <div className="auth-actions-row">
          <Link href="/login" className="auth-primary-link">
            Sign in
          </Link>
          <Link href="/dashboard" style={{ fontSize: "0.9rem", color: "var(--muted)", alignSelf: "center" }}>
            Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
