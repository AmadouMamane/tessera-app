import { NextResponse } from "next/server";

/**
 * Build/version stamp of THIS frontend image — the anti-divergence witness (ADR 0048).
 *
 * Returns the commit SHA baked into the image at build time (`ARG TESSERA_BUILD_SHA` in
 * Dockerfile.frontend), its build time, and the deployment target label. `make deploy-diff`
 * fetches this from every target's live host (onprem.<domain> / gcp.<domain>) and refuses when
 * the SHAs differ — divergence becomes a machine verdict, not a hope.
 *
 * Public and aggregate by design (same posture as the launcher signal, ADR 0009): a build SHA, a
 * build time, a target label. No subject data, no secret. An un-stamped local build reports
 * `sha: "dev"`, which deploy-diff treats as a divergence against a real SHA, never a match.
 */
export const dynamic = "force-dynamic";

export function GET(): NextResponse {
  return NextResponse.json({
    sha: process.env.TESSERA_BUILD_SHA ?? "dev",
    builtAt: process.env.TESSERA_BUILD_TIME ?? "unknown",
    target: process.env.TESSERA_TARGET ?? "unknown",
  });
}
