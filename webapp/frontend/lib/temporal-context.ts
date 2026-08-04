/**
 * Shared cockpit temporal context (ADR 0011).
 *
 * The overview's time rail owns the focused instant T and the period, but the
 * topbar (a sibling outside the dashboard tree) needs them too — so an evidence
 * pack or exported report is scoped to `(period, asOf)` rather than always
 * snapshotting "now". This is a tiny in-memory singleton: the dashboard writes
 * it as the rail moves, the topbar reads it at click time. It is ephemeral on
 * purpose (no persistence) — a fresh page load is live.
 */

export interface TemporalContext {
  /** ISO instant T being viewed, or null when live (now). */
  asOf: string | null;
  /** Active window key: "h24" | "d7" | "d14" | "d30". */
  period: string;
}

let current: TemporalContext = { asOf: null, period: "d7" };

/** Read the current cockpit temporal context (SSR-safe; defaults to live). */
export function getTemporalContext(): TemporalContext {
  return current;
}

/** Set the current cockpit temporal context (called by the overview rail). */
export function setTemporalContext(ctx: TemporalContext): void {
  current = ctx;
}
