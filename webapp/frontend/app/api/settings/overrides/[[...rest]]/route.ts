/**
 * BFF for the governed operable-knob overrides (ADR 0030).
 *
 * GET  /api/settings/overrides          → the knob panel (any authenticated operator)
 * PUT  /api/settings/overrides          → set one override, key in body (superadmin)
 * POST /api/settings/overrides/revert   → revert one override, key in body (superadmin)
 *
 * Same split as `settings/synthesis-access`: the check here is the friendly
 * refusal that keeps the UI honest; the agent's `require_superadmin` on the
 * verified operator assertion is the authority (ADR 0024). The service bearer
 * this proxy attaches proves the call came from our frontend — only the minted
 * assertion says which human authorized it.
 */
import { type NextRequest, NextResponse } from "next/server";

import { auth } from "@/auth";
import { backendHeaders, backendUrl } from "@/lib/server/backend";
import { OPERATOR_ASSERTION_HEADER, mintOperatorAssertion } from "@/lib/server/operator-assertion";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type Ctx = { params: Promise<{ rest?: string[] }> };

export async function GET(_request: NextRequest, context: Ctx): Promise<Response> {
  const { rest } = await context.params;
  if ((rest ?? []).length > 0) {
    return NextResponse.json({ detail: "not found" }, { status: 404 });
  }
  // The panel names operator principals (override authors) — an operator page,
  // not a public aggregate. Any authenticated operator role may read it.
  const role = (await auth())?.user?.role;
  if (!role) {
    return NextResponse.json({ detail: "operator authentication required" }, { status: 401 });
  }
  try {
    const upstream = await fetch(`${backendUrl()}/settings/overrides`, {
      headers: backendHeaders({ Accept: "application/json" }),
      cache: "no-store",
    });
    return new Response(upstream.body, {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
    });
  } catch (err) {
    return NextResponse.json(
      { detail: err instanceof Error ? err.message : "backend unreachable" },
      { status: 502 },
    );
  }
}

/** Superadmin gate + assertion mint shared by the two mutations. */
async function mintSuperadmin(): Promise<{ assertion: string } | Response> {
  const session = await auth();
  const role = session?.user?.role;
  if (role !== "superadmin") {
    return NextResponse.json({ detail: "superadmin only" }, { status: 403 });
  }
  const assertion = mintOperatorAssertion(session?.user?.name ?? role, role, "cockpit-embedded");
  if (!assertion) {
    console.error(
      "[api] override mutation blocked — TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY is unset " +
        "in the front env. Set the SAME secret on the agent and the front.",
    );
    return NextResponse.json(
      { detail: "operator assertion unavailable (signing key unset)" },
      { status: 503 },
    );
  }
  return { assertion };
}

async function forward(
  target: string,
  method: "PUT" | "POST",
  assertion: string,
  body: unknown,
): Promise<Response> {
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method,
      headers: backendHeaders({
        "Content-Type": "application/json",
        [OPERATOR_ASSERTION_HEADER]: assertion,
      }),
      body: JSON.stringify(body),
    });
  } catch (err) {
    return NextResponse.json(
      { detail: err instanceof Error ? err.message : "backend unreachable" },
      { status: 502 },
    );
  }
  return new Response(upstream.body, {
    status: upstream.status,
    headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
  });
}

export async function PUT(request: NextRequest, context: Ctx): Promise<Response> {
  const { rest } = await context.params;
  if ((rest ?? []).length > 0) {
    return NextResponse.json({ detail: "not found" }, { status: 404 });
  }
  const gate = await mintSuperadmin();
  if (gate instanceof Response) return gate;
  const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  return forward(`${backendUrl()}/settings/overrides`, "PUT", gate.assertion, {
    key: body.key,
    value: body.value,
    reason: body.reason,
  });
}

export async function POST(request: NextRequest, context: Ctx): Promise<Response> {
  const { rest } = await context.params;
  if (!(rest?.length === 1 && rest[0] === "revert")) {
    return NextResponse.json({ detail: "not found" }, { status: 404 });
  }
  const gate = await mintSuperadmin();
  if (gate instanceof Response) return gate;
  const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  return forward(`${backendUrl()}/settings/overrides/revert`, "POST", gate.assertion, {
    key: body.key,
    reason: body.reason,
  });
}
