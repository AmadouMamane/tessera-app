import { cn } from "@/lib/cn";
import type { OverviewTone } from "@/lib/overview";

interface MetricSparklineProps {
  values: number[];
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
  gold: "text-gold-400",
};

export function MetricSparkline({
  values,
  tone = "info",
  className,
  height = 34,
}: MetricSparklineProps) {
  const points = buildPoints(values, height);

  return (
    <svg
      aria-hidden
      viewBox={`0 0 100 ${height}`}
      preserveAspectRatio="none"
      className={cn("h-8 w-full overflow-visible", toneClasses[tone], className)}
    >
      <title>Trend</title>
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
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

function buildPoints(values: number[], height: number): string {
  if (values.length === 0) return "";
  if (values.length === 1) return `0 ${height / 2} 100 ${height / 2}`;

  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;
  const lastIndex = values.length - 1;

  return values
    .map((value, index) => {
      const x = (index / lastIndex) * 100;
      const y = height - 4 - ((value - min) / span) * (height - 8);
      return `${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
}
