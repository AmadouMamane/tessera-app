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

async function proxy(
  request: NextRequest,
  method: "GET" | "POST",
  path: string,
): Promise<Response> {
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

/** Header the agent reads the conversation-resume capability from (mirrors api/session.py). */
const RESUME_TOKEN_HEADER = "X-Tessera-Resume-Token";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ action?: string[] }> },
): Promise<Response> {
  const { action } = await context.params;

  // The customer's own transcript (audit 2026-07-12, F-4). The widget used to resume through
  // `/observability/conversation-messages`, an operator endpoint that answered anyone for any
  // conversation id. That id was never a secret — `/observability/conversations` published it
  // next to the opening user message — so the read now demands the signed capability the agent
  // minted for THIS browser at `turn.start`. We forward it; the agent verifies it.
  if (action?.[0] === "transcript") {
    const conversationId = request.nextUrl.searchParams.get("conversation_id") ?? "";
    const token = request.headers.get(RESUME_TOKEN_HEADER);
    if (!token) {
      return NextResponse.json(
        { detail: "a valid resume capability is required for this conversation" },
        { status: 403 },
      );
    }
    let upstream: Response;
    try {
      upstream = await fetch(
        `${backendUrl()}/session/transcript?conversation_id=${encodeURIComponent(conversationId)}`,
        {
          method: "GET",
          headers: backendHeaders({
            Accept: "application/json",
            [RESUME_TOKEN_HEADER]: token,
          }),
        },
      );
    } catch (err) {
      return NextResponse.json(
        { detail: err instanceof Error ? err.message : "backend unreachable" },
        { status: 502 },
      );
    }
    const headers = new Headers();
    const contentType = upstream.headers.get("content-type");
    if (contentType) headers.set("content-type", contentType);
    return new Response(upstream.body, { status: upstream.status, headers });
  }

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
