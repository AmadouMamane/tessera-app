/**
 * A sparkline for a business signal's `trend.points` — P3 item 19.
 *
 * DELIBERATELY NOT MOUNTED ANYWHERE. Shipped ready, wired by nobody, on the architect's
 * standing instruction ("sparkline livré NON branché"). It renders only what it is handed:
 * points whose `value_pct` is null are gaps in the line, never interpolated, never carried
 * forward from the previous day. `<2` real points render nothing at all — a two-pixel line
 * through one dot is decoration pretending to be a trend.
 *
 * Fact worth having in the open when the wiring decision is taken: the history it needs
 * already exists and is real. `business_capabilities._signal_trend` buckets actual event rows
 * by day and aggregates a genuine score per bucket, marking days with no applicable rows
 * `not_applicable` / `value_pct: null`. Wiring this component to `signal.trend.points`,
 * gated on `trend.available`, would therefore fabricate nothing. That is the architect's call
 * to make, not this component's.
 */
import type { BusinessTrendPoint } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

export interface SparklineProps {
  points: BusinessTrendPoint[];
  /** Accessible description; a sparkline with no name is noise to a screen reader. */
  label: string;
  className?: string;
  width?: number;
  height?: number;
}

/** Real, plottable points — a `null` value is an absence, not a zero. */
export function plottablePoints(points: BusinessTrendPoint[]): { x: number; y: number }[] {
  const plotted: { x: number; y: number }[] = [];
  points.forEach((point, index) => {
    if (typeof point.value_pct === "number") plotted.push({ x: index, y: point.value_pct });
  });
  return plotted;
}

export function Sparkline({ points, label, className, width = 64, height = 18 }: SparklineProps) {
  const plotted = plottablePoints(points);
  // One point is not a trend, and zero points are not a flat line at zero.
  if (plotted.length < 2 || points.length < 2) return null;

  const xs = points.length - 1;
  const ys = plotted.map((p) => p.y);
  const min = Math.min(...ys);
  const max = Math.max(...ys);
  const span = max - min || 1;

  const project = (p: { x: number; y: number }) => {
    const x = (p.x / xs) * (width - 2) + 1;
    const y = height - 1 - ((p.y - min) / span) * (height - 2);
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  };

  // Consecutive runs only: a gap (null day) breaks the polyline instead of bridging it.
  const segments: string[] = [];
  let run: { x: number; y: number }[] = [];
  points.forEach((point, index) => {
    if (typeof point.value_pct === "number") {
      run.push({ x: index, y: point.value_pct });
      return;
    }
    if (run.length > 1) segments.push(run.map(project).join(" "));
    run = [];
  });
  if (run.length > 1) segments.push(run.map(project).join(" "));
  if (segments.length === 0) return null;

  const last = plotted[plotted.length - 1];

  return (
    <svg
      role="img"
      aria-label={label}
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      className={cn("overflow-visible", className)}
    >
      <title>{label}</title>
      {segments.map((pointsAttr) => (
        <polyline
          key={pointsAttr}
          points={pointsAttr}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.25"
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity={0.85}
        />
      ))}
      {last ? (
        <circle
          cx={project(last).split(",")[0]}
          cy={project(last).split(",")[1]}
          r="1.6"
          fill="currentColor"
        />
      ) : null}
    </svg>
  );
}
