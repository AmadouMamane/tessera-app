/**
 * The page's own question, answered once: **can anything go live, and can I know?**
 *
 * `/surveiller/qualite-ia` is called Qualité IA and its second door is called "Évaluations avant
 * mise en ligne", yet nothing on it stated the verdict that actually decides a release. The four
 * facts that do — the eval gate, the null floor (ADR 0021 Rule 1), the observability level
 * required versus reached, and the phrase that names the block — were served, publicly, and the
 * page never read them.
 *
 * This module turns the per-agent decisions into ONE verdict for the page. It is pure so the
 * arithmetic is testable without a server, and it is deliberately conservative in three ways:
 *
 *  · **A blind level is not a low level.** `observability_level_unreadable` means the
 *    business-event store did not answer; it refuses the release like any other block, but it is
 *    counted and named apart, because the fix is "repair the read", not "emit more events".
 *  · **Not evaluated is not blocked.** An agent with no run has nothing to contradict; folding
 *    it into "blocked" would inflate a failure count with silence.
 *  · **The worst block wins the ribbon, and the ribbon says how many share it.** A page-level
 *    banner that averages severities tells the operator nothing to do.
 */

/** The decision as `/observability/release-control` serves it, narrowed to what a verdict needs. */
export interface AgentDecision {
  agentId: string;
  name: string;
  allowed: boolean;
  hasRun: boolean;
  blockedBy: string | null;
  observabilityLevel: string | null;
  requiredLevel: string | null;
  floorRegressions: string[];
}

/**
 * Why a release is refused. These are the backend's own constants
 * (`tessera.observability.agent_lifecycle`), mirrored as a union so a value the front does not
 * know cannot silently become one it does — an unrecognised cause lands in `unknown`, which
 * renders as "blocked, cause not recognised" rather than being attributed to the eval gate.
 */
export type BlockCause =
  | "eval_gate"
  | "null_floor"
  | "observability_level"
  | "observability_level_unreadable"
  | "unknown";

const KNOWN_CAUSES = new Set<BlockCause>([
  "eval_gate",
  "null_floor",
  "observability_level",
  "observability_level_unreadable",
]);

export function asBlockCause(raw: string | null): BlockCause {
  return raw !== null && KNOWN_CAUSES.has(raw as BlockCause) ? (raw as BlockCause) : "unknown";
}

/**
 * How loudly each cause must read.
 *
 * `null_floor` outranks everything: the model made the agent WORSE than running with no model
 * at all, which is the one result that cannot be traded against any score. The unreadable level
 * ranks below the measured ones on purpose — it is a hole in our instruments, not a fault
 * proven in the agent, and printing it as loudly as a certified regression would teach the
 * operator to distrust the loud colour.
 */
const CAUSE_RANK: Record<BlockCause, number> = {
  null_floor: 4,
  eval_gate: 3,
  observability_level: 2,
  observability_level_unreadable: 1,
  unknown: 0,
};

export interface ReleaseVerdict {
  /** Total agents the payload described — the denominator of every count below. */
  total: number;
  /** Agents the gate clears. */
  releasable: number;
  /** Agents a condition refuses, by cause. Never merged: four causes, four kinds of work. */
  blocked: Array<{ cause: BlockCause; agents: AgentDecision[] }>;
  /** Agents with no run at all. Not blocked — nothing has been asked of them yet. */
  notEvaluated: AgentDecision[];
  /** The loudest cause present, or `null` when nothing is blocked. */
  worst: BlockCause | null;
  /**
   * `true` when at least one agent's level could not be READ. The verdict is then partly
   * unknowable, and the ribbon must say so even while reporting the blocks it can see: a
   * witness that cannot see may not report "ok" (ADR 0026).
   */
  hasBlindSpot: boolean;
  severity: "critical" | "warning" | "ok" | "info";
}

/** Fold the per-agent decisions into the page's one verdict. */
export function summarizeRelease(agents: AgentDecision[]): ReleaseVerdict {
  const releasable = agents.filter((a) => a.allowed);
  // An agent with no run is neither cleared nor refused — it has not been asked.
  const notEvaluated = agents.filter((a) => !a.allowed && !a.hasRun);
  const refused = agents.filter((a) => !a.allowed && a.hasRun);

  const byCause = new Map<BlockCause, AgentDecision[]>();
  for (const agent of refused) {
    const cause = asBlockCause(agent.blockedBy);
    const bucket = byCause.get(cause);
    if (bucket) bucket.push(agent);
    else byCause.set(cause, [agent]);
  }

  const blocked = [...byCause.entries()]
    .map(([cause, list]) => ({ cause, agents: list }))
    .sort((a, b) => CAUSE_RANK[b.cause] - CAUSE_RANK[a.cause]);

  const worst = blocked[0]?.cause ?? null;
  const hasBlindSpot = byCause.has("observability_level_unreadable");

  // `info` rather than `ok` when nothing is blocked but something was never evaluated: a page
  // that paints "all clear" over agents nobody has run is describing its own silence.
  const severity: ReleaseVerdict["severity"] =
    worst === "null_floor" || worst === "eval_gate"
      ? "critical"
      : worst !== null
        ? "warning"
        : notEvaluated.length > 0
          ? "info"
          : "ok";

  return {
    total: agents.length,
    releasable: releasable.length,
    blocked,
    notEvaluated,
    worst,
    hasBlindSpot,
    severity,
  };
}

/**
 * Agents whose LEVEL is the whole story: required versus reached, side by side.
 *
 * `/observability/fleet` publishes the reached level and no requirement, so a reader there sees
 * "L0" with nothing to compare it to. Only this payload carries both, and only when they differ
 * is there anything to say.
 */
export function levelShortfalls(
  agents: AgentDecision[],
): Array<{ agentId: string; name: string; reached: string | null; required: string }> {
  return agents
    .filter((a) => a.requiredLevel !== null && a.observabilityLevel !== a.requiredLevel)
    .map((a) => ({
      agentId: a.agentId,
      name: a.name,
      reached: a.observabilityLevel,
      required: a.requiredLevel as string,
    }));
}
