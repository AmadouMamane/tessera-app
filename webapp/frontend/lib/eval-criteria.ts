/**
 * The pass criteria of a case, enumerated — pure, and shared by the two places that must say the
 * same thing about them: the case sheet in `Jeu de cas` (what the bench DEMANDS) and the executed
 * case in `Exécutions` (what the model DID about it).
 *
 * Mirror of `eval/failures/_schema.json` and of the three checkers in `eval/runner.py`
 * (`_check_substrings`, `_check_tools`, `_check_signals`). Enumerating them in one place is what
 * keeps the two surfaces from drifting into two different descriptions of the same rule.
 *
 * `verifiability` is the load-bearing field, and it is not cosmetic. A run's report keeps the
 * final response, the escalation flag and the tools — but NOT the confidence, NOT the retrieved
 * citations, and NOT whether each tool call actually SUCCEEDED. The harness evaluates
 * `must_not_invoke_tools` against the calls that succeeded (`if call.succeeded`), while the report
 * stores every attempted call. So a dashboard recomputing that criterion from the report would
 * announce "forbidden tool invoked" about a call the GUARD DENIED — a verdict the harness never
 * reached, rendered as if it had. Those criteria are therefore reported, never recomputed.
 */
import type { EvalPassCriteria } from "@/lib/api/schemas";

export type CriterionKind =
  | "must_not_contain"
  | "must_contain_any"
  | "must_not_match"
  | "must_escalate"
  | "min_confidence"
  | "max_confidence"
  | "must_cite_source"
  | "must_not_invoke_tools"
  | "must_invoke_tools";

export type Verifiability =
  /** A pure function of what the report stores (`final_response`, `needs_escalation`). The UI can
   *  recompute the verdict and point at the exact substring that decided it. */
  | "recomputable"
  /** The harness checked it against state the report does not keep (the confidence, the retrieved
   *  citations, the per-call success flag). Its reason is DISPLAYED as the harness wrote it, and
   *  never recomputed — a reconstruction that cannot see the same inputs is not evidence. */
  | "reported-only";

export interface Criterion {
  kind: CriterionKind;
  /** Substrings, regexes or tool names — whatever the criterion is expressed over. */
  values: string[];
  /** For `must_escalate` (true/false) and the confidence bounds (a number). */
  scalar: boolean | number | null;
  verifiability: Verifiability;
  /** A criterion an EMPTY response satisfies. §A1.8: silence is indistinguishable from competence. */
  negative: boolean;
}

const RECOMPUTABLE = new Set<CriterionKind>([
  "must_not_contain",
  "must_contain_any",
  "must_not_match",
  "must_escalate",
]);

/** Criteria a system that DOES NOTHING satisfies. They are why the null floor reaches 70%. */
const NEGATIVE = new Set<CriterionKind>([
  "must_not_contain",
  "must_not_match",
  "must_not_invoke_tools",
]);

function make(kind: CriterionKind, values: string[], scalar: boolean | number | null): Criterion {
  return {
    kind,
    values,
    scalar,
    verifiability: RECOMPUTABLE.has(kind) ? "recomputable" : "reported-only",
    negative: NEGATIVE.has(kind),
  };
}

/**
 * Every criterion a case declares, in the order the harness checks them.
 *
 * An absent criterion is absent — it is never rendered as an empty rule. A case with no criteria
 * at all yields an empty list, and the surface says so rather than implying the case is unchecked
 * because the UI failed to read it.
 */
export function listCriteria(pc: EvalPassCriteria | undefined | null): Criterion[] {
  if (!pc) return [];
  const out: Criterion[] = [];
  if (pc.must_not_contain?.length) out.push(make("must_not_contain", pc.must_not_contain, null));
  if (pc.must_contain_any?.length) out.push(make("must_contain_any", pc.must_contain_any, null));
  if (pc.must_not_match?.length) out.push(make("must_not_match", pc.must_not_match, null));
  if (pc.must_not_invoke_tools?.length) {
    out.push(make("must_not_invoke_tools", pc.must_not_invoke_tools, null));
  }
  if (pc.must_invoke_tools?.length) out.push(make("must_invoke_tools", pc.must_invoke_tools, null));
  if (pc.must_escalate !== undefined) out.push(make("must_escalate", [], pc.must_escalate));
  if (pc.min_confidence !== undefined) out.push(make("min_confidence", [], pc.min_confidence));
  if (pc.max_confidence !== undefined) out.push(make("max_confidence", [], pc.max_confidence));
  if (pc.must_cite_source !== undefined) {
    out.push(make("must_cite_source", [], pc.must_cite_source));
  }
  return out;
}
