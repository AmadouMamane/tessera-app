"use client";

import { ArrowUpRight } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { QInfo } from "@/components/observability/quality-info";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { ScoreSeries } from "@/lib/api/schemas";

const W = 100;
const H = 38;

/** A KPI tile for one metric: mean %, period delta (points), and a mini sparkline. */
export function MetricKpi({
  label,
  series,
  loading,
  info,
  onDrill,
  drillLabel,
}: {
  label: string;
  series: ScoreSeries | undefined;
  loading: boolean;
  /** Optional ⓘ explainer rendered next to the tile label. */
  info?: ReactNode;
  /** Makes the whole tile a drill-down (jump to the detail tab) with a ↗ affordance. */
  onDrill?: () => void;
  drillLabel?: string;
}) {
  const tq = useTranslations("quality");
  const buckets = series?.buckets ?? [];
  const n = buckets.length;
  const pts = buckets
    .map((b, i) => ({ x: n > 1 ? (i / (n - 1)) * W : W / 2, y: b.mean, i }))
    .filter((p): p is { x: number; y: number; i: number } => p.y != null)
    .map((p) => ({ x: p.x, y: 14 - p.y * 14, i: p.i }));
  const segments: string[] = [];
  for (let k = 1; k < pts.length; k++) {
    const a = pts[k - 1];
    const b = pts[k];
    if (a && b && b.i - a.i === 1) {
      segments.push(`M ${a.x} ${a.y} L ${b.x} ${b.y}`);
    }
  }
  const mean = series?.mean ?? null;
  const delta = series?.delta ?? null;
  return (
    <Card
      className={`group relative p-2 ${
        onDrill ? "cursor-pointer transition-colors hover:border-[var(--tessera-green)]/40" : ""
      }`}
    >
      {onDrill ? (
        <button
          type="button"
          onClick={onDrill}
          aria-label={drillLabel}
          className="absolute inset-0 z-10 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--tessera-green)]/40"
        />
      ) : null}
      <div
        className={`flex items-center gap-1 text-[0.7rem] leading-tight text-[var(--muted-foreground)] ${
          onDrill ? "pointer-events-none relative z-20" : ""
        }`}
      >
        <span className="min-w-0 truncate">{label}</span>
        {info ? <span className={onDrill ? "pointer-events-auto" : undefined}>{info}</span> : null}
      </div>
      <div
        className={`mt-0.5 flex items-end justify-between gap-2 ${
          onDrill ? "pointer-events-none relative z-20" : ""
        }`}
      >
        <span className="flex items-baseline gap-1">
          <span className="text-lg font-semibold tabular-nums">
            {mean != null ? `${Math.round(mean * 100)}%` : "—"}
          </span>
          {/* WHICH statistic this is, on the surface rather than inside the ⓘ.
              The SLO ribbon two rows above prints 52.6 % — the share of responses clearing the
              bar — while this tile printed 49 %, the mean of the same 19 scores. Two statistics
              of one sample under one metric name, four points apart: close enough that the only
              available reading was "one of these is broken". An operator comparing two figures
              does not open tooltips.
              (Both figures are named here as numbers, not quoted as on-screen strings: the i18n
              guard scans quoted text and a French label in a comment reads to it exactly like a
              hardcoded one. It is right to — a comment is a poor place to prove intent.) */}
          {mean != null ? (
            <span className="text-[0.6rem] text-[var(--muted-foreground)]">
              {tq("kpi.meanTag")}
            </span>
          ) : null}
        </span>
        {delta != null ? (
          <Badge tone={delta >= 0 ? "success" : "danger"} className="tabular-nums">
            {delta >= 0 ? "+" : ""}
            {Math.round(delta * 100)}
          </Badge>
        ) : null}
      </div>
      <div className={`mt-0.5 h-3 ${onDrill ? "pointer-events-none relative z-20" : ""}`}>
        {loading && !series ? (
          <Skeleton className="h-full w-full" />
        ) : (
          <svg
            viewBox="0 0 100 14"
            preserveAspectRatio="none"
            className="h-full w-full"
            aria-hidden="true"
          >
            {segments.map((d) => (
              <path
                key={d}
                d={d}
                fill="none"
                stroke="var(--tessera-fg-success)"
                strokeWidth={0.8}
                vectorEffect="non-scaling-stroke"
              />
            ))}
            {pts.map((p) => (
              <circle key={p.i} cx={p.x} cy={p.y} r={0.9} fill="var(--tessera-fg-success)" />
            ))}
          </svg>
        )}
      </div>
      {onDrill ? (
        <ArrowUpRight className="pointer-events-none absolute right-1.5 bottom-1.5 z-20 h-3 w-3 text-[var(--muted-foreground)] opacity-30 transition-opacity group-hover:opacity-70" />
      ) : null}
    </Card>
  );
}

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
          <span className="flex items-center gap-1.5">
            {tq("charts.evolution")}
            <QInfo title={tq("charts.evolution")} k="evolution" />
          </span>
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
          <Skeleton className="h-16 w-full" />
        ) : (
          <div className="flex flex-col gap-2">
            <div className="relative h-16 w-full">
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
                    stroke="var(--tessera-fg-success)"
                    strokeWidth={0.8}
                    vectorEffect="non-scaling-stroke"
                  />
                ))}
                {points.map((p) => (
                  <circle key={p.i} cx={p.x} cy={p.y} r={0.9} fill="var(--tessera-fg-success)" />
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
