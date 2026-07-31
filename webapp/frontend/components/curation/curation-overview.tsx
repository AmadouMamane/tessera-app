"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Check,
  ChevronRight,
  Database,
  Eye,
  FileSearch,
  Filter,
  GitBranch,
  ListChecks,
  PlayCircle,
  Plus,
  ShieldCheck,
  Snowflake,
  UploadCloud,
  UserCheck,
  X,
} from "lucide-react";
import type { Route } from "next";
import { useLocale, useTranslations } from "next-intl";
import type { ComponentType, ReactNode } from "react";
import { useState } from "react";

import { AgirRail, useAsOf } from "@/components/agir/agir-rail";
import { MetricInfo } from "@/components/cockpit/metric-info";
import { StretchChart } from "@/components/cockpit/stretch-chart";
import { SyntheticNotice } from "@/components/cockpit/synthetic-notice";
import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Button } from "@/components/ui/button";
import { Truncate } from "@/components/ui/truncate";
import { Link } from "@/i18n/navigation";
import { fetchCurationOverview, mutateCurationDecision } from "@/lib/api/client";
import type { CurationOverview as CurationData } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import { useUrlBackedView } from "@/lib/use-url-backed-view";

const RISK_BADGE: Record<string, string> = {
  eleve: "border-red-500/30 bg-red-500/15 text-red-300",
  moyen: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  bas: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
};
const WF_TEXT: Record<string, string> = {
  termine: "text-[var(--tessera-fg-success)]",
  encours: "text-[var(--tessera-fg-info)]",
  attente: "text-[var(--tessera-text-muted)]",
};
const LEVEL_BADGE: Record<string, string> = {
  bon: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  moyen: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  faible: "border-red-500/30 bg-red-500/15 text-red-300",
};
const COV_BG: Record<string, string> = {
  ok: "bg-emerald-500/70",
  warn: "bg-amber-500/70",
  bad: "bg-red-500/70",
  none: "bg-[var(--tessera-bg)]",
};

const TABS = ["overview", "curate", "coverage", "promotions", "rejections", "history"] as const;
type Tab = (typeof TABS)[number];
const ACTION_ICONS = {
  promote: UploadCloud,
  assign_review: UserCheck,
  freeze: Snowflake,
  create_replay: PlayCircle,
  export: UploadCloud,
} as const;

type T = ReturnType<typeof useTranslations<"curation">>;
type Data = CurationData;

/** ⓘ for a curation KPI/zone/panel — reads curation.explain.<k>.{what,how,source?}; te.has-guarded. */
function ExplainInfo({ k, title }: { k: string; title: string }) {
  const te = useTranslations("curation.explain");
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

export function CurationOverview() {
  const t = useTranslations("curation");
  const locale = useLocale();
  // AGIR composition (registre §6): As-of reads the folded state at T (URL-derived).
  const asof = useAsOf();
  const frozen = asof !== null;
  const { data } = useQuery({
    queryKey: ["curation-overview", locale, asof],
    queryFn: ({ signal }) => fetchCurationOverview(locale, asof, signal),
    staleTime: 30_000,
    refetchInterval: asof ? false : 30_000,
  });
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useUrlBackedView(TABS, "overview");
  const decide = useMutation({
    mutationFn: mutateCurationDecision,
    onSuccess: (fresh) => qc.setQueryData(["curation-overview", locale, null], fresh),
  });
  const onDecide = (candidateId: string, decision: "promote" | "review" | "reject") =>
    decide.mutate({ candidate_id: candidateId, decision, lang: locale });

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        …
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto pb-1 text-[var(--tessera-text)]">
      <CommandBar t={t} active={activeTab} onSelect={setActiveTab} />
      {/* Registre §6/§8 — AGIR composes As-of + Live; the candidates and their
          decisions fold to T server-side, and deciding freezes while As-of. */}
      <AgirRail />

      <div id="curation-tabpanel" role="tabpanel" className="flex min-w-0 flex-col gap-3">
        {activeTab === "curate" ? (
          <CurateQueue
            t={t}
            data={data}
            onDecide={onDecide}
            deciding={decide.isPending || frozen}
          />
        ) : null}
        {activeTab === "coverage" ? <CoverageTab t={t} data={data} /> : null}
        {activeTab === "promotions" ? (
          <DecidedTab
            t={t}
            data={data}
            decision="promote"
            onDecide={onDecide}
            deciding={decide.isPending || frozen}
          />
        ) : null}
        {activeTab === "rejections" ? (
          <DecidedTab
            t={t}
            data={data}
            decision="reject"
            onDecide={onDecide}
            deciding={decide.isPending || frozen}
          />
        ) : null}
        {activeTab === "history" ? <HistoryTab t={t} data={data} /> : null}
      </div>

      {activeTab !== "overview" ? null : (
        <>
          {/* A · État actuel */}
          <Zone
            label={t("zone.actual")}
            info={<ExplainInfo k="zone.actual" title={t("zone.actual")} />}
          >
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
              {data.kpis.map((kpi) => (
                <KpiTile
                  key={kpi.key}
                  kpi={kpi}
                  label={t(`kpi.${kpi.key}`)}
                  vs={t("delta.vs7d")}
                  info={<ExplainInfo k={`kpi.${kpi.key}`} title={t(`kpi.${kpi.key}`)} />}
                />
              ))}
            </div>
          </Zone>

          <div className="grid min-w-0 gap-2.5 xl:grid-cols-[minmax(0,1fr)_320px]">
            <div className="flex min-w-0 flex-col gap-3">
              {/* B · Diagnostic de curation */}
              <Zone
                label={t("zone.diagnostic")}
                info={<ExplainInfo k="zone.diagnostic" title={t("zone.diagnostic")} />}
              >
                <div className="grid gap-3 xl:grid-cols-12">
                  <PriorityLots
                    t={t}
                    data={data}
                    onDecide={onDecide}
                    deciding={decide.isPending || frozen}
                    className="xl:col-span-7"
                  />
                  <WhyTours t={t} data={data} className="xl:col-span-5" />
                </div>
              </Zone>

              {/* C · Gaps & couverture */}
              <Zone
                label={t("zone.gaps")}
                info={<ExplainInfo k="zone.gaps" title={t("zone.gaps")} />}
              >
                <div className="grid gap-3 xl:grid-cols-12">
                  <CoverageHeatmap t={t} data={data} className="xl:col-span-4" />
                  <Panel
                    title={t("panel.distribution")}
                    info={<ExplainInfo k="panel.distribution" title={t("panel.distribution")} />}
                    className="xl:col-span-3"
                  >
                    <Donut
                      slices={data.candidates_distribution}
                      total={data.distribution_total}
                      caption="candidats"
                      labelOf={(k) => t(`dist.${k}`)}
                      showCount
                    />
                  </Panel>
                  <QualitySignals t={t} data={data} className="xl:col-span-2" />
                  <LinkedDatasets t={t} data={data} className="xl:col-span-3" />
                </div>
              </Zone>
            </div>

            <CurationRail t={t} data={data} />
          </div>

          {/* D · Actions & gouvernance */}
          <Zone
            label={t("zone.governance")}
            info={<ExplainInfo k="zone.governance" title={t("zone.governance")} />}
          >
            <SyntheticNotice signalId="curation" compact />
            <div className="grid gap-3 xl:grid-cols-12">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:col-span-8 2xl:grid-cols-5">
                {data.actions.map((a) => (
                  <ActionCard key={a.key} action={a} t={t} />
                ))}
              </div>
              <RecentActivity
                t={t}
                data={data}
                className="xl:col-span-4"
                onViewAll={() => setActiveTab("history")}
              />
            </div>
          </Zone>

          {/* E · Impact & tendances */}
          <Zone
            label={t("zone.trends")}
            info={<ExplainInfo k="zone.trends" title={t("zone.trends")} />}
          >
            <SyntheticNotice signalId="curation" compact />
            <div className="grid gap-3 xl:grid-cols-12">
              <BacklogTrend t={t} data={data} className="xl:col-span-4" />
              <BalanceChart t={t} data={data} className="xl:col-span-4" />
              <ImpactPanel t={t} data={data} className="xl:col-span-4" />
            </div>
          </Zone>
        </>
      )}

      <Footer t={t} data={data} />
    </div>
  );
}

// ── chrome ───────────────────────────────────────────────────────────────────

function CommandBar({
  t,
  active,
  onSelect,
}: {
  t: T;
  active: Tab;
  onSelect: (tab: Tab) => void;
}) {
  return (
    <section className="flex min-h-[54px] shrink-0 flex-wrap items-center gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <div
        role="tablist"
        aria-label={t("tabs.overview")}
        className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5"
      >
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={tab === active}
            aria-controls="curation-tabpanel"
            onClick={() => onSelect(tab)}
            className={cn(
              "h-8 shrink-0 rounded-md border px-3 text-xs font-medium transition-colors",
              tab === active
                ? "border-[#2e72d2] bg-[#0d3561] text-[#d8eaff]"
                : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]",
            )}
          >
            {t(`tabs.${tab}`)}
          </button>
        ))}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Button
          asChild
          size="sm"
          variant="outline"
          className="h-9 gap-2 border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs"
        >
          <Link href="/surveiller/qualite-ia">
            <PlayCircle className="h-4 w-4" /> {t("actions.launchScoring")}
          </Link>
        </Button>
        <Button
          size="sm"
          onClick={() => onSelect("curate")}
          className="h-9 gap-2 border border-[#2e72d2] bg-[#1b4f8a] px-3 text-xs text-[#d8eaff] hover:bg-[#22609f]"
        >
          <Plus className="h-4 w-4" /> {t("actions.createLot")}
        </Button>
        <Button
          asChild
          size="sm"
          variant="outline"
          className="h-9 gap-2 border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs"
        >
          <Link href="/prouver/evidence-store">
            <FileSearch className="h-4 w-4" /> {t("actions.evidencePack")}
          </Link>
        </Button>
      </div>
    </section>
  );
}

// ── zone B ───────────────────────────────────────────────────────────────────

const DECISION_BADGE: Record<string, string> = {
  pending: "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]",
  promote: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  review: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  reject: "border-red-500/30 bg-red-500/15 text-red-300",
};

function PriorityLots({
  t,
  data,
  onDecide,
  deciding,
  className,
}: {
  t: T;
  data: Data;
  onDecide: (candidateId: string, decision: "promote" | "review" | "reject") => void;
  deciding: boolean;
  className?: string;
}) {
  return (
    <Panel
      title={t("panel.priorityLots")}
      info={<ExplainInfo k="panel.priorityLots" title={t("panel.priorityLots")} />}
      className={className}
      action={<ViewAll label={t("viewAll.lots")} href="/surveiller/qualite-ia" />}
    >
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-xs">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.62rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              <th className="px-2 py-1.5 font-medium">{t("col.id")}</th>
              <th className="px-2 py-1.5 font-medium">{t("col.category")}</th>
              <th className="px-2 py-1.5 font-medium">{t("col.risk")}</th>
              <th className="px-2 py-1.5 font-medium">{t("col.decision")}</th>
              <th className="px-2 py-1.5 text-right font-medium">{t("col.actions")}</th>
            </tr>
          </thead>
          <tbody>
            {data.priority_lots.map((lot) => (
              <tr
                key={lot.candidate_id}
                className="border-b border-[var(--tessera-border)]/60 last:border-0"
              >
                <td
                  className="max-w-[130px] truncate px-2 py-1.5 font-mono text-[0.68rem] text-[var(--tessera-fg-info)]"
                  title={lot.id}
                >
                  {lot.id}
                </td>
                <td className="whitespace-nowrap px-2 py-1.5 text-[var(--tessera-text)]">
                  {t(`category.${lot.category}`)}
                </td>
                <td className="px-2 py-1.5">
                  <Badge className={RISK_BADGE[lot.risk]}>{t(`risk.${lot.risk}`)}</Badge>
                </td>
                <td className="px-2 py-1.5">
                  <Badge className={DECISION_BADGE[lot.decision]}>
                    {t(`decide.${lot.decision}`)}
                  </Badge>
                </td>
                <td className="px-2 py-1.5">
                  <div className="flex items-center justify-end gap-1">
                    <DecideButton
                      icon={Check}
                      label={t("decide.promote")}
                      active={lot.decision === "promote"}
                      tone="emerald"
                      disabled={deciding}
                      onClick={() => onDecide(lot.candidate_id, "promote")}
                    />
                    <DecideButton
                      icon={Eye}
                      label={t("decide.review")}
                      active={lot.decision === "review"}
                      tone="amber"
                      disabled={deciding}
                      onClick={() => onDecide(lot.candidate_id, "review")}
                    />
                    <DecideButton
                      icon={X}
                      label={t("decide.reject")}
                      active={lot.decision === "reject"}
                      tone="red"
                      disabled={deciding}
                      onClick={() => onDecide(lot.candidate_id, "reject")}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

// ── focused tab views (all rows come from the real curation store) ───────────

type Candidate = Data["candidate_lots"][number];
type OnDecide = (candidateId: string, decision: "promote" | "review" | "reject") => void;

function fmtDecidedAt(iso: string, locale: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(locale, {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function CandidateRows({
  t,
  rows,
  onDecide,
  deciding,
  showDecidedAt,
}: {
  t: T;
  rows: Candidate[];
  onDecide: OnDecide;
  deciding: boolean;
  showDecidedAt?: boolean;
}) {
  const locale = useLocale();
  if (rows.length === 0) {
    return (
      <p className="px-2 py-6 text-center text-xs text-[var(--tessera-text-muted)]">
        {t("tabview.empty")}
      </p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left text-xs">
        <thead>
          <tr className="border-b border-[var(--tessera-border)] text-[0.62rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            <th className="px-2 py-1.5 font-medium">{t("col.id")}</th>
            <th className="px-2 py-1.5 font-medium">{t("col.agent")}</th>
            <th className="px-2 py-1.5 font-medium">{t("col.category")}</th>
            <th className="px-2 py-1.5 font-medium">{t("col.language")}</th>
            <th className="px-2 py-1.5 font-medium">{t("col.risk")}</th>
            <th className="px-2 py-1.5 font-medium">{t("col.decision")}</th>
            {showDecidedAt ? (
              <th className="px-2 py-1.5 font-medium">{t("col.decidedAt")}</th>
            ) : null}
            <th className="px-2 py-1.5 text-right font-medium">{t("col.actions")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((lot) => (
            <tr
              key={lot.candidate_id}
              className="border-b border-[var(--tessera-border)]/60 last:border-0"
            >
              <td
                className="max-w-[170px] truncate px-2 py-1.5 font-mono text-[0.68rem] text-[var(--tessera-fg-info)]"
                title={lot.title}
              >
                {lot.id}
              </td>
              <td className="whitespace-nowrap px-2 py-1.5 text-[var(--tessera-text-muted)]">
                {lot.agent_id}
              </td>
              <td className="whitespace-nowrap px-2 py-1.5 text-[var(--tessera-text)]">
                {t(`category.${lot.category}`)}
              </td>
              <td className="whitespace-nowrap px-2 py-1.5 uppercase text-[var(--tessera-text-muted)]">
                {lot.language}
              </td>
              <td className="px-2 py-1.5">
                <Badge className={RISK_BADGE[lot.risk]}>{t(`risk.${lot.risk}`)}</Badge>
              </td>
              <td className="px-2 py-1.5">
                <Badge className={DECISION_BADGE[lot.decision]}>
                  {t(`decide.${lot.decision}`)}
                </Badge>
              </td>
              {showDecidedAt ? (
                <td className="whitespace-nowrap px-2 py-1.5 text-[var(--tessera-text-muted)]">
                  {fmtDecidedAt(lot.decided_at, locale)}
                </td>
              ) : null}
              <td className="px-2 py-1.5">
                <div className="flex items-center justify-end gap-1">
                  <DecideButton
                    icon={Check}
                    label={t("decide.promote")}
                    active={lot.decision === "promote"}
                    tone="emerald"
                    disabled={deciding}
                    onClick={() => onDecide(lot.candidate_id, "promote")}
                  />
                  <DecideButton
                    icon={Eye}
                    label={t("decide.review")}
                    active={lot.decision === "review"}
                    tone="amber"
                    disabled={deciding}
                    onClick={() => onDecide(lot.candidate_id, "review")}
                  />
                  <DecideButton
                    icon={X}
                    label={t("decide.reject")}
                    active={lot.decision === "reject"}
                    tone="red"
                    disabled={deciding}
                    onClick={() => onDecide(lot.candidate_id, "reject")}
                  />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CurateQueue({
  t,
  data,
  onDecide,
  deciding,
}: {
  t: T;
  data: Data;
  onDecide: OnDecide;
  deciding: boolean;
}) {
  const [q, setQ] = useState("");
  const needle = q.trim().toLowerCase();
  const rows = data.candidate_lots.filter(
    (l) =>
      !needle || `${l.id} ${l.title} ${l.agent_id} ${l.language}`.toLowerCase().includes(needle),
  );
  return (
    <Zone
      label={t("tabview.curateTitle")}
      info={<ExplainInfo k="tabview.curate" title={t("tabview.curateTitle")} />}
    >
      <Panel
        title={t("tabview.queueCount", { n: rows.length })}
        action={
          <input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t("tabview.searchPlaceholder")}
            aria-label={t("tabview.searchPlaceholder")}
            className="h-8 w-56 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-xs text-[var(--tessera-text)] outline-none transition-colors placeholder:text-[var(--tessera-text-muted)] focus:border-[#2e72d2]"
          />
        }
      >
        <CandidateRows t={t} rows={rows} onDecide={onDecide} deciding={deciding} />
      </Panel>
    </Zone>
  );
}

function DecidedTab({
  t,
  data,
  decision,
  onDecide,
  deciding,
}: {
  t: T;
  data: Data;
  decision: "promote" | "reject";
  onDecide: OnDecide;
  deciding: boolean;
}) {
  const rows = data.candidate_lots.filter((l) => l.decision === decision);
  const title =
    decision === "promote" ? t("tabview.promotionsTitle") : t("tabview.rejectionsTitle");
  return (
    <Zone label={title} info={<ExplainInfo k="tabview.decided" title={title} />}>
      <Panel title={t("tabview.queueCount", { n: rows.length })}>
        <CandidateRows t={t} rows={rows} onDecide={onDecide} deciding={deciding} showDecidedAt />
      </Panel>
    </Zone>
  );
}

function HistoryTab({ t, data }: { t: T; data: Data }) {
  const locale = useLocale();
  const rows = data.candidate_lots
    .filter((l) => l.decision !== "pending")
    .sort((a, b) => (b.decided_at || "").localeCompare(a.decided_at || ""));
  return (
    <Zone
      label={t("tabview.historyTitle")}
      info={<ExplainInfo k="tabview.history" title={t("tabview.historyTitle")} />}
    >
      <Panel title={t("tabview.queueCount", { n: rows.length })}>
        {rows.length === 0 ? (
          <p className="px-2 py-6 text-center text-xs text-[var(--tessera-text-muted)]">
            {t("tabview.empty")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-[var(--tessera-border)] text-[0.62rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
                  <th className="px-2 py-1.5 font-medium">{t("col.decidedAt")}</th>
                  <th className="px-2 py-1.5 font-medium">{t("col.id")}</th>
                  <th className="px-2 py-1.5 font-medium">{t("col.agent")}</th>
                  <th className="px-2 py-1.5 font-medium">{t("col.decision")}</th>
                  <th className="px-2 py-1.5 font-medium">{t("col.decidedBy")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((lot) => (
                  <tr
                    key={lot.candidate_id}
                    className="border-b border-[var(--tessera-border)]/60 last:border-0"
                  >
                    <td className="whitespace-nowrap px-2 py-1.5 text-[var(--tessera-text-muted)]">
                      {fmtDecidedAt(lot.decided_at, locale)}
                    </td>
                    <td
                      className="max-w-[190px] truncate px-2 py-1.5 font-mono text-[0.68rem] text-[var(--tessera-fg-info)]"
                      title={lot.title}
                    >
                      {lot.id}
                    </td>
                    <td className="whitespace-nowrap px-2 py-1.5 text-[var(--tessera-text-muted)]">
                      {lot.agent_id}
                    </td>
                    <td className="px-2 py-1.5">
                      <Badge className={DECISION_BADGE[lot.decision]}>
                        {t(`decide.${lot.decision}`)}
                      </Badge>
                    </td>
                    <td className="whitespace-nowrap px-2 py-1.5 text-[var(--tessera-text)]">
                      {lot.owner}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </Zone>
  );
}

function CoverageTab({ t, data }: { t: T; data: Data }) {
  return (
    <Zone label={t("zone.gaps")} info={<ExplainInfo k="zone.gaps" title={t("zone.gaps")} />}>
      <div className="grid gap-3 xl:grid-cols-12">
        <CoverageHeatmap t={t} data={data} className="xl:col-span-5" />
        <Panel
          title={t("panel.distribution")}
          info={<ExplainInfo k="panel.distribution" title={t("panel.distribution")} />}
          className="xl:col-span-4"
        >
          <Donut
            slices={data.candidates_distribution}
            total={data.distribution_total}
            caption="candidats"
            labelOf={(k) => t(`dist.${k}`)}
            showCount
          />
        </Panel>
        <QualitySignals t={t} data={data} className="xl:col-span-3" />
      </div>
    </Zone>
  );
}

function WhyTours({ t, data, className }: { t: T; data: Data; className?: string }) {
  const maxValue = Math.max(...data.why_tours.map((w) => w.value), 1);
  return (
    <Panel
      title={t("panel.whyTours")}
      info={<ExplainInfo k="panel.whyTours" title={t("panel.whyTours")} />}
      className={className}
      action={<ViewAll label={t("viewAll.reasons")} />}
    >
      <SyntheticNotice signalId="curation" compact />
      <table className="w-full border-collapse text-left text-[0.72rem]">
        <thead>
          <tr className="border-b border-[var(--tessera-border)] text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            <th className="px-1.5 py-1 font-medium">{t("whyCol.reason")}</th>
            <th className="px-1.5 py-1 font-medium">{t("whyCol.value")}</th>
            <th className="px-1.5 py-1 text-right font-medium">{t("whyCol.cost")}</th>
          </tr>
        </thead>
        <tbody>
          {data.why_tours.map((w) => (
            <tr key={w.reason} className="border-b border-[var(--tessera-border)]/60 last:border-0">
              <td className="max-w-[180px] truncate px-1.5 py-1.5 text-[var(--tessera-text)]">
                {w.reason}
              </td>
              <td className="px-1.5 py-1.5">
                <div className="flex items-center gap-1.5">
                  <div className="h-[4px] overflow-hidden w-12 rounded-full bg-[var(--tessera-border)]">
                    <div
                      className="h-full rounded-full bg-[#2e72d2]"
                      style={{ width: `${(w.value / maxValue) * 100}%` }}
                    />
                  </div>
                  <span className="tabular-nums text-[var(--tessera-text-muted)]">{w.value}</span>
                </div>
              </td>
              <td className="px-1.5 py-1.5 text-right tabular-nums text-[var(--tessera-text-muted)]">
                {w.cost}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

// ── zone C ───────────────────────────────────────────────────────────────────

function CoverageHeatmap({ t, data, className }: { t: T; data: Data; className?: string }) {
  const { rows, cols, cells } = data.coverage;
  return (
    <Panel
      title={t("panel.coverage")}
      info={<ExplainInfo k="panel.coverage" title={t("panel.coverage")} />}
      className={className}
    >
      <SyntheticNotice signalId="curation" compact />
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-1 text-[0.6rem]">
          <thead>
            <tr>
              <th />
              {cols.map((c) => (
                <th
                  key={c}
                  className="px-0.5 pb-1 text-center font-medium text-[var(--tessera-text-muted)]"
                >
                  {t(`cov.${c}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, ri) => (
              <tr key={r}>
                <td className="whitespace-nowrap pr-1 text-right text-[var(--tessera-text-muted)]">
                  {t(`cov.${r}`)}
                </td>
                {cols.map((c, ci) => (
                  <td key={c} className="p-0">
                    <div
                      className={cn("h-4 w-full rounded-sm", COV_BG[cells[ri]?.[ci] ?? "none"])}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function QualitySignals({ t, data, className }: { t: T; data: Data; className?: string }) {
  return (
    <Panel
      title={t("panel.qualitySignals")}
      info={<ExplainInfo k="panel.qualitySignals" title={t("panel.qualitySignals")} />}
      className={className}
      action={<ViewAll label={t("viewAll.signals")} href="/surveiller/qualite-ia" />}
    >
      <SyntheticNotice signalId="curation" compact />
      <ul className="flex flex-col gap-2">
        {data.quality_signals.map((s) => (
          <li key={s.key} className="flex flex-col gap-1 text-[0.66rem]">
            <div className="flex items-center justify-between gap-1.5">
              <Truncate full={t(`signal.${s.key}`)} className="min-w-0 text-[var(--tessera-text)]">
                {t(`signal.${s.key}`)}
              </Truncate>
              <Badge className={LEVEL_BADGE[s.level]}>{t(`level.${s.level}`)}</Badge>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="h-[4px] overflow-hidden flex-1 rounded-full bg-[var(--tessera-border)]">
                <div
                  className={cn(
                    "h-full rounded-full",
                    s.level === "bon"
                      ? "bg-emerald-400"
                      : s.level === "moyen"
                        ? "bg-amber-400"
                        : "bg-red-400",
                  )}
                  style={{ width: `${s.pct}%` }}
                />
              </div>
              <span className="w-7 shrink-0 text-right tabular-nums text-[var(--tessera-text-muted)]">
                {s.pct}%
              </span>
            </div>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function LinkedDatasets({ t, data, className }: { t: T; data: Data; className?: string }) {
  return (
    <Panel
      title={t("panel.linkedDatasets")}
      info={<ExplainInfo k="panel.linkedDatasets" title={t("panel.linkedDatasets")} />}
      className={className}
      action={<ViewAll label={t("viewAll.datasets")} href="/surveiller/qualite-ia" />}
    >
      <SyntheticNotice signalId="curation" compact />
      <table className="w-full border-collapse text-left text-[0.68rem]">
        <thead>
          <tr className="border-b border-[var(--tessera-border)] text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            <th className="px-1.5 py-1 font-medium">{t("dsCol.dataset")}</th>
            <th className="px-1.5 py-1 font-medium">{t("dsCol.size")}</th>
            <th className="px-1.5 py-1 font-medium">{t("dsCol.updated")}</th>
          </tr>
        </thead>
        <tbody>
          {data.linked_datasets.map((d) => (
            <tr key={d.name} className="border-b border-[var(--tessera-border)]/60 last:border-0">
              <td className="px-1.5 py-1 font-mono text-[0.62rem] text-[var(--tessera-text)]">
                {d.name}
              </td>
              <td className="px-1.5 py-1 tabular-nums text-[var(--tessera-text-muted)]">
                {d.size}
              </td>
              <td className="px-1.5 py-1 text-[var(--tessera-text-muted)]">{d.updated}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

// ── right rail ───────────────────────────────────────────────────────────────

function CurationRail({ t, data }: { t: T; data: Data }) {
  const tc = useTranslations("common");
  return (
    <aside className="flex min-w-0 flex-col gap-3">
      <SyntheticNotice signalId="curation" compact />
      <Panel
        title={t("panel.workflow")}
        info={<ExplainInfo k="panel.workflow" title={t("panel.workflow")} />}
        action={<ViewAll label={t("viewAll.workflow")} />}
      >
        <ul className="flex flex-col gap-1.5">
          {data.workflow.map((w) => (
            <li key={w.step} className="flex items-center gap-2 text-[0.7rem]">
              <Truncate full={w.step} className="min-w-0 flex-1 text-[var(--tessera-text)]">
                {w.step}
              </Truncate>
              <span className="font-mono tabular-nums text-[var(--tessera-text-muted)]">
                {w.qty}
              </span>
              <span className={cn("w-16 text-right font-medium", WF_TEXT[w.status])}>
                {t(`wfStatus.${w.status}`)}
              </span>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel
        title={t("panel.release")}
        info={<ExplainInfo k="panel.release" title={t("panel.release")} />}
        action={<ViewAll label={t("release.viewDetail")} href="/agir/release-control" />}
      >
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2 text-[0.72rem]">
            <span className="font-mono text-[var(--tessera-fg-info)]">{data.release.id}</span>
            <Badge className="border-emerald-500/30 bg-emerald-500/15 text-emerald-300">
              {data.release.status}
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[0.66rem] text-[var(--tessera-text-muted)]">
              {t("release.readiness")}
            </span>
            <div className="h-[4px] overflow-hidden flex-1 rounded-full bg-[var(--tessera-border)]">
              <div
                className="h-full rounded-full bg-emerald-400"
                style={{ width: `${data.release.readiness}%` }}
              />
            </div>
            <span className="tabular-nums text-[var(--tessera-text)]">
              {data.release.readiness}%
            </span>
          </div>
        </div>
      </Panel>

      <Panel
        title={t("panel.linkedEvidence")}
        info={<ExplainInfo k="panel.linkedEvidence" title={t("panel.linkedEvidence")} />}
      >
        <div className="flex flex-col gap-2 text-[0.72rem]">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[var(--tessera-text-muted)]">{t("evidence.currentCohort")}</span>
            <span className="font-mono text-[0.66rem] text-[var(--tessera-text)]">
              {data.cohort}
            </span>
          </div>
          <Link
            href="/prouver/evidence-store"
            className="inline-flex h-8 w-full items-center justify-center gap-2 rounded-md border border-[#5b4bbd] bg-[#4c3fb0]/40 text-xs text-[var(--tessera-fg-accent)] transition-colors hover:bg-[#4c3fb0]/60"
          >
            <FileSearch className="h-3.5 w-3.5" /> {t("evidence.openPack")}
          </Link>
        </div>
      </Panel>

      <Panel
        title={t("panel.owners")}
        info={<ExplainInfo k="panel.owners" title={t("panel.owners")} />}
      >
        <table className="w-full border-collapse text-left text-[0.68rem]">
          <thead>
            <tr className="text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              <th className="pb-1 font-medium">{t("ownerCol.role")}</th>
              <th className="pb-1 text-center font-medium">{t("ownerCol.required")}</th>
              <th className="pb-1 text-center font-medium">{t("ownerCol.assigned")}</th>
              <th className="pb-1 text-right font-medium">{t("ownerCol.status")}</th>
            </tr>
          </thead>
          <tbody>
            {data.owners.map((o) => (
              <tr key={o.role}>
                <td className="py-0.5 text-[var(--tessera-text)]">{o.role}</td>
                <td className="py-0.5 text-center tabular-nums text-[var(--tessera-text-muted)]">
                  {o.required}
                </td>
                <td className="py-0.5 text-center tabular-nums text-[var(--tessera-text-muted)]">
                  {o.assigned}
                </td>
                <td className="py-0.5 text-right">
                  <span
                    className={
                      o.status === "ok"
                        ? "text-[var(--tessera-fg-success)]"
                        : "text-[var(--tessera-fg-warning)]"
                    }
                  >
                    {t(`ownerStatus.${o.status}`)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <Panel title={t("panel.quickActions")}>
        <ul className="flex flex-col gap-1">
          {/* filterSensitivity/openCatalog need their mutation/catalog target (a later
              lot) — disabled with the reason; the evidence pack navigates for real. */}
          {(
            [
              { key: "filterSensitivity", icon: Filter },
              { key: "openCatalog", icon: ListChecks },
              { key: "evidencePack", icon: FileSearch, href: "/prouver/evidence-store" },
            ] as { key: string; icon: typeof Filter; href?: Route }[]
          ).map((q) => (
            <li key={q.key}>
              {q.href ? (
                <Link
                  href={q.href}
                  className="flex w-full items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1.5 text-left text-[0.68rem] transition-colors hover:bg-[var(--tessera-muted)]"
                >
                  <q.icon className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-green)]" />
                  <Truncate
                    full={t(`quick.${q.key}`)}
                    className="min-w-0 flex-1 text-[var(--tessera-text)]"
                  >
                    {t(`quick.${q.key}`)}
                  </Truncate>
                </Link>
              ) : (
                <button
                  type="button"
                  disabled
                  title={tc("notWired")}
                  className="flex w-full cursor-not-allowed items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1.5 text-left text-[0.68rem] opacity-60"
                >
                  <q.icon className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)]" />
                  <span className="min-w-0 flex-1 truncate text-[var(--tessera-text-muted)]">
                    {t(`quick.${q.key}`)}
                  </span>
                </button>
              )}
            </li>
          ))}
        </ul>
      </Panel>
    </aside>
  );
}

// ── zone D ───────────────────────────────────────────────────────────────────

function ActionCard({ action, t }: { action: Data["actions"][number]; t: T }) {
  const Icon = ACTION_ICONS[action.key as keyof typeof ACTION_ICONS] ?? PlayCircle;
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <Icon className="h-4 w-4 text-[var(--tessera-green)]" />
      <p className="text-[0.74rem] font-medium leading-snug text-[var(--tessera-text)]">
        {t(`action.${action.key}`)}
      </p>
      <div className="mt-auto flex flex-wrap items-center gap-1">
        {action.role ? (
          <Badge className="border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]">
            {action.role}
          </Badge>
        ) : null}
        {action.requirement ? (
          <Badge className="border-amber-500/30 bg-amber-500/15 text-amber-300">
            {action.requirement === "dual" ? t("actCtrl.dualControl") : t("actCtrl.signature")}
          </Badge>
        ) : null}
      </div>
    </div>
  );
}

function RecentActivity({
  t,
  data,
  className,
  onViewAll,
}: { t: T; data: Data; className?: string; onViewAll?: () => void }) {
  return (
    <Panel
      title={t("panel.recentActivity")}
      info={<ExplainInfo k="panel.recentActivity" title={t("panel.recentActivity")} />}
      className={className}
      action={<ViewAll label={t("viewAll.activities")} onClick={onViewAll} />}
    >
      <table className="w-full border-collapse text-left text-[0.7rem]">
        <thead>
          <tr className="border-b border-[var(--tessera-border)] text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            <th className="px-1.5 py-1 font-medium">{t("actCol.time")}</th>
            <th className="px-1.5 py-1 font-medium">{t("actCol.action")}</th>
            <th className="px-1.5 py-1 font-medium">{t("actCol.actor")}</th>
          </tr>
        </thead>
        <tbody>
          {data.recent_activity.map((a, i) => (
            <tr
              key={`${a.time}-${a.action}-${i}`}
              className="border-b border-[var(--tessera-border)]/60 last:border-0"
            >
              <td className="px-1.5 py-1 font-mono tabular-nums text-[var(--tessera-text-muted)]">
                {a.time}
              </td>
              <td className="px-1.5 py-1 text-[var(--tessera-text)]">{a.action}</td>
              <td className="px-1.5 py-1 text-[var(--tessera-text-muted)]">{a.actor}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

// ── zone E ───────────────────────────────────────────────────────────────────

function BacklogTrend({ t, data, className }: { t: T; data: Data; className?: string }) {
  const b = data.backlog_trend;
  return (
    <Panel
      title={t("panel.backlogTrend")}
      info={<ExplainInfo k="panel.backlogTrend" title={t("panel.backlogTrend")} />}
      className={className}
    >
      <div className="h-[120px]">
        <StretchChart
          title={t("panel.backlogTrend")}
          lines={[
            { points: b.total, color: "#60a5fa" },
            { points: b.to_curate, color: "#fbbf24" },
            { points: b.promotable, color: "#34d399" },
            { points: b.rejected, color: "#f87171" },
          ]}
          ticks={b.labels}
        />
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[0.58rem] text-[var(--tessera-text-muted)]">
        <Legend color="#60a5fa" label={t("backlogLegend.total")} />
        <Legend color="#fbbf24" label={t("backlogLegend.toCurate")} />
        <Legend color="#34d399" label={t("backlogLegend.promotable")} />
        <Legend color="#f87171" label={t("backlogLegend.rejected")} />
      </div>
    </Panel>
  );
}

function BalanceChart({ t, data, className }: { t: T; data: Data; className?: string }) {
  const b = data.balance;
  return (
    <Panel
      title={t("panel.balance")}
      info={<ExplainInfo k="panel.balance" title={t("panel.balance")} />}
      className={className}
    >
      <div className="flex h-[120px] items-end gap-1.5">
        {b.labels.map((l, i) => {
          const promote = b.promote[i] ?? 0;
          const review = b.review[i] ?? 0;
          const reject = b.reject[i] ?? 0;
          const total = promote + review + reject || 1;
          return (
            <div key={l} className="flex h-full min-w-0 flex-1 flex-col justify-end">
              <div className="flex h-full flex-col overflow-hidden rounded-sm">
                <div style={{ height: `${(promote / total) * 100}%`, background: "#34d399" }} />
                <div style={{ height: `${(review / total) * 100}%`, background: "#fbbf24" }} />
                <div style={{ height: `${(reject / total) * 100}%`, background: "#f87171" }} />
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-1 flex flex-wrap items-center justify-between">
        <div className="flex gap-1.5 pl-0 text-[0.55rem] tabular-nums text-[var(--tessera-text-muted)]">
          {b.labels.map((l) => (
            <span key={l} className="flex-1 text-center">
              {l.slice(0, 5)}
            </span>
          ))}
        </div>
      </div>
      <div className="mt-0.5 flex flex-wrap gap-x-3 text-[0.58rem] text-[var(--tessera-text-muted)]">
        <Legend color="#34d399" label={t("balanceLegend.promote")} />
        <Legend color="#fbbf24" label={t("balanceLegend.review")} />
        <Legend color="#f87171" label={t("balanceLegend.reject")} />
      </div>
    </Panel>
  );
}

function ImpactPanel({ t, data, className }: { t: T; data: Data; className?: string }) {
  const im = data.impact;
  return (
    <Panel
      title={t("panel.impact")}
      info={<ExplainInfo k="panel.impact" title={t("panel.impact")} />}
      className={className}
      action={<ViewAll label={t("impact.viewDetail")} />}
    >
      <div className="flex items-stretch gap-3">
        <div className="flex flex-1 items-end justify-around gap-2">
          {[
            { v: im.current_val, label: t("impact.before"), color: "#64748b", val: im.current },
            { v: im.projected_val, label: t("impact.after"), color: "#2e72d2", val: im.projected },
          ].map((bar) => (
            <div
              key={bar.label}
              className="flex h-[90px] flex-1 flex-col items-center justify-end gap-1"
            >
              <span className="text-[0.7rem] font-semibold tabular-nums text-[var(--tessera-text-strong)]">
                {bar.val}
              </span>
              <div
                className="w-full rounded-t-sm"
                style={{ height: `${bar.v}%`, background: bar.color }}
              />
              <span className="text-[0.55rem] text-[var(--tessera-text-muted)]">{bar.label}</span>
            </div>
          ))}
        </div>
        <dl className="flex w-[42%] shrink-0 flex-col justify-center gap-1.5 border-l border-[var(--tessera-border)] pl-3 text-[0.68rem]">
          <KV label={t("impact.currentRate")} value={im.current} />
          <KV label={t("impact.projectedRate")} value={im.projected} />
          <KV
            label={t("impact.expectedDelta")}
            value={im.delta}
            tone="text-[var(--tessera-fg-success)]"
          />
        </dl>
      </div>
    </Panel>
  );
}

// ── footer ───────────────────────────────────────────────────────────────────

function Footer({ t, data }: { t: T; data: Data }) {
  const f = data.footer;
  return (
    <footer className="flex shrink-0 flex-wrap items-center gap-x-5 gap-y-1 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
      <Chip icon={GitBranch} label={t("footer.release", { id: f.release })} />
      <Chip icon={ShieldCheck} tone="text-[var(--tessera-green)]" label={t("footer.chain")} />
      <Chip icon={Database} label={t("footer.source", { src: f.source })} />
      <Chip icon={Activity} label={t("footer.sync", { ago: f.sync })} />
    </footer>
  );
}

// ── atoms ────────────────────────────────────────────────────────────────────

function Zone({ label, info, children }: { label: string; info?: ReactNode; children: ReactNode }) {
  return (
    <section
      data-slot="card"
      className="shrink-0 rounded-xl border border-[var(--tessera-border)]/60 bg-[var(--tessera-surface)]/20 p-2.5"
    >
      <h2 className="mb-2 flex items-center gap-1 text-[0.7rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
        {label}
        {info}
      </h2>
      {children}
    </section>
  );
}

function Panel({
  title,
  info,
  action,
  children,
  className,
}: {
  title: string;
  info?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      data-slot="card"
      className={cn(
        "flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3",
        className,
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="flex min-w-0 items-center gap-1 text-[0.8rem] font-semibold text-[var(--tessera-text)]">
          <Truncate full={title} className="min-w-0">
            {title}
          </Truncate>
          {info}
        </h3>
        {action}
      </div>
      <div className="min-h-0 flex-1">{children}</div>
    </div>
  );
}

function KpiTile({
  kpi,
  label,
  vs,
  info,
}: { kpi: Data["kpis"][number]; label: string; vs: string; info?: ReactNode }) {
  const up = kpi.delta_label.trim().startsWith("+");
  const good = up === kpi.good_is_up;
  const magnitude = kpi.delta_label.replace(/^[+-]\s*/, "");
  return (
    <div
      data-slot="card"
      className="flex h-[104px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3"
    >
      <p className="flex items-center gap-1 text-[0.7rem] font-medium text-[var(--tessera-text-muted)]">
        <Truncate full={label} className="min-w-0">
          {label}
        </Truncate>
        {info}
      </p>
      <div className="mt-1 flex items-center gap-2">
        <span className="whitespace-nowrap text-[1.5rem] font-semibold leading-none text-[var(--tessera-text-strong)]">
          {kpi.value}
        </span>
        <MetricSparkline
          className="h-6 min-w-0 flex-1"
          values={kpi.series}
          tone={kpi.good_is_up ? "success" : "danger"}
        />
      </div>
      <div className="mt-auto flex items-center gap-1 whitespace-nowrap text-[0.62rem] font-medium">
        <span className={good ? "text-[var(--tessera-green)]" : "text-[var(--tessera-fg-danger)]"}>
          {up ? "▲" : "▼"} {magnitude}
        </span>
        <span className="text-[var(--tessera-text-muted)]">{vs}</span>
      </div>
    </div>
  );
}

function Donut({
  slices,
  total,
  caption,
  labelOf,
  showCount,
}: {
  slices: Data["candidates_distribution"];
  total: number;
  caption: string;
  labelOf: (key: string) => string;
  showCount?: boolean;
}) {
  const sum = slices.reduce((s, x) => s + x.count, 0) || 1;
  const R = 39;
  const C = 2 * Math.PI * R;
  let off = 0;
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-[104px] w-[104px] shrink-0">
        <svg viewBox="0 0 104 104" className="h-full w-full -rotate-90" aria-hidden="true">
          <circle
            cx="52"
            cy="52"
            r={R}
            fill="none"
            stroke="var(--tessera-border)"
            strokeWidth="9"
          />
          {slices.map((s) => {
            const frac = s.count / sum;
            const seg = { dash: frac * C, gap: C - frac * C, o: -off * C };
            off += frac;
            return (
              <circle
                key={s.key}
                cx="52"
                cy="52"
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
        <div className="absolute inset-0 flex flex-col items-center justify-center overflow-hidden">
          <span className="max-w-[49px] truncate text-base font-semibold leading-none tabular-nums text-[var(--tessera-text-strong)]">
            {total}
          </span>
          <span className="line-clamp-2 max-w-[49px] break-words text-center text-[0.46rem] uppercase leading-tight text-[var(--tessera-text-muted)]">
            {caption}
          </span>
        </div>
      </div>
      <ul className="flex min-w-0 flex-1 flex-col gap-0.5 text-[0.64rem]">
        {slices.map((s) => (
          <li key={s.key} className="flex flex-col gap-0.5">
            <span className="flex min-w-0 items-center gap-1">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: s.color }} />
              <Truncate full={labelOf(s.key)} className="min-w-0 text-[var(--tessera-text)]">
                {labelOf(s.key)}
              </Truncate>
            </span>
            <span className="pl-2.5 tabular-nums text-[var(--tessera-text-muted)]">
              {showCount ? `${s.count} · ` : ""}
              {s.pct}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const DECIDE_TONE: Record<"emerald" | "amber" | "red", { active: string; idle: string }> = {
  emerald: {
    active: "border-emerald-500/50 bg-emerald-500/25 text-emerald-200",
    idle: "border-[var(--tessera-border)] text-[var(--tessera-text-muted)] hover:border-emerald-500/40 hover:text-[var(--tessera-fg-success)]",
  },
  amber: {
    active: "border-amber-500/50 bg-amber-500/25 text-amber-200",
    idle: "border-[var(--tessera-border)] text-[var(--tessera-text-muted)] hover:border-amber-500/40 hover:text-[var(--tessera-fg-warning)]",
  },
  red: {
    active: "border-red-500/50 bg-red-500/25 text-red-200",
    idle: "border-[var(--tessera-border)] text-[var(--tessera-text-muted)] hover:border-red-500/40 hover:text-[var(--tessera-fg-danger)]",
  },
};

function DecideButton({
  icon: Icon,
  label,
  active,
  tone,
  disabled,
  onClick,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  active: boolean;
  tone: "emerald" | "amber" | "red";
  disabled: boolean;
  onClick: () => void;
}) {
  const c = DECIDE_TONE[tone];
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      aria-pressed={active}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "inline-flex h-6 w-6 items-center justify-center rounded border transition-colors disabled:cursor-not-allowed disabled:opacity-40",
        active ? c.active : c.idle,
      )}
    >
      <Icon className="h-3.5 w-3.5" />
    </button>
  );
}

function Badge({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded border px-1.5 py-0.5 text-[0.58rem] font-medium",
        className,
      )}
    >
      {children}
    </span>
  );
}

function KV({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[var(--tessera-text-muted)]">{label}</span>
      <span className={cn("tabular-nums text-[var(--tessera-text)]", tone)}>{value}</span>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1">
      <span className="h-1 w-3 rounded-full" style={{ background: color }} /> {label}
    </span>
  );
}

/** Panel action affordance: a Link when it has a target, a button when it has a
 *  handler, nothing otherwise — never a dead button. */
function ViewAll({ label, href, onClick }: { label: string; href?: Route; onClick?: () => void }) {
  const cls =
    "flex shrink-0 items-center gap-0.5 text-[0.66rem] font-medium text-[var(--tessera-fg-info)] hover:text-[var(--tessera-fg-info)]";
  if (href) {
    return (
      <Link href={href} className={cls}>
        {label} <ChevronRight className="h-3 w-3" />
      </Link>
    );
  }
  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={cls}>
        {label} <ChevronRight className="h-3 w-3" />
      </button>
    );
  }
  return null;
}

function Chip({
  icon: Icon,
  label,
  tone,
}: { icon: typeof Activity; label: string; tone?: string }) {
  return (
    <span className="flex min-w-0 items-center gap-1.5 whitespace-nowrap">
      <Icon className={cn("h-3.5 w-3.5 shrink-0", tone)} />
      <Truncate full={label}>{label}</Truncate>
    </span>
  );
}
