/**
 * The focused signal (`?signal=`) — which signal the page's per-agent table must answer.
 *
 * The breakdown lens is driven by the alarm by default (the SLO hero). Selecting a row in the
 * signal registry focuses THAT signal, and the table either answers it or says why it cannot:
 * an org-wide signal (no AGENT dimension in `capabilities.py`) gets no per-agent table at all.
 *
 * Pure module (no React) so the server page and the client registry read the same key, and the
 * UI-row keys that differ from their registry id are mapped in ONE place.
 */

export const SIGNAL_FOCUS_PARAM = "signal";

/**
 * UI row keys whose capability-registry id is spelled differently.
 *
 * Two spellings for one signal is a small cost paid in ONE place. The alternative — letting a
 * component call `capabilityFor("refusalOver")` and silently get `undefined`, which
 * `signalSupports` turns into `false` — is how a filter affordance disappears without anyone
 * noticing that the registry was never asked about the right thing.
 *
 * `crossTenant` / `leastPrivilege` / `embeddingInversion` are control VIEWS of signals already
 * declared under their own names; they map onto those rather than minting new ids.
 */
const REGISTRY_ID: Record<string, string> = {
  piiLeak: "pii_leak",
  errorBudget: "error_budget",
  refusalOver: "refusal_over",
  refusalUnder: "refusal_under",
  injectionBypass: "injection_bypass",
  crossTenant: "cross_tenant",
  leastPrivilege: "least_privilege",
  embeddingInversion: "embedding_inversion",
};

/** The capability-registry id for a signal row's UI key. */
export function registryIdFor(uiKey: string): string {
  return REGISTRY_ID[uiKey] ?? uiKey;
}

/** The focused signal id from a URL param, or `undefined` (⇒ the alarm drives the table). */
export function readSignalFocus(
  params: URLSearchParams | Record<string, string | string[] | undefined>,
): string | undefined {
  const raw =
    params instanceof URLSearchParams ? params.get(SIGNAL_FOCUS_PARAM) : params[SIGNAL_FOCUS_PARAM];
  const value = Array.isArray(raw) ? raw[0] : raw;
  const trimmed = value?.trim();
  return trimmed ? trimmed : undefined;
}
