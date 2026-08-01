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
