/**
 * Route handler for POST /api/chat.
 *
 * Proxies the request to the FastAPI backend and streams the SSE response
 * back to the browser. Using a route handler instead of a next.config rewrite
 * is required for SSE: the rewrite layer buffers the full response before
 * forwarding, which breaks streaming for long LLM calls — and, unlike a
 * rewrite, lets us inject the service-to-service bearer token and the
 * per-session id used for rate limiting.
 */
import { type NextRequest, NextResponse } from "next/server";

import { auth } from "@/auth";
import { isGatedModel } from "@/lib/models";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const SESSION_COOKIE = "tessera_sid";
const SESSION_MAX_AGE = 60 * 60 * 24; // 24h

export async function POST(request: NextRequest): Promise<Response> {
  const body = await request.text();

  // Server-side gate for paid frontier models (e.g. GPT-5.5): only the
  // superadmin may run them, so a public visitor can't burn API credits by
  // POSTing the model id directly. This is the authoritative lock — the UI
  // disabling the card is only a courtesy.
  let requestedModel: string | undefined;
  try {
    requestedModel = (JSON.parse(body) as { model?: string }).model;
  } catch {
    requestedModel = undefined;
  }
  if (requestedModel && isGatedModel(requestedModel)) {
    const session = await auth();
    if (session?.user?.role !== "superadmin") {
      return NextResponse.json(
        { detail: "Ce modèle frontier est réservé au compte super-admin." },
        { status: 403 },
      );
    }
  }

  // Per-browser session id — the rate-limit key. Reuse the cookie if present,
  // otherwise mint one and set it on the response. httpOnly so client JS can
  // never read or spoof it.
  let sessionId = request.cookies.get(SESSION_COOKIE)?.value;
  const isNewSession = !sessionId;
  if (!sessionId) sessionId = crypto.randomUUID();

  const upstream = await fetch(`${backendUrl()}/chat`, {
    method: "POST",
    headers: backendHeaders({
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      "X-Session-Id": sessionId,
    }),
    body,
    // Propagate the client's abort (stop button / navigation) to the backend so
    // it cancels generation instead of running the LLM to completion unseen.
    signal: request.signal,
  });

  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.text().catch(() => "");
    // Forward Retry-After so the client can show the exact wait on a 429.
    const retryAfter = upstream.headers.get("Retry-After");
    return NextResponse.json(
      { detail: detail || `upstream error ${upstream.status}` },
      {
        status: upstream.status,
        headers: retryAfter ? { "Retry-After": retryAfter } : undefined,
      },
    );
  }

  const headers = new Headers({
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
    "X-Accel-Buffering": "no",
  });
  if (isNewSession) {
    headers.append(
      "Set-Cookie",
      `${SESSION_COOKIE}=${sessionId}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${SESSION_MAX_AGE}`,
    );
  }

  return new Response(upstream.body, { status: 200, headers });
}
