"use client";

import { cn } from "@/lib/cn";

/**
 * Shared cockpit atom — the stretchy inline-SVG line chart, lifted from the
 * Journal d'audit reference (see docs/ui-style-reference.md §5). The viewBox
 * stretches to fill the card width (`preserveAspectRatio="none"`) while strokes
 * keep a constant 2px width (`vectorEffect="non-scaling-stroke"`) — that pair is
 * why the chart fills a wide card instead of staying centred.
 *
 * The caller computes the series and tick labels (use {@link sampleTicks} to thin
 * a dense x-axis down to four representative ticks) and passes them in; the chart
 * owns only the stretch + tick layout.
 */

/** One line to draw: its y-values and stroke color. */
export interface ChartLine {
  points: number[];
  color: string;
}

/** Thin a dense series down to ~4 evenly-spaced items for axis ticks. */
export function sampleTicks<T>(items: T[]): T[] {
  if (items.length <= 4) return items;
  const indexes = new Set([
    0,
    Math.floor((items.length - 1) / 3),
    Math.floor(((items.length - 1) * 2) / 3),
    items.length - 1,
  ]);
  return [...indexes]
    .sort((a, b) => a - b)
    .map((index) => items[index])
    .filter((item): item is T => item !== undefined);
}

export function StretchChart({
  lines,
  ticks = [],
  title,
}: {
  lines: ChartLine[];
  /** Tick labels under the chart (laid out across four columns). */
  ticks?: string[];
  /** Accessible <title> for the SVG (e.g. the total count). */
  title: string;
}) {
  return (
    <div className="flex h-full flex-col justify-end gap-1.5 pb-1">
      <svg
        viewBox="0 0 220 64"
        preserveAspectRatio="none"
        className="h-[58px] w-full shrink-0"
        aria-hidden="true"
      >
        <title>{title}</title>
        <line
          x1="0"
          x2="220"
          y1="58"
          y2="58"
          stroke="currentColor"
          vectorEffect="non-scaling-stroke"
          className="text-[var(--tessera-border)]"
        />
        {lines.map((line) => (
          <polyline
            key={line.color}
            points={polyline(line.points, 220, 56)}
            fill="none"
            stroke={line.color}
            strokeWidth="2"
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>
      {ticks.length > 0 ? (
        <div className="grid grid-cols-4 gap-1 text-[0.62rem] text-[var(--tessera-text-muted)]">
          {ticks.map((label, index) => (
            <span
              // biome-ignore lint/suspicious/noArrayIndexKey: axis tick labels are positional and the row is regenerated wholesale per window
              key={`${label}-${index}`}
              className={cn(
                "min-w-0 truncate",
                index === 0
                  ? "text-left"
                  : index === ticks.length - 1
                    ? "text-right"
                    : "text-center",
              )}
            >
              {label}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function polyline(values: number[], width: number, height: number): string {
  if (values.length === 0) return "";
  const max = Math.max(...values, 1);
  const last = Math.max(values.length - 1, 1);
  return values
    .map((value, index) => {
      const x = (index / last) * width;
      const y = height - (value / max) * (height - 8);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}
