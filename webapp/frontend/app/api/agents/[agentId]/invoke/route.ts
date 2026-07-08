/**
 * Route handler for POST /api/agents/[agentId]/invoke (ADR 0019 §I3).
 *
 * The Console's server seam for testing an `http`-binding agent. Like /api/chat it mints a
 * signed operator assertion from the server-verified next-auth session (never a client
 * claim) and forwards it to the backend invocation route — but this is request/response
 * JSON, not SSE. The backend enforces operator + plane + binding; this proxy's job is the
 * operator-assertion minting and the service bearer, exactly as the chat proxy does.
 *
 * Without a privileged role (or with the signing key unset) no assertion is minted and the
 * backend refuses the turn — the honest, fail-closed direction.
 */
import { type NextRequest, NextResponse } from "next/server";

import { auth } from "@/auth";
import { operatorSurfaceForHint } from "@/lib/auth/roles";
import { backendHeaders, backendUrl } from "@/lib/server/backend";
import { OPERATOR_ASSERTION_HEADER, mintOperatorAssertion } from "@/lib/server/operator-assertion";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ agentId: string }> },
): Promise<Response> {
  const { agentId } = await context.params;
  const body = await request.text();

  // Operator forwarding (ADR 0010 Phase B): the console is a cockpit-embedded surface, so a
  // platform operator mints a cockpit-embedded assertion. The privilege portal is auth(),
  // never a client field; without the right role nothing is minted and the backend refuses.
  const session = await auth();
  const role = session?.user?.role ?? null;
  const principal = session?.user?.name ?? role;
  const mintedSurface = operatorSurfaceForHint(role, "console");
  const operatorAssertion =
    role && principal && mintedSurface
      ? mintOperatorAssertion(principal, role, mintedSurface)
      : null;

  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}/agents/${encodeURIComponent(agentId)}/invoke`, {
      method: "POST",
      headers: backendHeaders({
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(operatorAssertion ? { [OPERATOR_ASSERTION_HEADER]: operatorAssertion } : {}),
      }),
      body,
      signal: request.signal,
    });
  } catch (err) {
    return NextResponse.json(
      { detail: err instanceof Error ? err.message : "backend unreachable" },
      { status: 502 },
    );
  }

  const text = await upstream.text();
  const headers = new Headers();
  const contentType = upstream.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  return new Response(text, { status: upstream.status, headers });
}
