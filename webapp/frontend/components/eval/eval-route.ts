/**
 * The eval screen's canonical home — ONE spelling, imported by every self-link.
 *
 * The screen lived at `/eval`, an orphan (zero inbound links; only its own tab strip pointed
 * at it). It now lives as the "Évaluations" view of `/surveiller/qualite-ia` — the page whose
 * sidebar entry and subtitle had been promising it all along — and `/eval` redirects here so
 * every deep link an operator ever sent keeps resolving.
 */
export const EVAL_PATHNAME = "/surveiller/qualite-ia";

/** The query param that selects the page's view. */
export const EVAL_VIEW_PARAM = "vue";

/** The value that opens the evaluations view (default is the monitoring dashboard). */
export const EVAL_VIEW_VALUE = "evaluations";

/** A query object for a link INTO the evaluations view, preserving the given params. */
export function evalQuery(query: Record<string, string> = {}): Record<string, string> {
  return { [EVAL_VIEW_PARAM]: EVAL_VIEW_VALUE, ...query };
}
