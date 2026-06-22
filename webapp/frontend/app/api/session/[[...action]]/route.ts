/**
 * Server-side proxy for the customer-session endpoints (ADR 0008/0009).
 *
 *   GET  /api/session         → backend GET  /session         (introspect)
 *   POST /api/session/login   → backend POST /session/login   (demo login)
 *   POST /api/session/logout  → backend POST /session/logout  (logout)
 *
 * This is the *customer* session (signed cookie that derives the agent's
 * auth_state), distinct from the operator/dashboard NextAuth session. The proxy
 * forwards the browser's cookie up to the backend and relays the backend's
 * Set-Cookie back down, so the httpOnly signed cookie round-trips first-party.
 */
import { type NextRequest, NextResponse } from "next/server";

import { backendHeaders, backendUrl } from "@/lib/server/backend";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function relaySetCookie(upstream: Response, headers: Headers): void {
  // undici exposes multiple Set-Cookie via getSetCookie(); fall back to the
  // single combined header otherwise.
  const cookies =
    typeof upstream.headers.getSetCookie === "function"
      ? upstream.headers.getSetCookie()
      : [upstream.headers.get("set-cookie")].filter((v): v is string => v !== null);
  for (const cookie of cookies) headers.append("set-cookie", cookie);
}

async function proxy(request: NextRequest, method: "GET" | "POST", path: string): Promise<Response> {
  const cookie = request.headers.get("cookie");
  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}${path}`, {
      method,
      headers: backendHeaders({
        Accept: "application/json",
        ...(cookie ? { Cookie: cookie } : {}),
      }),
    });
  } catch (err) {
    return NextResponse.json(
      { detail: err instanceof Error ? err.message : "backend unreachable" },
      { status: 502 },
    );
  }

  const headers = new Headers();
  const contentType = upstream.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  relaySetCookie(upstream, headers);
  return new Response(upstream.body, { status: upstream.status, headers });
}

export async function GET(request: NextRequest): Promise<Response> {
  return proxy(request, "GET", "/session");
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ action?: string[] }> },
): Promise<Response> {
  const { action } = await context.params;
  const head = action?.[0];
  if (head === "login") return proxy(request, "POST", "/session/login");
  if (head === "logout") return proxy(request, "POST", "/session/logout");
  return NextResponse.json({ detail: "not found" }, { status: 404 });
}
