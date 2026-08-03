/**
 * The bench's own blind spots — measured, and shown (spec §3 A, §A1.7, §A1.8).
 *
 * Showing the holes in your own benchmark is the most complete form of the honesty doctrine, and
 * everything here is DERIVED from artefacts already committed: the case definitions and the null
 * baseline. Nothing new is computed, and nothing is guessed.
 *
 * Three findings, and each of them changes how a number on this screen should be read.
 */
import type { Criterion } from "@/lib/eval-criteria";
import type { CaseKey } from "@/lib/eval-score";

/**
 * Would an EMPTY response pass this case? (§A1.8 — the finding under the 70% floor.)
 *
 * The null control passes 122 of 174 runs with no model at all, and this is why: the criteria are
 * mostly NEGATIVE. The guard refuses, the IBAN is not in the refusal, ✅. **A system that does
 * nothing satisfies them all** — silence is indistinguishable from competence, and a case that
 * cannot tell the two apart cannot grade a model.
 *
 * Reasoned against the harness's real behaviour on an empty run (`final_response=""`,
 * `needs_escalation=False`, no tool call, no confidence, no citation), criterion by criterion —
 * not against the shape of the key. `max_confidence` is the one that catches people out: with no
 * confidence recorded, `conf is not None and conf > max` is False, so the bound is NOT exceeded and
 * silence passes it. `min_confidence` is the mirror image and silence FAILS it.
 *
 * A case declaring NO criterion at all is passed by silence too — vacuously, and it is the weakest
 * case of all.
 */
export function passedBySilence(criteria: Criterion[]): boolean {
  return criteria.every((c) => {
    switch (c.kind) {
      // Nothing emitted, so nothing forbidden was emitted.
      case "must_not_contain":
        return true;
      // Nothing said, so nothing was asserted. Same shape as the line above, and it belongs
      // in this count for the same reason: a criterion silence satisfies is one the null
      // floor collects for free.
      case "must_not_assert":
        return true;
      // Nothing invoked, so nothing forbidden was invoked.
      case "must_not_invoke_tools":
        return true;
      // Silence fails this only if a pattern matches the EMPTY string (`.*` and friends).
      case "must_not_match":
        return c.values.every((pattern) => {
          try {
            return !new RegExp(pattern).test("");
          } catch {
            return true; // unreadable here — assume silence does not trip it
          }
        });
      // An empty run escalates nothing: it satisfies `must_escalate: false` and fails `true`.
      case "must_escalate":
        return c.scalar === false;
      // No confidence recorded → the upper bound is not exceeded (the harness's own arithmetic).
      case "max_confidence":
        return true;
      case "must_cite_source":
        return c.scalar !== true;
      // These are the criteria a refusal cannot satisfy. They are what a strong case is made of.
      case "must_contain_any":
      case "must_invoke_tools":
      case "min_confidence":
        return false;
      default:
        return false;
    }
  });
}

export type CasePower =
  /** The guard passes every run of this case with no model at all. It grades a model on NOTHING. */
  | "floor"
  /** The floor fails at least one of its runs — the only kind of case a model can prove itself on. */
  | "model-dependent"
  /** Not in the committed baseline. Never guessed. */
  | "unknown";

/**
 * What a case can tell you about a MODEL, read off the committed floor (§A1.7).
 *
 * > A case the guard holds on its own has ZERO discriminating power on the model. Say it.
 *
 * Measured on this catalogue: `policy_violation` (15/15) and `escalation_failure` (6/6) sit
 * entirely at the floor — neither category can grade a model, and that comes straight out of the
 * baseline with no new computation.
 */
export function casePower(
  caseId: string,
  floorVerdicts: Readonly<Record<CaseKey, boolean>> | null,
): CasePower {
  if (!floorVerdicts) return "unknown";
  const prefix = `${caseId}|`;
  let seen = false;
  let allPassed = true;
  for (const [key, ok] of Object.entries(floorVerdicts)) {
    if (!key.startsWith(prefix)) continue;
    seen = true;
    if (!ok) allPassed = false;
  }
  if (!seen) return "unknown";
  return allPassed ? "floor" : "model-dependent";
}

/**
 * Can a case even NAME a capability it covers?
 *
 * The spec asks for a coverage map — cases × the AgentSpecs' declared capabilities — so that a
 * capability with no case shows honest-empty. Measured before building it: **not one of the 63
 * cases references a single declared capability**, and the reason is structural rather than
 * accidental. `eval/failures/_schema.json` sets `additionalProperties: false` and declares no field
 * through which a case could name one. The coverage is therefore not *empty*; it is
 * **inexpressible**, and a map drawn over a join that does not exist would read complete while
 * being invented — the exact failure this screen exists to refuse.
 *
 * So the surface states the gap instead of drawing the map, and this function is what keeps the
 * statement true: the day the dataset gains such a field (a governed change — the UI can reveal the
 * hole, it cannot fill it), this returns true, the test pinning it fails, and the map becomes
 * buildable on a real key.
 */
const CAPABILITY_FIELDS = ["capabilities", "covers_capabilities", "capability_ids", "covers"];

export function coverageIsExpressible(caseSchemaFields: readonly string[]): boolean {
  return caseSchemaFields.some((field) => CAPABILITY_FIELDS.includes(field));
}
