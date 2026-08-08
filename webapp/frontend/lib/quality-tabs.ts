import { EVAL_VIEW_PARAM } from "@/components/eval/eval-route";

/**
 * The URL contract of `/surveiller/qualite-ia` — one page, two tab strips, two parameters.
 *
 * The page holds two independent strips: the monitoring dashboard's tabs, and `EvalTabs` on the
 * evaluations view. **Both wrote `?tab=`.** Their vocabularies were disjoint but not disjoint
 * enough: `runs` belonged to both, so `?tab=runs` named two different screens depending on
 * `?vue=`, and a URL an operator sent to a colleague could not be resolved by reading it.
 *
 * The dashboard's side was renamed, for two measured reasons rather than a preference: nothing
 * in the repository linked to `?tab=runs|failed|models|judge`, and the evaluations strip is the
 * one that GROWS as the boundary migration moves the eval-shaped tabs across — the surviving
 * plain name should be the one that ends up carrying most of the page.
 *
 * Declared here rather than inline in the dashboard so the separation is a fact a test can read
 * without importing a 1300-line client component.
 */
export const DASHBOARD_TAB_PARAM = "onglet";

/** The evaluations strip's parameter, unchanged. */
export const EVAL_TAB_PARAM = "tab";

/** The parameter that chooses WHICH of the two views is open. Neither strip may reuse it. */
export const QUALITY_VIEW_PARAM = EVAL_VIEW_PARAM;

/**
 * The monitoring dashboard's tabs — what is left of it after the boundary migration.
 *
 * It used to hold six. Four of them (`runs`, `failed`, `models`, `judge`) read the EVAL REPORT
 * ARCHIVE and the judge's gold set: not one of them samples a live turn, and every one of them
 * answers "should this go live", which is the other view's whole question. They now live there
 * ({@link CROSSED_TARGETS}). What remains is what the page's own name promises: signals sampled
 * from production, and the overview that summarises them.
 */
export const DASHBOARD_TABS = ["overview", "signals"] as const;

export type DashboardTab = (typeof DASHBOARD_TABS)[number];

/**
 * Drill-down destinations that used to be dashboard tabs and are now evaluations-view tabs.
 *
 * The overview's cards, the right rail and the signal rail all offer "see the failed cases",
 * "see the model comparison", "see the runs". Those sentences stay true — the content moved, it
 * did not disappear — so the links must follow it across the boundary instead of pointing at a
 * tab that no longer exists. Mapping them here (rather than editing ~15 call sites in three
 * 1000-line files) keeps every existing `onOpen("failed")` working and makes the crossing a
 * single fact one test can read.
 *
 * The key is the OLD dashboard name, because that is what the call sites still say; the value
 * is the evaluations tab it resolves to. `runs` → `archive` is the one rename: the evaluations
 * strip already had a `runs`, and it is a different population (see `eval-tabs.tsx`).
 */
export const CROSSED_TARGETS = {
  runs: "archive",
  failed: "failed",
  models: "models",
  judge: "judge",
} as const;

export type CrossedTarget = keyof typeof CROSSED_TARGETS;

/**
 * Every destination a quality-page drill-down may name: the two that stay local, and the four
 * that now cross. Kept as one union because the call sites do not know — and should not need to
 * know — which side of the boundary their target ended up on.
 */
export type QualityTarget = DashboardTab | CrossedTarget;

/** Does this destination still live in the dashboard, or has it crossed to the other view? */
export function isDashboardTab(target: QualityTarget): target is DashboardTab {
  return (DASHBOARD_TABS as readonly string[]).includes(target);
}
