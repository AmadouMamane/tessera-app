"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
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
import type { Route } from "next";
import { useLocale, useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { AuthorityLabel } from "@/components/cockpit/authority-label";
import { MetricInfo } from "@/components/cockpit/metric-info";
import { useRailTimeline, useTemporalState } from "@/components/overview/temporal-rail";
import { SignalCommandBar } from "@/components/surveiller/signal-command-bar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Truncate } from "@/components/ui/truncate";
import { Link } from "@/i18n/navigation";
import { fetchImprovement } from "@/lib/api/client";
import type { Opportunity } from "@/lib/api/schemas";
import { useWindowStore } from "@/lib/stores/window-store";
import { useUrlBackedView } from "@/lib/use-url-backed-view";

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
/** One slot per root CAUSE — identity, not severity: no cause is "the good one". */
const CAUSE_COLOR = [
  "var(--tessera-cat-1)",
  "var(--tessera-cat-2)",
  "var(--tessera-cat-3)",
  "var(--tessera-cat-4)",
  "var(--tessera-cat-5)",
];

const TABS = ["overview", "plan", "curation", "experiments", "release"] as const;

function Panel({
  title,
  children,
  info,
}: { title: string; children: ReactNode; info?: ReactNode }) {
  return (
    <Card className="min-w-0">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-1 text-[0.78rem] font-medium">
          <span>{title}</span>
          {info}
        </CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

/** ⓘ for an improvement panel/metric, reading improvement.explain.<k> (null if undocumented). */
function ExplainInfo({ k, title }: { k: string; title: string }) {
  const te = useTranslations("improvement.explain");
  if (!te.has(`${k}.what`)) return null;
  return (
    <MetricInfo
      title={title}
      what={te(`${k}.what`)}
      how={te.has(`${k}.how`) ? te(`${k}.how`) : undefined}
      source={te.has(`${k}.source`) ? te(`${k}.source`) : undefined}
    />
  );
}

function Kpi({
  icon: Icon,
  label,
  value,
  tone,
  infoKey,
  href,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  tone?: string;
  infoKey?: string;
  /** Real source this tile drills into — makes the whole tile a link (↗). */
  href?: Route;
}) {
  const te = useTranslations("improvement.explain");
  const ti = useTranslations("improvement");
  return (
    <Card
      className={`group relative flex flex-col gap-0.5 p-3 ${
        href ? "transition-colors hover:border-[var(--tessera-green)]/40" : ""
      }`}
    >
      {/* Whole-tile drill-down: an overlay <Link> sibling so the inner ⓘ never
          triggers navigation (content is pointer-transparent, ⓘ re-enabled). */}
      {href ? (
        <Link
          href={href}
          aria-label={ti("openSource", { label })}
          className="absolute inset-0 z-10 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--tessera-green)]/40"
        />
      ) : null}
      <div
        className={`flex items-center gap-1.5 text-xs text-[var(--muted-foreground)] ${
          href ? "pointer-events-none relative z-20" : ""
        }`}
      >
        <Icon className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">{label}</span>
        {infoKey ? (
          <span className={href ? "pointer-events-auto ml-auto" : "ml-auto"}>
            <MetricInfo
              title={label}
              what={te(`${infoKey}.what`)}
              how={te(`${infoKey}.how`)}
              source={te.has(`${infoKey}.source`) ? te(`${infoKey}.source`) : undefined}
            />
          </span>
        ) : null}
      </div>
      <div
        className={`text-2xl font-semibold tabular-nums ${tone ?? "text-[var(--foreground)]"} ${
          href ? "pointer-events-none relative z-20" : ""
        }`}
      >
        {value}
      </div>
      {href ? (
        <ArrowUpRight className="pointer-events-none absolute right-1.5 bottom-1.5 z-20 h-3 w-3 text-[var(--muted-foreground)] opacity-30 transition-opacity group-hover:opacity-70" />
      ) : null}
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
            <Truncate className="min-w-0 flex-1">{s.label}</Truncate>
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
  const locale = useLocale();
  const [activeTab, setActiveTab] = useUrlBackedView(TABS, "overview");
  const temporal = useTemporalState();
  const { asOf, historyMode } = temporal;
  const railTimeline = useRailTimeline();
  // The window LENGTH, from the header's period selector. This page SHOWS that selector, so
  // its posture must be the posture over the selected period — a control that steers nothing
  // is worse than no control, because it is read as if it did.
  const period = useWindowStore((st) => st.period);
  const q = useQuery({
    queryKey: ["improvement", locale, asOf ?? null, period],
    queryFn: ({ signal }) => fetchImprovement(locale, asOf, signal, period),
    refetchInterval: historyMode ? false : POLL,
  });
  const d = q.data;

  // SR-01 command bar — the improvement posture is org-wide (no ?agent= in its
  // query), so the agent-scope chip is hidden with its fleet fetch (v1.8 rule:
  // a control the page does not honour is not shown).
  const commandBar = (
    <SignalCommandBar
      temporal={temporal}
      timeline={railTimeline.data}
      liveStatus={ti("temporal.liveData")}
      scopeFilter={false}
    />
  );

  if (!d?.available) {
    return (
      <div className="flex flex-col gap-2.5">
        {commandBar}
        <Card>
          <CardContent className="py-10 text-center text-sm text-[var(--muted-foreground)]">
            {q.isLoading ? ti("loading") : ti("unavailable")}
          </CardContent>
        </Card>
      </div>
    );
  }

  const causeSlices = Object.entries(d.causes ?? {}).map(([label, count], i) => ({
    label,
    count,
    color: CAUSE_COLOR[i % CAUSE_COLOR.length] ?? "var(--tessera-text-muted)",
  }));
  const topProblems = [...(d.opportunities ?? [])].sort((a, b) => b.gain_pts - a.gain_pts);

  // KPI tiles — defined once, composed per tab (only the active tab renders).
  const kpi = {
    gain: (
      <Kpi
        key="gain"
        icon={TrendingUp}
        label={ti("kpi.gain")}
        infoKey="gain"
        href="/surveiller/qualite-ia"
        value={`+${d.potential_gain_pts ?? 0} pts`}
        tone={GOOD}
      />
    ),
    actions: (
      <Kpi
        key="actions"
        icon={Sparkles}
        label={ti("kpi.actions")}
        infoKey="actions"
        value={`${d.n_active_actions ?? 0}`}
      />
    ),
    curate: (
      <Kpi
        key="curate"
        icon={Layers}
        label={ti("kpi.curate")}
        infoKey="curate"
        href="/agir/curation-eval-set"
        value={`${d.n_to_curate ?? 0}`}
        tone={WARN}
      />
    ),
    frozen: (
      <Kpi
        key="frozen"
        icon={Snowflake}
        label={ti("kpi.frozen")}
        infoKey="frozen"
        href="/agir/release-control"
        value={`${d.n_frozen_releases ?? 0}`}
        tone={(d.n_frozen_releases ?? 0) > 0 ? BAD : GOOD}
      />
    ),
    shadow: (
      <Kpi
        key="shadow"
        icon={FlaskConical}
        label={ti("kpi.shadow")}
        infoKey="shadow"
        href="/agir/replay-shadow"
        value={`${d.n_shadow_candidates ?? 0}`}
      />
    ),
    coverage: (
      <Kpi
        key="coverage"
        icon={Target}
        label={ti("kpi.coverage")}
        infoKey="coverage"
        href="/agir/curation-eval-set"
        value={`${Math.round((d.eval_coverage ?? 0) * 100)}%`}
        tone={(d.eval_coverage ?? 0) >= 0.8 ? GOOD : WARN}
      />
    ),
    debt: (
      <Kpi
        key="debt"
        icon={Boxes}
        label={ti("kpi.debt")}
        infoKey="debt"
        href="/configurer/sources-memoire"
        value={`${d.corpus_debt_days ?? 0} j`}
        tone={(d.corpus_debt_days ?? 0) > 90 ? WARN : GOOD}
      />
    ),
    roi: (
      <Kpi
        key="roi"
        icon={TrendingUp}
        label={ti("kpi.roi")}
        infoKey="roi"
        value={`+${d.roi_pct ?? 0}%`}
        tone={GOOD}
      />
    ),
  };

  const panelOpportunities = (
    <Panel
      title={ti("panel.opportunities")}
      info={<ExplainInfo k="opportunities" title={ti("panel.opportunities")} />}
    >
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
  );

  const panelCauses = (
    <Panel title={ti("panel.causes")} info={<ExplainInfo k="causes" title={ti("panel.causes")} />}>
      {causeSlices.length === 0 ? (
        <p className="py-4 text-center text-[0.7rem] text-[var(--muted-foreground)]">—</p>
      ) : (
        <Donut slices={causeSlices} />
      )}
    </Panel>
  );

  const panelCoverage = (
    <Panel
      title={ti("panel.coverage")}
      info={<ExplainInfo k="coverage" title={ti("panel.coverage")} />}
    >
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
      <div className="mt-2 h-[4px] w-full overflow-hidden rounded-full bg-[var(--tessera-border)]">
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
  );

  const candidateCard = d.candidate ? <CandidateCard candidate={d.candidate} /> : null;
  const topProblemsCard = <TopProblemsCard topProblems={topProblems} />;

  const tabBody: Record<(typeof TABS)[number], ReactNode> = {
    // Vue d'ensemble = the comprehensive dashboard (normative 09): the KPI strip,
    // the priorities table (A), the diagnostics (B) and the release/top-problems
    // cards, all at once. The other tabs are focused subsets. Sections the backend
    // has no real source for (change log, corpus gaps, burndown) are omitted.
    overview: (
      <>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-8">
          {[
            kpi.gain,
            kpi.actions,
            kpi.curate,
            kpi.frozen,
            kpi.shadow,
            kpi.coverage,
            kpi.debt,
            kpi.roi,
          ]}
        </div>
        {panelOpportunities}
        <div className="grid items-start gap-2 lg:grid-cols-2">
          {panelCauses}
          {panelCoverage}
        </div>
        <div className="grid items-start gap-2 lg:grid-cols-2">
          {candidateCard}
          {topProblemsCard}
        </div>
      </>
    ),
    plan: (
      <>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
          {[kpi.gain, kpi.actions, kpi.roi]}
        </div>
        {panelOpportunities}
        {panelCauses}
      </>
    ),
    curation: (
      <>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
          {[kpi.curate, kpi.coverage, kpi.debt]}
        </div>
        <div className="grid items-start gap-2 lg:grid-cols-2">
          {panelCoverage}
          {panelCauses}
        </div>
        <CtaCard
          href="/agir/curation-eval-set"
          icon={Layers}
          label={ti("cta.curationLabel")}
          desc={ti("cta.curationDesc")}
        />
      </>
    ),
    experiments: (
      <>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
          {[kpi.shadow, kpi.gain, kpi.roi]}
        </div>
        <p className="text-[0.72rem] leading-relaxed text-[var(--muted-foreground)]">
          {ti("cta.experimentsNote")}
        </p>
        {topProblemsCard}
        <CtaCard
          href="/agir/replay-shadow"
          icon={FlaskConical}
          label={ti("cta.experimentsLabel")}
          desc={ti("cta.experimentsDesc")}
        />
      </>
    ),
    release: (
      <>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-2">{[kpi.frozen, kpi.coverage]}</div>
        {candidateCard}
        <CtaCard
          href="/agir/release-control"
          icon={Snowflake}
          label={ti("cta.releaseLabel")}
          desc={ti("cta.releaseDesc")}
        />
      </>
    ),
  };

  return (
    <div className="flex flex-col gap-2.5">
      {commandBar}
      <nav
        role="tablist"
        aria-label={ti("title")}
        className="flex min-w-0 items-center gap-1 overflow-x-auto border-b border-[var(--tessera-border)]"
      >
        {TABS.map((t) => {
          const active = t === activeTab;
          return (
            <button
              key={t}
              type="button"
              role="tab"
              id={`improvement-tab-${t}`}
              aria-selected={active}
              aria-controls="improvement-tabpanel"
              onClick={() => setActiveTab(t)}
              className={`-mb-px flex shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-[0.8rem] transition-colors ${active ? "border-[var(--tessera-green)] font-medium text-[var(--tessera-text)]" : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--tessera-text)]"}`}
            >
              {ti(`tabs.${t}`)}
            </button>
          );
        })}
      </nav>

      <div className="grid gap-2 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div
          id="improvement-tabpanel"
          role="tabpanel"
          aria-labelledby={`improvement-tab-${activeTab}`}
          className="flex min-w-0 flex-col gap-2"
        >
          {tabBody[activeTab]}
        </div>

        <ImprovementRail
          currentVersion={d.current_version ?? ""}
          onOpenPlan={() => setActiveTab("plan")}
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
          <Truncate className="min-w-0">{o.action}</Truncate>
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

/** The current release candidate and its real quality gates (eval + corpus). */
function CandidateCard({
  candidate,
}: {
  candidate: {
    version: string;
    label: string;
    gates: { name: string; value: string; passed: boolean }[];
  };
}) {
  const ti = useTranslations("improvement");
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2 pb-2">
        <CardTitle className="flex items-center gap-1.5 text-sm">
          {candidate.version}
          <ExplainInfo k="candidate" title={ti("rail.candidate")} />
        </CardTitle>
        <Badge tone="neutral">{ti("rail.candidate")}</Badge>
      </CardHeader>
      <CardContent className="flex flex-col gap-1.5">
        {candidate.gates.map((g) => (
          <div key={g.name} className="flex items-center justify-between gap-2 text-[0.72rem]">
            <span className="text-[var(--muted-foreground)]">{ti(`gate.${g.name}`)}</span>
            <span className="flex items-center gap-2">
              <span className="tabular-nums">{g.value}</span>
              <Badge tone={g.passed ? "success" : "warning"}>
                {g.passed ? ti("gateState.pass") : ti("gateState.watch")}
              </Badge>
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

/** The most gain-bearing addressable problems, ranked by their apportioned gain. */
function TopProblemsCard({ topProblems }: { topProblems: Opportunity[] }) {
  const ti = useTranslations("improvement");
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-1.5 text-sm">
          {ti("rail.topProblems")}
          <ExplainInfo k="topProblems" title={ti("rail.topProblems")} />
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-1.5">
        {topProblems.length === 0 ? (
          <p className="py-2 text-center text-[0.7rem] text-[var(--muted-foreground)]">—</p>
        ) : (
          topProblems.slice(0, 5).map((p) => (
            <div key={p.rank} className="flex items-center gap-2 text-[0.72rem]">
              <Truncate className="min-w-0 flex-1">{p.cause}</Truncate>
              <span className={`shrink-0 tabular-nums ${GOOD}`}>+{p.gain_pts} pts</span>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

/** The version currently serving production (read from the report). */
function CurrentReleaseCard({ currentVersion }: { currentVersion: string }) {
  const ti = useTranslations("improvement");
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-1.5 text-sm">
          {ti("rail.current")}
          <ExplainInfo k="current" title={ti("rail.current")} />
        </CardTitle>
      </CardHeader>
      <CardContent className="flex items-center justify-between gap-2 text-[0.72rem]">
        <span className="font-serif text-base font-semibold tabular-nums">
          {currentVersion || "—"}
        </span>
        <Badge tone="success">{ti("rail.inProd")}</Badge>
      </CardContent>
    </Card>
  );
}

/** A real navigation card into the sibling action page (curation / shadow / release). */
function CtaCard({
  href,
  icon: Icon,
  label,
  desc,
}: {
  href: Route;
  icon: LucideIcon;
  label: string;
  desc: string;
}) {
  return (
    <Link
      href={href}
      className="group flex items-center gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]/40 p-3 transition-colors hover:border-[var(--tessera-green)]/40 hover:bg-[var(--tessera-surface)]/70"
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-[var(--tessera-muted)] text-[var(--tessera-green)]">
        <Icon className="h-4 w-4" />
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-[0.8rem] font-medium">{label}</span>
        <span className="text-[0.68rem] text-[var(--muted-foreground)]">{desc}</span>
      </span>
      <ArrowUpRight className="h-4 w-4 shrink-0 text-[var(--muted-foreground)] opacity-40 transition-opacity group-hover:opacity-80" />
    </Link>
  );
}

function ImprovementRail({
  currentVersion,
  onOpenPlan,
}: {
  currentVersion: string;
  onOpenPlan: () => void;
}) {
  const ti = useTranslations("improvement");
  return (
    <aside className="flex min-w-0 flex-col gap-2">
      <div className="flex flex-col gap-2 xl:sticky xl:top-4">
        <CurrentReleaseCard currentVersion={currentVersion} />

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-1.5 text-sm">
              {ti("rail.sensitive")}
              <ExplainInfo k="sensitive" title={ti("rail.sensitive")} />
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1.5">
            <SensitiveLink
              href="/agir/release-control"
              icon={Snowflake}
              label={ti("rail.freeze")}
            />
            <SensitiveLink href="/agents" icon={Settings2} label={ti("rail.prompt")} />
            <SensitiveLink
              href="/configurer/sources-memoire"
              icon={Boxes}
              label={ti("rail.corpus")}
            />
          </CardContent>
        </Card>

        <Button
          size="sm"
          type="button"
          onClick={onOpenPlan}
          className="h-8 w-full justify-center gap-2 border border-[#5b4bbd] bg-[#4c3fb0]/40 text-xs text-[var(--tessera-fg-accent)] hover:bg-[#4c3fb0]/60"
        >
          {ti("rail.planCta")}
        </Button>
      </div>
    </aside>
  );
}

/** A sensitive-action shortcut: a real link to the governed page (Admin+ badge). */
function SensitiveLink({
  href,
  icon: Icon,
  label,
}: { href: Route; icon: LucideIcon; label: string }) {
  return (
    <Link
      href={href}
      className="group flex items-center gap-2 rounded-md border border-[var(--tessera-border)] px-2 py-1.5 text-[0.72rem] transition-colors hover:border-[var(--tessera-green)]/40 hover:bg-[var(--tessera-surface)]/50"
    >
      <Icon className="h-3.5 w-3.5 shrink-0 text-[var(--muted-foreground)] group-hover:text-[var(--tessera-green)]" />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      <Badge tone="warning">
        <AuthorityLabel authority="Admin+" />
      </Badge>
    </Link>
  );
}
