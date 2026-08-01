import { NextResponse } from "next/server";

/**
 * Build/version stamp of this DEPLOYMENT — the anti-divergence witness (ADR 0048).
 *
 * `make deploy-diff` fetches this from every target's live host and refuses when the SHAs
 * differ, so divergence becomes a machine verdict rather than a hope. It reads exactly one
 * field, `sha`, which is why that field must not claim more than this route can see.
 *
 * A host is a PAIR — a frontend image and an agent image — and until 2026-08-02 only the
 * frontend was stamped. Reporting the frontend's SHA alone would have answered "is this the
 * code I think it is?" for half of what runs there: rebuild the front and forget the agent, and
 * two hosts would compare equal while serving different backends. That is worse than the
 * un-stamped state it replaces, because `sha: "dev"` at least made deploy-diff say *CannotSay*.
 *
 * So `sha` is the pair's identity, and it is equal to the frontend's SHA only when the agent
 * reports the same one. Any other case yields a value that cannot compare equal to a clean
 * stamp — `mixed:…` when the two disagree, `unverified:…` when the agent could not be asked.
 * Both halves stay visible in `frontend` / `agent` for whoever is reading rather than diffing.
 *
 * Public and aggregate by design (same posture as the launcher signal, ADR 0009): build SHAs, a
 * build time, a target label. No subject data, no secret.
 */
export const dynamic = "force-dynamic";

/** How long the agent gets to name its own code before this route gives up on it. */
const AGENT_TIMEOUT_MS = 1500;

/**
 * The commit the AGENT reports having loaded, or `null` when it cannot say.
 *
 * `/healthz` carries `code_sha` (frozen at import, ADR 0026) and `code_sha_source`. Only a
 * value stamped by a build — `source === "env"` — is usable here: a `git`-derived SHA comes
 * from a working tree that can move under a running process, and `unknown` is the honest
 * absence this function must pass through rather than paper over.
 */
async function agentSha(): Promise<string | null> {
  const base = process.env.TESSERA_BACKEND_URL;
  if (!base) return null;
  try {
    const response = await fetch(`${base}/healthz`, {
      signal: AbortSignal.timeout(AGENT_TIMEOUT_MS),
      cache: "no-store",
    });
    if (!response.ok) return null;
    const body = (await response.json()) as {
      code_sha?: unknown;
      code_sha_source?: unknown;
    };
    if (body.code_sha_source !== "env" || typeof body.code_sha !== "string") return null;
    return body.code_sha || null;
  } catch {
    // Unreachable, slow, or malformed: all of them mean "this route did not see the agent",
    // and the caller turns that into `unverified:` rather than into the frontend's own SHA.
    return null;
  }
}

export async function GET(): Promise<NextResponse> {
  const frontend = process.env.TESSERA_BUILD_SHA || "dev";
  const agent = await agentSha();
  const sha =
    agent === null
      ? frontend === "dev"
        ? "dev"
        : `unverified:${frontend}`
      : agent === frontend
        ? frontend
        : `mixed:${frontend}/${agent}`;

  return NextResponse.json({
    sha,
    frontend,
    agent,
    builtAt: process.env.TESSERA_BUILD_TIME ?? "unknown",
    target: process.env.TESSERA_TARGET ?? "unknown",
  });
}
