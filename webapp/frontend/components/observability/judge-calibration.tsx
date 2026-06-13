"use client";

import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Calibration, CalibrationPoint } from "@/lib/api/schemas";

const MATCH = "#10b981";
const MISS = "#ef4444";

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs text-[var(--muted-foreground)]">{label}</span>
      <span className="font-serif text-lg font-semibold tabular-nums">{value}</span>
    </div>
  );
}

/** Scatter of judge score by human verdict, coloured by agreement. */
function AgreementScatter({ points }: { points: CalibrationPoint[] }) {
  const tq = useTranslations("quality");
  const H = 56;
  const top = 4;
  const good = points.filter((p) => p.human_label === "good");
  const bad = points.filter((p) => p.human_label !== "good");
  const bandX = (size: number, i: number, center: number) =>
    size <= 1 ? center : center - 12 + (24 * i) / (size - 1);
  const dot = (group: CalibrationPoint[], center: number) =>
    group.map((p, i) => (
      <circle
        key={`${center}-${p.question}-${i}`}
        cx={bandX(group.length, i, center)}
        cy={top + (1 - p.judge_score) * H}
        r={1.4}
        fill={p.match ? MATCH : MISS}
      />
    ));
  return (
    <div className="flex flex-col gap-1">
      <div className="relative h-44 w-full">
        <svg
          viewBox={`0 0 100 ${H + top * 2}`}
          preserveAspectRatio="none"
          className="h-full w-full"
          aria-hidden="true"
        >
          {/* pass threshold at 0.5 */}
          <line
            x1={0}
            x2={100}
            y1={top + 0.5 * H}
            y2={top + 0.5 * H}
            stroke="var(--tessera-border)"
            strokeDasharray="2 2"
            strokeWidth={0.4}
          />
          {dot(good, 28)}
          {dot(bad, 72)}
        </svg>
      </div>
      <div className="flex justify-around text-xs text-[var(--muted-foreground)]">
        <span>{tq("judge.humanGood")}</span>
        <span>{tq("judge.humanBad")}</span>
      </div>
    </div>
  );
}

/** Histogram of judge scores in five bins. */
function ScoreDistribution({ points }: { points: CalibrationPoint[] }) {
  const bins = [0, 0, 0, 0, 0];
  for (const p of points) {
    const idx = Math.min(4, Math.max(0, Math.floor(p.judge_score * 5)));
    bins[idx] = (bins[idx] ?? 0) + 1;
  }
  const max = Math.max(1, ...bins);
  return (
    <div className="flex h-44 items-end gap-2">
      {bins.map((c, i) => (
        <div key={(i * 0.2).toFixed(1)} className="flex flex-1 flex-col items-center gap-1">
          <span className="text-[0.65rem] tabular-nums text-[var(--muted-foreground)]">{c}</span>
          <div
            className="w-full rounded-t bg-blue-500/70"
            style={{ height: `${(c / max) * 100}%`, minHeight: c > 0 ? "4px" : "0" }}
          />
          <span className="text-[0.6rem] tabular-nums text-[var(--muted-foreground)]">
            {(i * 0.2).toFixed(1)}
          </span>
        </div>
      ))}
    </div>
  );
}

/** Full judge-calibration hero: KPIs, agreement scatter, distribution, disagreements. */
export function JudgeCalibration({
  data,
  loading,
}: {
  data: Calibration | undefined;
  loading: boolean;
}) {
  const tq = useTranslations("quality");

  if (loading && !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{tq("judge.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-48 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (!data?.available) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{tq("judge.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
            {tq("judge.unavailable")}
          </p>
        </CardContent>
      </Card>
    );
  }

  const points = data.points ?? [];
  const disagreements = points.filter((p) => !p.match);
  const pct = (x: number | undefined) => (x == null ? "—" : `${Math.round(x * 100)}%`);

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between gap-2 text-sm">
            {tq("judge.title")}
            <Badge tone={data.lenient ? "warning" : "success"}>
              {data.lenient ? tq("judge.lenientYes") : tq("judge.lenientNo")}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-x-8 gap-y-3">
            <Metric label={tq("judge.kappa")} value={(data.kappa ?? 0).toFixed(2)} />
            <Metric label={tq("judge.agreement")} value={pct(data.agreement)} />
            <Metric
              label={tq("judge.separation")}
              value={`${(data.mean_score_good ?? 0).toFixed(2)} / ${(data.mean_score_bad ?? 0).toFixed(2)}`}
            />
            <Metric label={tq("judge.verbosity")} value={(data.verbosity_corr ?? 0).toFixed(2)} />
            <Metric label={tq("judge.judge")} value={data.judge_model ?? "—"} />
            <Metric label="n" value={String(data.n ?? points.length)} />
          </div>
        </CardContent>
      </Card>

      <div className="grid items-start gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{tq("judge.scatter")}</CardTitle>
          </CardHeader>
          <CardContent>
            {points.length === 0 ? (
              <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">—</p>
            ) : (
              <AgreementScatter points={points} />
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{tq("judge.distribution")}</CardTitle>
          </CardHeader>
          <CardContent>
            {points.length === 0 ? (
              <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">—</p>
            ) : (
              <ScoreDistribution points={points} />
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            {tq("judge.disagreements")}
            <Badge tone={disagreements.length === 0 ? "success" : "warning"}>
              {disagreements.length}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {disagreements.length === 0 ? (
            <p className="py-4 text-center text-sm text-[var(--muted-foreground)]">
              {tq("judge.noDisagreements")}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                    <th className="py-2 pr-4 font-medium">{tq("judge.cols.case")}</th>
                    <th className="py-2 pr-4 font-medium">{tq("judge.cols.human")}</th>
                    <th className="py-2 pr-4 font-medium">{tq("judge.cols.judge")}</th>
                    <th className="py-2 font-medium">{tq("judge.cols.score")}</th>
                  </tr>
                </thead>
                <tbody>
                  {disagreements.map((p, i) => (
                    <tr key={`${p.question}-${i}`} className="border-b border-[var(--border)]/50">
                      <td className="py-2 pr-4 text-[var(--muted-foreground)]">
                        <span className="line-clamp-1 max-w-md">{p.question}</span>
                      </td>
                      <td className="py-2 pr-4">{p.human_label}</td>
                      <td className="py-2 pr-4">{p.judge_label}</td>
                      <td className="py-2 tabular-nums">{p.judge_score.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
