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

/** UI row keys whose capability-registry id is spelled differently. */
const REGISTRY_ID: Record<string, string> = { piiLeak: "pii_leak" };

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
