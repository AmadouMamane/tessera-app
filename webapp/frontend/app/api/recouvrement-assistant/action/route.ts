import { type NextRequest, NextResponse } from "next/server";

import { backendHeaders, backendUrl } from "@/lib/server/backend";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND_RECOUVREMENT_ASSISTANT_ACTION_PATH = "/recouvrement-assistant/action";
const BACKEND_UNAVAILABLE_DETAIL = "recouvrement assistant backend unavailable";

export async function POST(request: NextRequest): Promise<Response> {
  const body = await request.text();

  let upstream: Response;
  try {
    upstream = await fetch(`${backendUrl()}${BACKEND_RECOUVREMENT_ASSISTANT_ACTION_PATH}`, {
      method: "POST",
      headers: backendHeaders({
        "content-type": request.headers.get("content-type") ?? "application/json",
        Accept: "application/json",
      }),
      body,
      signal: request.signal,
    });
  } catch (err) {
    console.warn("[recouvrement-assistant] backend action request failed", err);
    return NextResponse.json({ detail: BACKEND_UNAVAILABLE_DETAIL }, { status: 502 });
  }

  if (!upstream.ok) {
    const detail = await upstream.text().catch(() => "");
    console.warn("[recouvrement-assistant] backend action rejected request", {
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
