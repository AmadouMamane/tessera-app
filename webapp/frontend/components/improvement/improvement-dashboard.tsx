"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Boxes,
  FlaskConical,
  Layers,
  type LucideIcon,
  Settings2,
  ShieldCheck,
  Snowflake,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchImprovement } from "@/lib/api/client";
import type { Opportunity } from "@/lib/api/schemas";

const GOOD = "text-emerald-600 dark:text-emerald-400";
const WARN = "text-amber-600 dark:text-amber-400";
const BAD = "text-red-600 dark:text-red-400";

const LEVEL_BADGE: Record<string, "success" | "warning" | "danger"> = {
  low: "success",
  medium: "warning",
  high: "danger",
};
const STATUS_BADGE: Record<string, "neutral" | "warning" | "success" | "danger"> = {
  to_start: "neutral",
  in_progress: "warning",
  ready: "success",
  to_approve: "danger",
};
const CAUSE_COLOR = ["#60a5fa", "#34d399", "#fbbf24", "#f472b6", "#a78bfa"];

const TABS = ["overview", "plan", "curation", "experiments", "release"] as const;

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card className="min-w-0">
      <CardHeader className="pb-2">
        <CardTitle className="text-[0.78rem] font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function Kpi({
  icon: Icon,
  label,
  value,
  tone,
}: { icon: LucideIcon; label: string; value: string; tone?: string }) {
  return (
    <Card className="flex flex-col gap-0.5 p-3">
      <div className="flex items-center gap-1.5 text-xs text-[var(--muted-foreground)]">
        <Icon className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">{label}</span>
      </div>
      <div className={`text-2xl font-semibold tabular-nums ${tone ?? "text-[var(--foreground)]"}`}>
        {value}
      </div>
    </Card>
  );
}

function Donut({ slices }: { slices: { label: string; count: number; color: string }[] }) {
  const total = slices.reduce((s, x) => s + x.count, 0) || 1;
  const R = 28;
  const C = 2 * Math.PI * R;
  let off = 0;
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-[80px] w-[80px] shrink-0">
        <svg viewBox="0 0 72 72" className="h-full w-full -rotate-90" aria-hidden="true">
          <circle
            cx="36"
            cy="36"
            r={R}
            fill="none"
            stroke="var(--tessera-border)"
            strokeWidth="9"
          />
          {slices.map((s) => {
            const frac = s.count / total;
            const seg = { dash: frac * C, gap: C - frac * C, o: -off * C };
            off += frac;
            return (
              <circle
                key={s.label}
                cx="36"
                cy="36"
                r={R}
                fill="none"
                stroke={s.color}
                strokeWidth="9"
                strokeDasharray={`${seg.dash} ${seg.gap}`}
                strokeDashoffset={seg.o}
              />
            );
          })}
        </svg>
        <div className="absolute inset-0 flex items-center justify-center text-base font-semibold tabular-nums">
          {total}
        </div>
      </div>
      <ul className="flex min-w-0 flex-1 flex-col gap-1 text-[0.7rem]">
        {slices.map((s) => (
          <li key={s.label} className="flex items-center gap-1.5">
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: s.color }} />
            <span className="min-w-0 flex-1 truncate">{s.label}</span>
            <span className="shrink-0 tabular-nums text-[var(--muted-foreground)]">{s.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const POLL = 30_000;

export function ImprovementDashboard() {
  const ti = useTranslations("improvement");
  const q = useQuery({
    queryKey: ["improvement"],
    queryFn: ({ signal }) => fetchImprovement(signal),
    refetchInterval: POLL,
  });
  const d = q.data;

  if (!d?.available) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-[var(--muted-foreground)]">
          {q.isLoading ? ti("loading") : ti("unavailable")}
        </CardContent>
      </Card>
    );
  }

  const causeSlices = Object.entries(d.causes ?? {}).map(([label, count], i) => ({
    label,
    count,
    color: CAUSE_COLOR[i % CAUSE_COLOR.length] ?? "#94a3b8",
  }));
  const topProblems = [...(d.opportunities ?? [])].sort((a, b) => b.gain_pts - a.gain_pts);

  return (
    <div className="flex flex-col gap-2">
      <nav className="flex min-w-0 items-center gap-1 overflow-x-auto border-b border-[var(--tessera-border)]">
        {TABS.map((t, i) => (
          <span
            key={t}
            className={`-mb-px flex shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-[0.8rem] ${i === 0 ? "border-[var(--tessera-green)] font-medium text-[var(--tessera-text)]" : "border-transparent text-[var(--muted-foreground)]"}`}
          >
            {ti(`tabs.${t}`)}
          </span>
        ))}
      </nav>

      {/* KPI strip */}
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-8">
        <Kpi
          icon={TrendingUp}
          label={ti("kpi.gain")}
          value={`+${d.potential_gain_pts ?? 0} pts`}
          tone={GOOD}
        />
        <Kpi icon={Sparkles} label={ti("kpi.actions")} value={`${d.n_active_actions ?? 0}`} />
        <Kpi icon={Layers} label={ti("kpi.curate")} value={`${d.n_to_curate ?? 0}`} tone={WARN} />
        <Kpi
          icon={Snowflake}
          label={ti("kpi.frozen")}
          value={`${d.n_frozen_releases ?? 0}`}
          tone={(d.n_frozen_releases ?? 0) > 0 ? BAD : GOOD}
        />
        <Kpi icon={FlaskConical} label={ti("kpi.shadow")} value={`${d.n_shadow_candidates ?? 0}`} />
        <Kpi
          icon={Target}
          label={ti("kpi.coverage")}
          value={`${Math.round((d.eval_coverage ?? 0) * 100)}%`}
          tone={(d.eval_coverage ?? 0) >= 0.8 ? GOOD : WARN}
        />
        <Kpi
          icon={Boxes}
          label={ti("kpi.debt")}
          value={`${d.corpus_debt_days ?? 0} j`}
          tone={(d.corpus_debt_days ?? 0) > 90 ? WARN : GOOD}
        />
        <Kpi icon={TrendingUp} label={ti("kpi.roi")} value={`+${d.roi_pct ?? 0}%`} tone={GOOD} />
      </div>

      <div className="grid gap-2 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="flex min-w-0 flex-col gap-2">
          {/* A. Priorités d'amélioration */}
          <Panel title={ti("panel.opportunities")}>
            <div className="overflow-x-auto">
              <table className="w-full text-[0.72rem]">
                <thead>
                  <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
                    <th className="py-1 pr-2 font-medium">{ti("col.action")}</th>
                    <th className="py-1 pr-2 font-medium">{ti("col.cause")}</th>
                    <th className="py-1 pr-2 text-right font-medium">{ti("col.gain")}</th>
                    <th className="py-1 pr-2 font-medium">{ti("col.effort")}</th>
                    <th className="py-1 pr-2 font-medium">{ti("col.risk")}</th>
                    <th className="py-1 pr-2 font-medium">{ti("col.owner")}</th>
                    <th className="py-1 font-medium">{ti("col.status")}</th>
                  </tr>
                </thead>
                <tbody>
                  {(d.opportunities ?? []).map((o) => (
                    <OpportunityRow key={o.rank} o={o} />
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          {/* B. causes · couverture */}
          <div className="grid items-start gap-2 lg:grid-cols-2">
            <Panel title={ti("panel.causes")}>
              {causeSlices.length === 0 ? (
                <p className="py-4 text-center text-[0.7rem] text-[var(--muted-foreground)]">—</p>
              ) : (
                <Donut slices={causeSlices} />
              )}
            </Panel>
            <Panel title={ti("panel.coverage")}>
              <div className="flex items-end gap-2">
                <span
                  className={`text-2xl font-semibold tabular-nums ${(d.eval_coverage ?? 0) >= 0.8 ? GOOD : WARN}`}
                >
                  {Math.round((d.eval_coverage ?? 0) * 100)}%
                </span>
                <span className="pb-1 text-xs text-[var(--muted-foreground)]">
                  {ti("panel.coverageSub")}
                </span>
              </div>
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-[var(--tessera-muted)]/50">
                <div
                  className="h-full rounded-full bg-[var(--tessera-green)]"
                  style={{ width: `${(d.eval_coverage ?? 0) * 100}%` }}
                />
              </div>
              <div className="mt-2 flex justify-between text-[0.7rem]">
                <span className="text-[var(--muted-foreground)]">{ti("panel.debt")}</span>
                <span className="tabular-nums">{d.corpus_debt_days ?? 0} j</span>
              </div>
              <div className="flex justify-between text-[0.7rem]">
                <span className="text-[var(--muted-foreground)]">{ti("panel.curate")}</span>
                <span className="tabular-nums">{d.n_to_curate ?? 0}</span>
              </div>
            </Panel>
          </div>
        </div>

        <ImprovementRail
          candidate={d.candidate ?? null}
          topProblems={topProblems}
          currentVersion={d.current_version ?? ""}
        />
      </div>

      <div className="mt-1 flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--muted-foreground)]">
        <Chip icon={ShieldCheck} label={ti("status.chain")} tone="text-[var(--tessera-green)]" />
        <Chip icon={Boxes} label={ti("status.truth")} />
        <Chip icon={Sparkles} label={ti("status.improvement")} />
      </div>
    </div>
  );
}

function OpportunityRow({ o }: { o: Opportunity }) {
  const ti = useTranslations("improvement");
  return (
    <tr className="border-b border-[var(--border)]/50">
      <td className="py-1 pr-2">
        <span className="flex items-center gap-1.5">
          <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded bg-[var(--tessera-muted)] text-[0.55rem] font-semibold tabular-nums">
            {o.rank}
          </span>
          <span className="min-w-0 truncate">{o.action}</span>
        </span>
      </td>
      <td className="py-1 pr-2 text-[var(--muted-foreground)]">{o.cause}</td>
      <td className={`py-1 pr-2 text-right tabular-nums ${GOOD}`}>+{o.gain_pts} pts</td>
      <td className="py-1 pr-2">
        <Badge tone={LEVEL_BADGE[o.effort] ?? "neutral"}>{ti(`level.${o.effort}`)}</Badge>
      </td>
      <td className="py-1 pr-2">
        <Badge tone={LEVEL_BADGE[o.risk] ?? "neutral"}>{ti(`level.${o.risk}`)}</Badge>
      </td>
      <td className="py-1 pr-2 text-[var(--muted-foreground)]">{o.owner}</td>
      <td className="py-1">
        <Badge tone={STATUS_BADGE[o.status] ?? "neutral"}>{ti(`status.${o.status}`)}</Badge>
      </td>
    </tr>
  );
}

function Chip({ icon: Icon, label, tone }: { icon: LucideIcon; label: string; tone?: string }) {
  return (
    <span className="flex min-w-0 items-center gap-1.5 whitespace-nowrap">
      <Icon className={`h-3.5 w-3.5 shrink-0 ${tone ?? ""}`} />
      <span className="truncate">{label}</span>
    </span>
  );
}

function ImprovementRail({
  candidate,
  topProblems,
  currentVersion,
}: {
  candidate: {
    version: string;
    label: string;
    gates: { name: string; value: string; passed: boolean }[];
  } | null;
  topProblems: Opportunity[];
  currentVersion: string;
}) {
  const ti = useTranslations("improvement");
  return (
    <aside className="flex min-w-0 flex-col gap-2">
      <div className="flex flex-col gap-2 xl:sticky xl:top-4">
        {candidate ? (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-2 pb-2">
              <CardTitle className="text-sm">{candidate.version}</CardTitle>
              <Badge tone="neutral">{ti("rail.candidate")}</Badge>
            </CardHeader>
            <CardContent className="flex flex-col gap-1.5">
              {candidate.gates.map((g) => (
                <div
                  key={g.name}
                  className="flex items-center justify-between gap-2 text-[0.72rem]"
                >
                  <span className="text-[var(--muted-foreground)]">{ti(`gate.${g.name}`)}</span>
                  <span className="flex items-center gap-2">
                    <span className="tabular-nums">{g.value}</span>
                    <Badge tone={g.passed ? "success" : "warning"}>
                      {g.passed ? "Pass" : "Watch"}
                    </Badge>
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
        ) : null}

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{ti("rail.topProblems")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1.5">
            {topProblems.slice(0, 5).map((p) => (
              <div key={p.rank} className="flex items-center gap-2 text-[0.72rem]">
                <span className="min-w-0 flex-1 truncate">{p.cause}</span>
                <span className={`shrink-0 tabular-nums ${GOOD}`}>+{p.gain_pts} pts</span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{ti("rail.sensitive")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1.5">
            <SensitiveAction icon={Snowflake} label={ti("rail.freeze")} />
            <SensitiveAction icon={Settings2} label={ti("rail.prompt")} />
            <SensitiveAction icon={Boxes} label={ti("rail.corpus")} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{ti("rail.current")}</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between gap-2 text-[0.72rem]">
            <span className="font-serif text-base font-semibold tabular-nums">
              {currentVersion || "—"}
            </span>
            <Badge tone="success">{ti("rail.inProd")}</Badge>
          </CardContent>
        </Card>

        <Button
          size="sm"
          className="h-8 w-full justify-center gap-2 border border-[#5b4bbd] bg-[#4c3fb0]/40 text-xs text-[#c4b5fd] hover:bg-[#4c3fb0]/60"
        >
          {ti("rail.planCta")}
        </Button>
      </div>
    </aside>
  );
}

function SensitiveAction({ icon: Icon, label }: { icon: LucideIcon; label: string }) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-[var(--tessera-border)] px-2 py-1.5 text-[0.72rem]">
      <Icon className="h-3.5 w-3.5 shrink-0 text-[var(--muted-foreground)]" />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      <Badge tone="warning">Admin+</Badge>
    </div>
  );
}
