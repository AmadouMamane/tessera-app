import { useTranslations } from "next-intl";

import { cn } from "@/lib/cn";
import type { OverviewTone } from "@/lib/overview";

/**
 * A control's curve. `null` is a HOLE, not a zero.
 *
 * The distinction is the whole reason this component takes `(number | null)[]` rather than
 * the `number[]` it started with. A bucket with no traffic and a bucket that measured zero
 * render as the same low point on a line, and on a leak rate they mean opposite things —
 * "nothing happened this week" versus "a week of clean answers". Joining across the hole
 * would also draw a slope through days nobody observed, which is a claim about those days.
 *
 * So a gap breaks the line, and each surviving run of points is drawn as its own polyline.
 * An isolated point (neighbours on both sides absent) still gets a dot, because a single
 * measurement should not vanish just for having no one to connect to.
 */
interface MetricSparklineProps {
  values: (number | null)[];
  tone?: OverviewTone;
  className?: string;
  height?: number;
}

const toneClasses: Record<OverviewTone, string> = {
  success: "text-[var(--tessera-fg-success)]",
  warning: "text-[var(--tessera-fg-warning)]",
  danger: "text-[var(--tessera-fg-danger)]",
  info: "text-[var(--tessera-fg-info)]",
  neutral: "text-[var(--tessera-text-muted)]",
  gold: "text-[var(--tessera-fg-gold)]",
};

export function MetricSparkline({
  values,
  tone = "info",
  className,
  height = 34,
}: MetricSparklineProps) {
  const { runs, dots } = buildRuns(values, height);

  return (
    <svg
      aria-hidden
      viewBox={`0 0 100 ${height}`}
      preserveAspectRatio="none"
      className={cn("h-8 w-full overflow-visible", toneClasses[tone], className)}
    >
      <title>Trend</title>
      {runs.map((points) => (
        <polyline
          key={points}
          points={points}
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      ))}
      {dots.map(([cx, cy]) => (
        <circle
          key={`${cx}-${cy}`}
          cx={cx}
          cy={cy}
          r="1.6"
          fill="currentColor"
          vectorEffect="non-scaling-stroke"
        />
      ))}
      <line
        x1="0"
        x2="100"
        y1={height - 2}
        y2={height - 2}
        stroke="currentColor"
        strokeOpacity="0.12"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

/**
 * What the cell says when `hasDrawableCurve` is false — the else-branch of the sparkline.
 *
 * It lives beside the curve because it is the same decision seen from the other side, and it
 * is a COMPONENT rather than a string because the honest version of "pas encore d'historique"
 * needs the geometry: three of the four reasons a control has no curve carry a `.why` on
 * hover, and this one — the only reason that is about the WINDOW rather than the metric — had
 * none. At 7 days it read "no history yet" over 7 scored turns, 39 captured ones and a full
 * probe run. There was history; it all sat inside one 21 h slice, so there was one point, and
 * one point is not a trend.
 *
 * Both tables render it, which is the point: the same control's curve is drawn on Vue
 * d'ensemble and on Qualité IA, and two sentences for one situation is how a cockpit teaches
 * that its explanations are decorative.
 */
export function NoHistoryLabel({
  values,
  bucketHours,
  className,
}: {
  /** The curve that could not be drawn — its length IS the number of slices. */
  values: (number | null)[];
  /** How wide one slice is, in hours. Computable exactly when `values` is non-empty. */
  bucketHours?: number | null;
  className?: string;
}) {
  const t = useTranslations("overview.noCurve");
  const measured = values.filter((v) => v !== null).length;
  const total = values.length;
  const width =
    bucketHours == null
      ? null
      : bucketHours >= 24
        ? t("sliceDays", { n: Math.round(bucketHours / 24) })
        : t("sliceHours", { n: Math.round(bucketHours) });

  return (
    <span
      className={className}
      // No window, no explanation: an empty `values` means the series has not arrived, and
      // inventing "0 slices of 0 h" would be a sentence about nothing.
      // `why.tooShort`, never `tooShort.why`: next-intl reads a dot as a namespace step, so a
      // flat key containing one resolves to nothing and renders its own path. That is what the
      // three sibling tooltips did — silently, on every build, since they were written.
      title={total > 0 && width ? t("why.tooShort", { n: measured, total, width }) : undefined}
    >
      {t("tooShort")}
    </span>
  );
}

/**
 * Contiguous runs of measured points, plus the lone points that have no run to join.
 *
 * The x position comes from a value's INDEX in the whole series, gaps included — so the
 * horizontal axis stays calendar time. Dropping the nulls and re-indexing would compress the
 * quiet weeks out of the picture and silently redraw the axis.
 */
function buildRuns(
  values: (number | null)[],
  height: number,
): { runs: string[]; dots: [number, number][] } {
  const measured = values.filter((v): v is number => v !== null);
  if (measured.length === 0) return { runs: [], dots: [] };

  const max = Math.max(...measured);
  const min = Math.min(...measured);
  const span = max - min || 1;
  const lastIndex = Math.max(1, values.length - 1);

  const point = (value: number, index: number): [number, number] => [
    Number(((index / lastIndex) * 100).toFixed(1)),
    Number((height - 4 - ((value - min) / span) * (height - 8)).toFixed(1)),
  ];

  // A single measured point across the whole window has no slope to draw; a flat line would
  // claim the value held for the entire span. One dot says exactly what is known.
  const [only] = measured;
  if (measured.length === 1 && only !== undefined) {
    const index = values.findIndex((v) => v !== null);
    return { runs: [], dots: [point(only, index)] };
  }

  const runs: string[] = [];
  const dots: [number, number][] = [];
  let current: [number, number][] = [];
  const flush = (): void => {
    if (current.length > 1) runs.push(current.map(([x, y]) => `${x} ${y}`).join(" "));
    else {
      const [lone] = current;
      if (lone !== undefined) dots.push(lone);
    }
    current = [];
  };
  values.forEach((value, index) => {
    if (value === null) flush();
    else current.push(point(value, index));
  });
  flush();
  return { runs, dots };
}
