import { z } from "zod";

import type { PillarSignal } from "@/lib/launcher-pillars";

/**
 * Client-side fetch of the public launcher signal (`/api/launcher-signal`),
 * validated like every other response in this app. The schema declares exactly
 * the structural subset the band consumes (`PillarSignal`) — zod strips the
 * rest — so the parsed value needs no cast. `null` on any failure: the band
 * then keeps its last honest state and lets the freshness stamp age visibly.
 */
const PillarSignalWireSchema = z.object({
  agentsCount: z.number().int().nonnegative(),
  passedAgents: z.number().int().nonnegative(),
  agentsWithRelease: z.number().int().nonnegative(),
  agents: z.array(z.object({ verdictStale: z.boolean() })),
  integrityVerified: z.boolean().nullable(),
  opposabilityBadge: z
    .enum(["non_scelle", "scelle_opposable", "scelle_non_qualifie", "integrite_partielle"])
    .nullable(),
  guardActivity: z
    .object({
      checkedToday: z.number().int().nonnegative(),
      blockedToday: z.number().int().nonnegative(),
    })
    .nullable(),
});

export async function fetchLauncherSignal(): Promise<PillarSignal | null> {
  try {
    const res = await fetch("/api/launcher-signal", { cache: "no-store" });
    if (!res.ok) return null;
    const parsed = PillarSignalWireSchema.safeParse(await res.json());
    return parsed.success ? parsed.data : null;
  } catch {
    return null;
  }
}
