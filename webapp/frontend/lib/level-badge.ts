/**
 * Which observability badge a fleet card shows (ADR 0017 §4).
 *
 * The cockpit knows two rungs: `level` is COMPUTED from observed turns, `level_declared` is
 * what the manifest's declarations would reach if that evidence existed. They are equal
 * exactly when `level_evidence` is `"observed"`.
 *
 * When they differ, the badge must render the DECLARED rung in a muted variant that names it
 * as declared — never dress it up as a computed one. `turn-agent` made the bug visible: it
 * declares an observable contract, emits nothing, and used to display a plain "L1".
 *
 * Pure and agent-agnostic on purpose: the gap is data computed server-side, so no card ever
 * needs a per-agent condition.
 */

export type LevelEvidence = "observed" | "dormant" | "unverifiable";

export interface LevelFacts {
  level?: string | null;
  level_declared?: string | null;
  level_evidence?: LevelEvidence;
}

export type LevelBadgeView =
  /** No manifest → honest-empty. The absence of a level is never rendered as "L0". */
  | { kind: "none" }
  /** The rung is backed by observed turns. */
  | { kind: "computed"; level: string }
  /** The manifest promises more than the facts prove; `evidence` says whose silence it is. */
  | { kind: "declared"; level: string; evidence: LevelEvidence };

export function levelBadgeView(facts: LevelFacts): LevelBadgeView {
  const computed = facts.level ?? null;
  const declared = facts.level_declared ?? null;

  if (declared && declared !== computed) {
    // `unverifiable` is the safe default: an older payload without `level_evidence` cannot
    // tell us the agent is dormant, and blaming a live agent for a silent store would be a
    // different lie from the one we are fixing.
    return { kind: "declared", level: declared, evidence: facts.level_evidence ?? "unverifiable" };
  }
  if (computed) return { kind: "computed", level: computed };
  return { kind: "none" };
}
