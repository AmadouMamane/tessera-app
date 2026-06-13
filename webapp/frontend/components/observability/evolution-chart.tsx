"use client";

import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { ScoreSeries } from "@/lib/api/schemas";

const W = 100;
const H = 38;

/** Real "score over the last N days" line chart (Vue d'ensemble, image 00). */
export function EvolutionChart({
  series,
  loading,
}: {
  series: ScoreSeries | undefined;
  loading: boolean;
}) {
  const tq = useTranslations("quality");
  const buckets = series?.buckets ?? [];
  const n = buckets.length;

  // Points for non-empty buckets only (empty ⇒ gap, never a fabricated zero).
  const points = buckets
    .map((b, i) => ({ x: n > 1 ? (i / (n - 1)) * W : W / 2, y: b.mean, i }))
    .filter((p): p is { x: number; y: number; i: number } => p.y != null)
    .map((p) => ({ x: p.x, y: H - p.y * H, i: p.i }));

  // Connect only consecutive buckets; a gap breaks the line into segments.
  const segments: string[] = [];
  for (let k = 1; k < points.length; k++) {
    const a = points[k - 1];
    const b = points[k];
    if (a && b && b.i - a.i === 1) {
      segments.push(`M ${a.x} ${a.y} L ${b.x} ${b.y}`);
    }
  }

  const delta = series?.delta ?? null;
  const mean = series?.mean ?? null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-2 text-sm">
          {tq("charts.evolution")}
          {delta != null ? (
            <Badge tone={delta >= 0 ? "success" : "danger"} className="tabular-nums">
              {delta >= 0 ? "+" : ""}
              {delta.toFixed(2)}
            </Badge>
          ) : null}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading && !series ? (
          <Skeleton className="h-28 w-full" />
        ) : (
          <div className="flex flex-col gap-2">
            <div className="relative h-28 w-full">
              <svg
                viewBox={`0 0 ${W} ${H}`}
                preserveAspectRatio="none"
                className="h-full w-full"
                aria-hidden="true"
              >
                {/* gridlines at 0 / 0.5 / 1.0 */}
                {[0, 0.5, 1].map((g) => (
                  <line
                    key={g}
                    x1={0}
                    x2={W}
                    y1={H - g * H}
                    y2={H - g * H}
                    stroke="var(--tessera-border)"
                    strokeWidth={0.3}
                  />
                ))}
                {segments.map((d) => (
                  <path
                    key={d}
                    d={d}
                    fill="none"
                    stroke="#10b981"
                    strokeWidth={0.8}
                    vectorEffect="non-scaling-stroke"
                  />
                ))}
                {points.map((p) => (
                  <circle key={p.i} cx={p.x} cy={p.y} r={0.9} fill="#10b981" />
                ))}
              </svg>
              {points.length === 0 ? (
                <span className="absolute inset-0 flex items-center justify-center text-xs text-[var(--muted-foreground)]">
                  {tq("charts.noData")}
                </span>
              ) : null}
            </div>
            <div className="flex items-center justify-between text-xs text-[var(--muted-foreground)]">
              <span className="tabular-nums">
                {tq("charts.mean")} {mean != null ? mean.toFixed(2) : "—"}
              </span>
              <span className="tabular-nums">{tq("charts.points", { n: series?.n ?? 0 })}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
