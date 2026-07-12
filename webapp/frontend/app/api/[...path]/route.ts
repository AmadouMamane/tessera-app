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
 *   - observability   → public AGGREGATES only (ADR 0009). The subject-scoped reads under
 *                       the same prefix — transcripts, session detail, memory inventory —
 *                       require a verified operator (see below).
 *   - audit           → admin or auditor (ADR 0009; replaces TESSERA_DASHBOARD_PUBLIC)
 *   - budget          → admin only (cost counters)
 *   - memory          → subject-scoped, so a verified operator (GDPR Art. 15 read)
 *   - anything else   → never proxied (404)
 *
 * Audit 2026-07-12, **P1 F-4**: `observability` sat in ALWAYS_PUBLIC as a whole, so
 * `GET /api/observability/conversation-messages?conversation_id=…` handed any conversation's
 * full transcript to an anonymous visitor — with the service bearer attached on their behalf.
 * The prefix is still public; the fourteen subject-scoped paths under it are not.
 */
import { type NextRequest, NextResponse } from "next/server";

import { auth } from "@/auth";
import { canMutateCockpit, canReadSubjectData, operatorSurfaceForRole } from "@/lib/auth/roles";
import { isSubjectScopedPath } from "@/lib/auth/subject-paths";
import { backendHeaders, backendUrl } from "@/lib/server/backend";
import { OPERATOR_ASSERTION_HEADER, mintOperatorAssertion } from "@/lib/server/operator-assertion";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const ALWAYS_PUBLIC = new Set(["healthz", "readyz", "observability"]);

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await context.params;
  const head = path[0] ?? "";

  // Subject-scoped reads (F-4). Checked BEFORE the ALWAYS_PUBLIC allowlist, because most of
  // them live under the `observability` prefix that allowlist opens. The agent re-checks the
  // assertion — this is the friendly refusal, that one is the authority.
  const subjectScoped = isSubjectScopedPath(path);
  const extraHeaders: Record<string, string> = {};

  if (subjectScoped) {
    const session = await auth();
    const role = session?.user?.role ?? null;
    if (role === null) {
      return NextResponse.json({ detail: "operator authentication required" }, { status: 401 });
    }
    if (!canReadSubjectData(role)) {
      return NextResponse.json(
        { detail: "this role may not read subject-scoped data" },
        {
          status: 403,
        },
      );
    }
    // Mint the assertion the agent verifies. The bearer this proxy attaches says only that
    // the call came from our frontend; it never says which human asked, and a transcript is
    // personal data. Without the assertion the agent refuses — which is the point.
    const surface = operatorSurfaceForRole(role);
    const assertion = surface
      ? mintOperatorAssertion(session?.user?.name ?? role, role, surface)
      : null;
    if (!assertion) {
      console.error(
        "[api] subject-scoped read blocked — TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY is " +
          "unset in the front env. Set the SAME secret on the agent and the front.",
      );
      return NextResponse.json(
        { detail: "operator assertion unavailable (signing key unset)" },
        { status: 503 },
      );
    }
    extraHeaders[OPERATOR_ASSERTION_HEADER] = assertion;
  } else if (!ALWAYS_PUBLIC.has(head)) {
    const role = (await auth())?.user?.role;
    // superadmin is the highest role — it passes every operator gate.
    const allowed =
      (head === "audit" && (role === "admin" || role === "auditor" || role === "superadmin")) ||
      (head === "budget" && (role === "admin" || role === "superadmin"));
    if (!allowed) {
      // Known operator paths return 401 to signal auth; everything else is 404.
      const known = head === "audit" || head === "budget";
      return NextResponse.json(
        { detail: known ? "operator authentication required" : "not found" },
        { status: known ? 401 : 404 },
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
        ...extraHeaders,
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

/**
 * POST is the MUTATION plane: the 26 observability POSTs promote an agent to production,
 * rewrite runtime configuration, switch a guardrail off and mutate the governance stores.
 *
 * Audit 2026-07-10, P0 `broken-access-control` (route.ts:25/81): this handler used to proxy
 * them with NO session check whatsoever — `observability` sat in ALWAYS_PUBLIC and the POST
 * branch only checked the path segment. Because the proxy attaches the service bearer on the
 * caller's behalf, an anonymous visitor's mutation arrived at the agent perfectly
 * authenticated. The bearer says "this came from our frontend"; it never says "who asked".
 *
 * Reads (GET) stay public — that is the cockpit's declared posture and is unchanged. Only
 * the mutation plane is gated, and it is gated on BOTH sides: here, so an anonymous POST is
 * refused at the edge; and in the agent, where the `mutations` router requires a verified
 * operator assertion. The frontend gate is the friendly one; the agent gate is the real one.
 *
 * Being an operator is not enough: the role must carry WRITE authority (`canMutateCockpit`).
 * The `auditor` reads and does not write (ADR 0009), so it is refused here — with a 403, not
 * a 401: it is authenticated, it simply may not do this.
 */
export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await context.params;
  if ((path[0] ?? "") !== "observability") {
    return NextResponse.json({ detail: "not found" }, { status: 404 });
  }
  const session = await auth();
  const role = session?.user?.role ?? null;
  // 401 and 403 are different answers and the order matters. No session at all → we do not
  // know who is asking (401, "authenticate"). A session whose role has no write authority —
  // an `auditor`, who reads and does not write (ADR 0009) — → we know exactly who is asking
  // and the answer is still no (403, "nothing to retry"). Telling an auditor to log in again
  // when they already have is a lie about what went wrong.
  if (role === null) {
    return NextResponse.json({ detail: "operator authentication required" }, { status: 401 });
  }
  if (!canMutateCockpit(role)) {
    return NextResponse.json(
      { detail: "this role is read-only on the cockpit control plane" },
      { status: 403 },
    );
  }

  // Mint the signed assertion the agent verifies. Without it the agent's `mutations` router
  // refuses the request — which is the point: the service bearer this proxy attaches proves
  // only that the call came from the frontend, never that a human operator authorized it.
  const principal = session?.user?.name ?? role;
  const operatorAssertion = mintOperatorAssertion(principal, role, "cockpit-embedded");
  if (!operatorAssertion) {
    // The signing key is unset, so no assertion can be minted and the agent will refuse.
    // Fail here with a diagnosable message rather than letting it surface as an opaque 401.
    console.error(
      "[api] operator mutation blocked — TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY is unset " +
        "in the front env. Set the SAME secret on the agent and the front.",
    );
    return NextResponse.json(
      { detail: "operator assertion unavailable (signing key unset)" },
      { status: 503 },
    );
  }

  const target = `${backendUrl()}/${path.join("/")}${request.nextUrl.search}`;
  const body = await request.text();

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: "POST",
      headers: backendHeaders({
        "content-type": request.headers.get("content-type") ?? "application/json",
        Accept: "application/json",
        [OPERATOR_ASSERTION_HEADER]: operatorAssertion,
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
