/**
 * A number nobody could read is not the number zero, and it is not a verdict.
 *
 * The shape this replaces is everywhere in the governance dashboards:
 *
 *     tone={(crossTenant.data?.n_leaks ?? 0) > 0 ? BAD : GOOD}
 *     value={`${crossTenant.data?.n_leaks ?? 0}`}
 *
 * When that query does not answer — 401, 403, backend down, contract drift — `data` is
 * `undefined`, `?? 0` makes it zero, zero is not greater than zero, and the security dashboard
 * prints a green **0 cross-tenant leaks**. The most reassuring sentence on the page is the one
 * emitted by knowing nothing at all. Ten tiles on that one screen did this, and the file-level
 * ratchet next door (`failed-read-is-not-an-empty-result`) could not see them: it clears a whole
 * file once ANY read-failure guard appears in it, and this file has one, four hundred lines away.
 *
 * `?? 0` is legitimate where zero is a fact about a COLLECTION the caller holds — `items.length
 * ?? 0`, a sparkline's first point, a filter predicate. It is never legitimate between a
 * possibly-absent read and a threshold. The distinction is what this module encodes: pass the
 * raw, possibly-null value and a predicate, and get back a third answer.
 *
 * ADR 0026: a witness that cannot see may never report "ok".
 */

/** The three things a governed number can be, once. */
export type Reading<T> = { bad: T; good: T; unread: T };

/**
 * Normalise "no reading" to a single value. `undefined` (query never answered), `null` (backend
 * said it could not compute) and `NaN` (a division by an empty window) are the same fact here:
 * nothing was measured.
 */
export function readNumber(value: number | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  return Number.isFinite(value) ? value : null;
}

/**
 * The tone a tile should wear, given a possibly-absent reading.
 *
 * `isBad` is only ever called with a real number, so call sites keep reading as the threshold
 * they mean — `(n) => n > 0`, `(r) => r >= 0.5` — with no null-handling smeared through them.
 */
export function toneFor<T>(
  value: number | null | undefined,
  isBad: (v: number) => boolean,
  tones: Reading<T>,
): T {
  const n = readNumber(value);
  if (n === null) return tones.unread;
  return isBad(n) ? tones.bad : tones.good;
}

/**
 * The figure itself. An em dash where there is no reading — never a fabricated `0`, which is
 * both a number and a claim.
 */
export function showNumber(
  value: number | null | undefined,
  format: (v: number) => string = (v) => String(v),
): string {
  const n = readNumber(value);
  return n === null ? "—" : format(n);
}

/** True when the tile is showing an absence rather than a measurement. */
export function isUnread(value: number | null | undefined): boolean {
  return readNumber(value) === null;
}
