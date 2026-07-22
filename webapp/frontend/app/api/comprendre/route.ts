import { NextResponse } from "next/server";

import { loadComprendreFacts } from "@/lib/server/comprendre";

/** Public BFF for the aggregate proof tiles; no subject-level fact crosses this boundary. */
export const dynamic = "force-dynamic";

export async function GET(): Promise<NextResponse> {
  return NextResponse.json(await loadComprendreFacts());
}
