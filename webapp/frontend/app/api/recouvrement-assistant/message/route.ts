/**
 * BFF proxy for the recouvrement assistant's message workflow.
 *
 * Audit 2026-07-12, **P0 F-1**: this handler used to proxy with NO session check while
 * `backendHeaders` attached the service bearer on the caller's behalf — so an anonymous
 * visitor of the public URL reached a workflow that emits ~30 business events per turn
 * into the audit ledger. The bearer says "this came from our frontend"; it never says
 * "who asked". Same class as the 26 cockpit mutations closed on 2026-07-11
 * (`app/api/[...path]/route.ts`), whose POST branch this now mirrors.
 *
 * Gated on BOTH sides: here, so an anonymous POST is refused at the edge; and in the
 * agent, where the `recouvrement_assistant` router requires a verified operator
 * assertion (`require_collections_operator`). The frontend gate is the friendly one;
 * the agent gate is the real one.
 */
import { type NextRequest, NextResponse } from "next/server";

import { auth } from "@/auth";
import { canActOnCollections } from "@/lib/auth/roles";
import { backendHeaders, backendUrl } from "@/lib/server/backend";
import { OPERATOR_ASSERTION_HEADER, mintOperatorAssertion } from "@/lib/server/operator-assertion";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND_RECOUVREMENT_ASSISTANT_PATH = "/recouvrement-assistant/message";
const BACKEND_UNAVAILABLE_DETAIL = "recouvrement assistant backend unavailable";

export async function POST(request: NextRequest): Promise<Response> {
  const session = await auth();
  const role = session?.user?.role ?? null;
  // 401 and 403 are different answers (ADR 0009 doctrine, same as the cockpit BFF): no
  // session → we do not know who is asking, authenticate. A session whose role has no
  // write authority on this plane — the auditor, who may enter the console and may not
  // act from it — → we know exactly who is asking and the answer is still no.
  if (role === null) {
    return NextResponse.json({ detail: "operator authentication required" }, { status: 401 });
  }
  if (!canActOnCollections(role)) {
    return NextResponse.json(
      { detail: "this role is read-only on the recouvrement business plane" },
      { status: 403 },
    );
  }

  // Mint the signed assertion the agent verifies (surface: recouvrement's dedicated
  // console). The service bearer below proves only that the call came from our frontend;
  // the assertion is what proves a verified operator asked — and it carries the principal
  // the agent stamps into the ledger.
  const principal = session?.user?.name ?? role;
  const operatorAssertion = mintOperatorAssertion(principal, role, "dedicated-ui");
  if (!operatorAssertion) {
    console.error(
      "[recouvrement-assistant] blocked — TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY is unset " +
        "in the front env. Set the SAME secret on the agent and the front.",
    );
    return NextResponse.json(
      { detail: "operator assertion unavailable (signing key unset)" },
      { status: 503 },
    );
  }

  const body = await request.text();

  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}${BACKEND_RECOUVREMENT_ASSISTANT_PATH}`, {
      method: "POST",
      headers: backendHeaders({
        "content-type": request.headers.get("content-type") ?? "application/json",
        Accept: "application/json",
        [OPERATOR_ASSERTION_HEADER]: operatorAssertion,
      }),
      body,
      signal: request.signal,
    });
  } catch (err) {
    console.warn("[recouvrement-assistant] backend request failed", err);
    return NextResponse.json({ detail: BACKEND_UNAVAILABLE_DETAIL }, { status: 502 });
  }

  if (!upstream.ok) {
    const detail = await upstream.text().catch(() => "");
    console.warn("[recouvrement-assistant] backend rejected request", {
      status: upstream.status,
      detail,
    });
    return NextResponse.json(
      { detail: BACKEND_UNAVAILABLE_DETAIL },
      { status: upstream.status === 404 ? 502 : upstream.status },
    );
  }

  const headers = new Headers();
  const contentType = upstream.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  return new Response(upstream.body, { status: upstream.status, headers });
}
