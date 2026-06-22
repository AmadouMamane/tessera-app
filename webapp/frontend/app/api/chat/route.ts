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
import { hasCollectionsAccess, isOperator } from "@/lib/auth/roles";
import { isGatedModel } from "@/lib/models";
import { backendHeaders, backendUrl } from "@/lib/server/backend";
import { OPERATOR_ASSERTION_HEADER, mintOperatorAssertion } from "@/lib/server/operator-assertion";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const SESSION_COOKIE = "tessera_sid";
const SESSION_MAX_AGE = 60 * 60 * 24; // 24h

// The client surface hint a privileged surface sends (see lib/api/sse.ts). It is
// NOT a privilege: it only selects an operator branch *when* the request also
// carries the right verified next-auth session (auth()). A forged hint from a
// visitor mints nothing — the turn stays customer/widget.
const CLIENT_SURFACE_HEADER = "x-tessera-client-surface";
const CONSOLE_SURFACE = "console"; // cockpit operator console (Phase B)
const RECOUVREMENT_SURFACE = "recouvrement"; // recouvrement business console (Phase C)

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
  // Resolve the operator session once (server-verified next-auth JWT). It gates
  // both the paid-model lock and the operator-assertion minting below.
  const session = await auth();
  if (requestedModel && isGatedModel(requestedModel)) {
    if (session?.user?.role !== "superadmin") {
      return NextResponse.json(
        { detail: "Ce modèle frontier est réservé au compte super-admin." },
        { status: 403 },
      );
    }
  }

  // Operator forwarding (ADR 0010 Phase B/C): mint a signed assertion the agent
  // verifies to derive AuthState.OPERATOR on the carried surface. The privilege
  // portal is auth() (the next-auth session cookie verified server-side), never
  // the client hint — without the right session role, no assertion is minted and
  // the turn stays on the customer/widget path.
  //   - cockpit console (Phase B) → cockpit-embedded, for platform operators;
  //   - recouvrement business console (Phase C) → dedicated-ui, for the
  //     collections role (or a platform operator supervising).
  const clientSurface = request.headers.get(CLIENT_SURFACE_HEADER);
  const role = session?.user?.role;
  const principal = session?.user?.name ?? role;
  let operatorAssertion: string | null = null;
  if (role && principal) {
    if (clientSurface === CONSOLE_SURFACE && isOperator(role)) {
      operatorAssertion = mintOperatorAssertion(principal, role, "cockpit-embedded");
    } else if (clientSurface === RECOUVREMENT_SURFACE && hasCollectionsAccess(role)) {
      operatorAssertion = mintOperatorAssertion(principal, role, "dedicated-ui");
    }
  }

  // Per-browser session id — the rate-limit key. Reuse the cookie if present,
  // otherwise mint one and set it on the response. httpOnly so client JS can
  // never read or spoof it.
  let sessionId = request.cookies.get(SESSION_COOKIE)?.value;
  const isNewSession = !sessionId;
  if (!sessionId) sessionId = crypto.randomUUID();

  // Forward the signed customer-session cookie so the backend can derive
  // auth_state from it (ADR 0008/0009). It is the *only* thing that lifts the
  // turn from anonymous to customer — never the request body.
  const customerSession = request.cookies.get("tessera_session")?.value;

  const upstream = await fetch(`${backendUrl()}/chat`, {
    method: "POST",
    headers: backendHeaders({
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      "X-Session-Id": sessionId,
      ...(customerSession ? { Cookie: `tessera_session=${customerSession}` } : {}),
      ...(operatorAssertion ? { [OPERATOR_ASSERTION_HEADER]: operatorAssertion } : {}),
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
