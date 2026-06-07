/**
 * Server-side proxy for the backend read endpoints (audit, healthz, readyz,
 * budget). A next.config rewrite cannot inject the Authorization header, so we
 * proxy here instead and attach the service-to-service bearer token.
 *
 * The more specific `app/api/chat/route.ts` takes precedence over this
 * catch-all, so POST /api/chat is unaffected.
 *
 * Security: this proxy authenticates on the caller's behalf, so it must NOT be
 * a wildcard — that would make every authenticated agent GET endpoint anonymously
 * reachable through the public front. We allowlist by first path segment:
 *   - healthz/readyz  → always public (liveness/readiness)
 *   - audit           → admin or auditor (ADR 0009; replaces TESSERA_DASHBOARD_PUBLIC)
 *   - budget          → admin only (cost counters)
 *   - observability   → admin or auditor (assurance cockpit)
 *   - anything else   → never proxied (404)
 */
import { type NextRequest, NextResponse } from "next/server";

import { auth } from "@/auth";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const ALWAYS_PUBLIC = new Set(["healthz", "readyz"]);

function isAllowedOperatorPath(head: string, role: string | undefined): boolean {
  const operator = role === "admin" || role === "auditor" || role === "superadmin";
  return (
    (head === "audit" && operator) ||
    (head === "observability" && operator) ||
    (head === "budget" && (role === "admin" || role === "superadmin"))
  );
}

function isKnownOperatorPath(head: string): boolean {
  return head === "audit" || head === "budget" || head === "observability";
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await context.params;
  const head = path[0] ?? "";

  if (!ALWAYS_PUBLIC.has(head)) {
    const role = (await auth())?.user?.role;
    // superadmin is the highest role — it passes every operator gate.
    if (!isAllowedOperatorPath(head, role)) {
      // Known operator paths return 401 to signal auth; everything else is 404.
      return NextResponse.json(
        { detail: isKnownOperatorPath(head) ? "operator authentication required" : "not found" },
        { status: isKnownOperatorPath(head) ? 401 : 404 },
      );
    }
  }
  const target = `${backendUrl()}/${path.join("/")}${request.nextUrl.search}`;

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: "GET",
      headers: backendHeaders({
        Accept: request.headers.get("accept") ?? "application/json",
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
  return new Response(upstream.body, { status: upstream.status, headers });
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await context.params;
  const head = path[0] ?? "";
  const role = (await auth())?.user?.role;
  if (head !== "observability" || !isAllowedOperatorPath(head, role)) {
    return NextResponse.json(
      { detail: isKnownOperatorPath(head) ? "operator authentication required" : "not found" },
      { status: isKnownOperatorPath(head) ? 401 : 404 },
    );
  }

  const target = `${backendUrl()}/${path.join("/")}${request.nextUrl.search}`;
  const body = await request.text();
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: "POST",
      headers: backendHeaders({
        Accept: request.headers.get("accept") ?? "application/json",
        "Content-Type": request.headers.get("content-type") ?? "application/json",
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
