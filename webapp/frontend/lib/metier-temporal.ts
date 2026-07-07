/**
 * BR-01 §5 — temporal mode for the AGENT / Métier surface (registre des rails v1.3).
 *
 * Métier reads honor the *global* as-of instant, but Métier is NOT a signal scrubber: the
 * signal-time navigation of business signals belongs to SURVEILLER (SR-01). The Métier KPI
 * band is a current-state read, not a rail. So Métier only reflects a posed as-of instant as
 * an "état à T" read (TE-01 / AGIR semantics): **Live by default, As-of when a global T is
 * posed**. The instant is derived from the URL (deep-link is the source of truth), never from
 * a private component state.
 *
 * The backend `/observability/business/{capabilities,runs}` endpoints already accept `at`.
 */

export type MetierTemporalMode = "live" | "asof";

export interface MetierTemporalParams {
  /** As-of instant T (ISO) from the URL when the reading is "as of a date". */
  asof: string | null;
  /** History scrub cursor (ISO) from the URL — also a posed point in time. */
  at: string | null;
}

/**
 * Resolve the posed as-of instant from URL params only (SSR-safe, deterministic). Returns
 * `null` when no instant is posed (= live). `asof` (explicit "voir à date") wins over the
 * history cursor `at`; both are ISO instants forwarded to the backend as `at`.
 */
export function resolveMetierAsOf(params: MetierTemporalParams): string | null {
  return params.asof || params.at || null;
}

/** The active temporal mode Métier displays for a resolved as-of instant. */
export function metierTemporalMode(asOf: string | null): MetierTemporalMode {
  return asOf ? "asof" : "live";
}
