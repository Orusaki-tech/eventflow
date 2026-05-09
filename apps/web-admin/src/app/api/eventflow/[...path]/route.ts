import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
]);

function upstreamRoot(): string | null {
  const u = process.env.EVENTFLOW_UPSTREAM_URL?.trim();
  if (!u) return null;
  return u.replace(/\/$/, "");
}

async function proxy(req: NextRequest, pathSegments: string[]): Promise<NextResponse> {
  const root = upstreamRoot();
  if (!root) {
    return NextResponse.json(
      { detail: "EVENTFLOW_UPSTREAM_URL is not configured on the server (Vercel env)." },
      { status: 500 }
    );
  }

  const pathPart = pathSegments.join("/");
  const target = `${root}/${pathPart}${req.nextUrl.search}`;

  const headers = new Headers();
  const auth = req.headers.get("authorization");
  if (auth) headers.set("Authorization", auth);
  const accept = req.headers.get("accept");
  if (accept) headers.set("Accept", accept);
  const ct = req.headers.get("content-type");
  if (ct && !["GET", "HEAD"].includes(req.method)) {
    headers.set("Content-Type", ct);
  }

  const init: RequestInit = {
    method: req.method,
    headers,
    redirect: "manual",
  };

  if (!["GET", "HEAD"].includes(req.method)) {
    const buf = await req.arrayBuffer();
    if (buf.byteLength) init.body = buf;
  }

  let upstreamRes: Response;
  try {
    upstreamRes = await fetch(target, init);
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ detail: `Upstream fetch failed: ${msg}` }, { status: 502 });
  }

  const outHeaders = new Headers();
  upstreamRes.headers.forEach((value, key) => {
    if (HOP_BY_HOP.has(key.toLowerCase())) return;
    outHeaders.set(key, value);
  });

  const body = await upstreamRes.arrayBuffer();
  return new NextResponse(body, { status: upstreamRes.status, headers: outHeaders });
}

type Ctx = { params: { path: string[] } };

export async function GET(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params.path);
}

export async function POST(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params.path);
}

export async function PUT(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params.path);
}

export async function PATCH(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params.path);
}

export async function DELETE(req: NextRequest, ctx: Ctx) {
  return proxy(req, ctx.params.path);
}
