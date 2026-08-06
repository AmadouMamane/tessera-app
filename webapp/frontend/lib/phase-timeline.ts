import type { ComponentPhase } from "@/lib/api/schemas";

/**
 * Pure geometry for the component-history timeline (ADR 0052 §Amendment 1.2).
 *
 * The whole point of drawing phases instead of a percentage is that a hole in the record stays
 * VISIBLE: everything this module does not cover with a segment is time nobody watched, and the
 * renderer shows it as the empty track — never stretched, never interpolated. The math lives
 * here, testable without a browser, because a timeline that silently mis-places a fail by an
 * hour is worse than the totals it replaces.
 */
export interface TimelineSegment {
  verdict: string;
  /** Left edge, as a share of the window (0..100). */
  leftPct: number;
  /** Width, as a share of the window (0..100). Zero for a single observation — the renderer
   * gives it a minimum ink width, because one real look must not be invisible. */
  widthPct: number;
  since: string;
  until: string;
  seconds: number;
  n_observations: number;
}

const ms = (iso: string): number | null => {
  const t = Date.parse(iso);
  return Number.isNaN(t) ? null : t;
};

const clampPct = (n: number): number => Math.min(100, Math.max(0, n));

/**
 * Project one component's phases onto a window, as percentage segments.
 *
 * Assumes the backend already clipped phases to the window (`clipped_phases`), but clamps
 * anyway: a segment leaking past 100 % would paint watched time over unwatched time, which is
 * the exact over-claim the surface exists to refuse. Unparseable instants drop the phase — a
 * bar drawn at a guessed position is worse than a narrower record.
 */
export function segmentsFor(
  phases: ComponentPhase[],
  component: string,
  windowSince: string,
  windowUntil: string,
): TimelineSegment[] {
  const since = ms(windowSince);
  const until = ms(windowUntil);
  if (since === null || until === null || until <= since) return [];
  const span = until - since;

  const own = phases.filter((phase) => phase.component === component);
  const segments: TimelineSegment[] = [];
  for (const phase of own) {
    const start = ms(phase.since);
    const stop = ms(phase.until);
    if (start === null || stop === null || stop < start) continue;
    const leftPct = clampPct(((start - since) / span) * 100);
    const rightPct = clampPct(((stop - since) / span) * 100);
    segments.push({
      verdict: phase.verdict,
      leftPct,
      widthPct: Math.max(0, rightPct - leftPct),
      since: phase.since,
      until: phase.until,
      seconds: Math.max(0, (stop - start) / 1000),
      n_observations: phase.n_observations,
    });
  }
  segments.sort((a, b) => a.leftPct - b.leftPct);
  return segments;
}

/** Every component that has at least one drawable phase, in draw order. */
export function componentsInTimeline(phases: ComponentPhase[]): string[] {
  const seen: string[] = [];
  for (const phase of phases) {
    if (!seen.includes(phase.component)) seen.push(phase.component);
  }
  return seen.sort((a, b) => a.localeCompare(b));
}
