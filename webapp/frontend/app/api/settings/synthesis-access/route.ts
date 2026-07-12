/**
 * Superadmin-gated write for the "admin may see the synthesis" grant.
 *
 * The enforcement used to live ONLY here — "the agent persists the flag without its own role
 * check", as this file once said. That is the finding (audit 2026-07-12, **P1 F-5**): a rule
 * enforced in the browser's own BFF is not enforced, because the service bearer the proxy
 * attaches authenticates the *frontend*, never the human, and nothing obliged a caller to
 * come through here at all.
 *
 * The agent now carries the authority (`require_superadmin`), so this route must mint the
 * signed operator assertion it verifies — the check below is the friendly refusal that keeps
 * the UI honest, not the lock. Mirrors the read in `lib/server/settings.ts` and the mint in
 * `app/api/[...path]/route.ts`.
 */
import { type NextRequest, NextResponse } from "next/server";

import { auth } from "@/auth";
import { backendHeaders, backendUrl } from "@/lib/server/backend";
import { OPERATOR_ASSERTION_HEADER, mintOperatorAssertion } from "@/lib/server/operator-assertion";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(): Promise<Response> {
  const role = (await auth())?.user?.role;
  if (role !== "superadmin") {
    return NextResponse.json({ detail: "superadmin only" }, { status: 403 });
  }
  try {
    const upstream = await fetch(`${backendUrl()}/settings/synthesis-admin`, {
      headers: backendHeaders({ Accept: "application/json" }),
      cache: "no-store",
    });
    const data = await upstream.json().catch(() => ({ enabled: false }));
    return NextResponse.json(data, { status: upstream.status });
  } catch (err) {
    return NextResponse.json(
      { detail: err instanceof Error ? err.message : "backend unreachable" },
      { status: 502 },
    );
  }
}

export async function PUT(request: NextRequest): Promise<Response> {
  const session = await auth();
  const role = session?.user?.role;
  if (role !== "superadmin") {
    return NextResponse.json({ detail: "superadmin only" }, { status: 403 });
  }

  // The agent verifies this, and refuses without it (`require_superadmin`). The bearer below
  // proves the call came from our frontend; only this proves a superadmin authorized it.
  const assertion = mintOperatorAssertion(session?.user?.name ?? role, role, "cockpit-embedded");
  if (!assertion) {
    console.error(
      "[api] synthesis grant blocked — TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY is unset " +
        "in the front env. Set the SAME secret on the agent and the front.",
    );
    return NextResponse.json(
      { detail: "operator assertion unavailable (signing key unset)" },
      { status: 503 },
    );
  }

  let enabled = false;
  try {
    const body = (await request.json()) as { enabled?: unknown };
    enabled = Boolean(body?.enabled);
  } catch {
    enabled = false;
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}/settings/synthesis-admin`, {
      method: "PUT",
      headers: backendHeaders({
        "Content-Type": "application/json",
        [OPERATOR_ASSERTION_HEADER]: assertion,
      }),
      body: JSON.stringify({ enabled }),
    });
  } catch (err) {
    return NextResponse.json(
      { detail: err instanceof Error ? err.message : "backend unreachable" },
      { status: 502 },
    );
  }

  const data = await upstream.json().catch(() => ({ enabled }));
  return NextResponse.json(data, { status: upstream.status });
}
