import { EVAL_VIEW_PARAM } from "@/components/eval/eval-route";

/**
 * The URL contract of `/surveiller/qualite-ia` — one page, two tab strips, two parameters.
 *
 * The page holds two independent strips: the monitoring dashboard's six tabs, and `EvalTabs`
 * (`cases | runs | compare`) on the evaluations view. **Both wrote `?tab=`.** Their vocabularies
 * are disjoint but not disjoint enough: `runs` belongs to both, so `?tab=runs` named two
 * different screens depending on `?vue=`, and a URL an operator sent to a colleague could not be
 * resolved by reading it.
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

/** The monitoring dashboard's tabs, in the order the strip renders them. */
export const DASHBOARD_TABS = ["overview", "signals", "runs", "failed", "models", "judge"] as const;

export type DashboardTab = (typeof DASHBOARD_TABS)[number];
