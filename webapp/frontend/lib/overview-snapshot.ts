/**
 * Selecting one signal out of the batched snapshot (ADR 0015 §Performance).
 *
 * `GET /observability/snapshot` returns every hot-path signal for one scope in a single
 * backend pass that shares its upstream reads. It has existed, cached and single-flighted,
 * since the spine migration — and the cockpit never called it, firing one request per card
 * instead. This module is the client half: one query, each card `select`s its slice.
 *
 * Two properties this file exists to preserve, because collapsing requests is worthless if
 * either is lost:
 *
 * 1. **No new truth.** A slice is validated with the *same* zod schema the card's own route
 *    used. The backend already pins `snapshot.signals[id].data` byte-identical to that route
 *    (`tests/unit/test_spine_signals_parity.py`); this keeps the client honest about it too.
 * 2. **Honest-empty, field by field.** A signal the backend could not compute comes back
 *    absent, and absent stays `undefined` here — never `{}`, never a zero. One unavailable
 *    store degrades one card, exactly as it does today, and never blanks the page.
 */

import type { z } from "zod";

/** The signal ids the backend's snapshot set actually carries (`snapshot_signal_ids()`). */
export const SNAPSHOT_SIGNALS = [
  "scores",
  "slo",
  "trend",
  "funnel",
  "gating",
  "toxicity",
  "pii_leak",
  "cost",
  "anomalies",
  "what_changed",
] as const;

export type SnapshotSignalId = (typeof SNAPSHOT_SIGNALS)[number];

/** One signal as the snapshot carries it: the payload, plus which scope dimensions it honoured. */
export interface SnapshotEntry {
  data?: unknown;
  report?: unknown;
}

export interface OverviewSnapshot {
  scope?: unknown;
  signals?: Record<string, SnapshotEntry | undefined>;
  meta?: unknown;
}

/**
 * The slice for `id`, validated with the card's own schema — or `undefined` when the backend
 * had nothing to say.
 *
 * Absent signal, absent `data`, or a payload that fails the card's schema all yield
 * `undefined`. The last case matters: a snapshot that drifted from the route contract must
 * degrade the card to its honest-empty state rather than render a half-parsed object. The
 * backend parity test is what stops that from happening silently; this is the client's own
 * refusal to guess.
 */
export function selectSignal<TSchema extends z.ZodTypeAny>(
  snapshot: OverviewSnapshot | undefined,
  id: SnapshotSignalId,
  schema: TSchema,
): z.infer<TSchema> | undefined {
  const entry = snapshot?.signals?.[id];
  if (!entry || entry.data === undefined || entry.data === null) return undefined;
  const parsed = schema.safeParse(entry.data);
  return parsed.success ? parsed.data : undefined;
}
