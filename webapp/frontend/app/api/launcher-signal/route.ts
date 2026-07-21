import { NextResponse } from "next/server";

import { loadLauncherSignal } from "@/lib/server/launcher-signal";

/**
 * Public-safe launcher signal (ADR 0009) for the band's client polling.
 *
 * Anonymous BY DESIGN: it serves exactly the aggregate the public
 * server-rendered launcher already displays — fleet size, gate rollup,
 * guard-activity counters, integrity verdict — never operator-gated detail.
 * The band's "temps réel" claim is witnessed by a fresh fetch of this route,
 * not asserted; the backend reads behind it are TTL-cached, so an anonymous
 * visitor cannot turn polling into a ledger-scan amplifier.
 */
export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse> {
  return NextResponse.json(await loadLauncherSignal());
}
