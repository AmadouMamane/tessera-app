/**
 * How far the TRUE rate can plausibly sit from the one on screen — in percentage points.
 *
 * A rate published without its uncertainty invites the reader to compare 92 % to a 95 %
 * target as if both were exact; on 67 judged responses that comparison is noise wearing a
 * verdict. The cockpit already refuses to publish a rate at all under `MIN_N_FOR_A_RATE`
 * (a count cannot be misread); this module is the next step of the same doctrine — a result
 * carries its power ([[null-result-carries-its-power]]): above the floor, the rate leads
 * AND says how much one more observation could move it.
 *
 * The interval is Wilson's (95 % by default), not the naive ±z·√(p(1−p)/n): the naive form
 * collapses to ±0 at p = 0 or 1 — maximal confidence exactly where a small sample knows the
 * least — and can cross 0 % or 100 %. Wilson stays inside [0, 1] and stays honest at the
 * edges. The returned margin is the LARGER of the two half-widths around the displayed rate
 * (Wilson is asymmetric; quoting the smaller side would overstate the certainty).
 *
 * Returns `null` when no margin can be computed — never 0, which would claim exactness.
 */
export function rateMarginPts(successes: number, n: number, z = 1.96): number | null {
  if (!Number.isFinite(successes) || !Number.isFinite(n)) return null;
  if (n <= 0 || successes < 0 || successes > n) return null;
  const p = successes / n;
  const z2 = z * z;
  const denom = 1 + z2 / n;
  const center = (p + z2 / (2 * n)) / denom;
  const half = (z / denom) * Math.sqrt((p * (1 - p)) / n + z2 / (4 * n * n));
  const low = Math.max(0, center - half);
  const high = Math.min(1, center + half);
  return Math.max(p - low, high - p) * 100;
}
