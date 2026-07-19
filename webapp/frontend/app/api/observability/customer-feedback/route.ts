/**
 * Server-side proxy for the customer feedback endpoint (ADR 0041).
 *
 *   POST /api/observability/customer-feedback → backend POST /observability/customer-feedback
 *
 * Customer plane: NO operator session. The generic catch-all POST proxy
 * (`app/api/[...path]/route.ts`) requires an operator and would refuse an anonymous
 * customer — so this dedicated, more-specific route takes precedence (like `/api/chat`).
 * Like `GET /session/transcript`, it forwards the browser's signed resume capability; the
 * agent verifies it and binds the vote to the conversation. The service bearer
 * (`backendHeaders`) says only that the call came from our front, never who voted.
 */
import { type NextRequest, NextResponse } from "next/server";

import { backendHeaders, backendUrl } from "@/lib/server/backend";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/** Header the agent reads the conversation-resume capability from (mirrors api/session.py). */
const RESUME_TOKEN_HEADER = "X-Tessera-Resume-Token";

export async function POST(request: NextRequest): Promise<Response> {
  const token = request.headers.get(RESUME_TOKEN_HEADER);
  if (!token) {
    return NextResponse.json(
      { detail: "a valid resume capability is required to leave feedback" },
      { status: 403 },
    );
  }
  const body = await request.text();
  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}/observability/customer-feedback`, {
      method: "POST",
      headers: backendHeaders({
        "content-type": "application/json",
        Accept: "application/json",
        [RESUME_TOKEN_HEADER]: token,
      }),
      body,
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
  return new Response(upstream.body, { status: upstream.status, headers });
}
