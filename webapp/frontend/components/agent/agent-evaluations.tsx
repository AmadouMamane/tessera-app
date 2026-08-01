"use client";

import { useQuery } from "@tanstack/react-query";
import {
  BarChart3,
  CalendarClock,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  GitCompare,
  Layers,
  type LucideIcon,
  Play,
  Plus,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Target,
  X,
} from "lucide-react";
import type { Route } from "next";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { CardInfo } from "@/components/cockpit/card-info";
import {
  TemporalRail,
  useRailTimeline,
  useTemporalState,
} from "@/components/overview/temporal-rail";
import { Truncate } from "@/components/ui/truncate";
import { Link } from "@/i18n/navigation";
import { agentPath } from "@/lib/agent-context";
import { fetchAgentEvaluations, requestAgentRelease } from "@/lib/api/client";
import type { AgentEvaluations as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import { useAgentId } from "@/lib/use-agent-id";
import { AgentSubtabs } from "./agent-subtabs";
import { EvaluationRunRail } from "./evaluation-run-rail";
import { ComparaisonsTab, ExportsTab, ResultsTab, SetsTab, VersionsTab } from "./evaluation-tabs";

type RowT = NonNullable<Data["table"]>["rows"][number];

// Inline locale pick for the handful of strings this component computes itself
// (the backend payload is already localized; these are the client-side bits).
function pick(locale: string, fr: string, de: string, en: string): string {
  return locale === "de" ? de : locale === "en" ? en : fr;
}

const KPI_ICONS: LucideIcon[] = [Sparkles, Target, ShieldCheck, BarChart3, Layers, Target];
const TYPE_TONE: Record<string, string> = {
  sys: "border-violet-500/30 bg-violet-500/15 text-[var(--tessera-fg-accent)]",
  tpl: "border-sky-500/30 bg-sky-500/15 text-[var(--tessera-fg-info)]",
  agt: "border-emerald-500/30 bg-emerald-500/15 text-[var(--tessera-fg-success)]",
};
const STATUS_TONE: Record<string, string> = {
  good: "text-[var(--tessera-fg-success)]",
  info: "text-[var(--tessera-fg-info)]",
  off: "text-[var(--tessera-text-muted)]",
};
const STATUS_DOT: Record<string, string> = {
  good: "bg-emerald-400",
  info: "bg-sky-400",
  off: "bg-slate-500",
};
const TONE_TEXT: Record<string, string> = {
  good: "text-[var(--tessera-fg-success)]",
  bad: "text-[var(--tessera-fg-danger)]",
  muted: "text-[var(--tessera-text-muted)]",
};
const WATCH_DOT: Record<string, string> = {
  warn: "bg-amber-400",
  info: "bg-sky-400",
  crit: "bg-red-400",
};
const PER_PAGE_OPTS = [10, 25, 50];
const MAX_PAGE_BUTTONS = 5;
const NUMERIC_COLS = new Set([4, 5, 6, 9]);
// AGENT-scoped targets depend on the active agent; GOUVERNER targets are global.
const quickHref = (agentId: string): Record<string, Route> => ({
  run: "/agir/curation-eval-set" as Route,
  compare: "/prouver/etat-a-date" as Route,
  results: agentPath(agentId, "historique") as Route,
  sets: "/agir/curation-eval-set" as Route,
});

function useDismiss(open: boolean, onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);
  return ref;
}

function rowSortKey(r: RowT, col: number): string | number {
  switch (col) {
    case 0:
      return r.name;
    case 1:
      return r.type;
    case 2:
      return r.status;
    case 3:
      return r.version;
    case 4:
      return r.score_num;
    case 5:
      return r.pass_rate;
    case 6:
      return r.is_fact && r.total ? r.failed / r.total : -1;
    case 7:
      return r.last_run;
    case 8:
      return r.owner;
    case 9:
      return r.total;
    default:
      return r.name;
  }
}

function compareRows(a: RowT, b: RowT, col: number, dir: "asc" | "desc"): number {
  const av = rowSortKey(a, col);
  const bv = rowSortKey(b, col);
  const cmp = NUMERIC_COLS.has(col)
    ? Number(av) - Number(bv)
    : String(av).localeCompare(String(bv), "fr");
  return dir === "asc" ? cmp : -cmp;
}

export function AgentEvaluations() {
  const t = useTranslations("agentEvaluations");
  const locale = useLocale();
  const temporal = useTemporalState();
  const railTimeline = useRailTimeline();
  const [subtab, setSubtab] = useState("");
  const agentId = useAgentId();
  const { data } = useQuery({
    queryKey: ["agent-evaluations", agentId, locale],
    queryFn: ({ signal }) => fetchAgentEvaluations(agentId, locale, signal),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  if (!data?.available) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        {data ? t("unavailable") : t("loading")}
      </div>
    );
  }

  const a = data.actions;
  const subtabs = data.subtabs ?? [];
  const active = subtab || subtabs[0] || "";
  // Gate by INDEX, not label: `active` and `subtabs[i]` are the same localized
  // string, so index comparison is locale-safe (a hardcoded FR compare would not).
  const activeIdx = Math.max(0, subtabs.indexOf(active));

  return (
    <div className="flex flex-col gap-2.5 pb-2 text-[var(--tessera-text)]">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <button
          type="button"
          onClick={() => {
            setSubtab(subtabs[0] ?? "");
            temporal.changeMode("history");
          }}
          className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          <CalendarClock className="h-4 w-4" /> {a?.asof}
        </button>
        <Link
          href={"/agir/curation-eval-set" as Route}
          className="flex h-9 items-center gap-2 rounded-md border border-[#7c5cf5] bg-[#6d4aed] px-3 text-xs font-medium text-white hover:bg-[#7c5cf5]"
        >
          <Plus className="h-4 w-4" /> {a?.create}
        </Link>
      </div>

      <AgentSubtabs tabs={subtabs} active={active} onSelect={setSubtab} />

      {activeIdx === 0 ? (
        <OverviewTab data={data} temporal={temporal} railTimeline={railTimeline} />
      ) : null}
      {activeIdx === 1 ? <SetsTab data={data} /> : null}
      {activeIdx === 2 ? <ResultsTab data={data} mode="all" /> : null}
      {activeIdx === 3 ? <DimensionsTab data={data} /> : null}
      {activeIdx === 4 ? <ComparaisonsTab data={data} /> : null}
      {activeIdx === 5 ? <ResultsTab data={data} mode="failed" /> : null}
      {activeIdx === 6 ? <VersionsTab data={data} /> : null}
      {activeIdx === 7 ? <ExportsTab data={data} /> : null}
    </div>
  );
}

/** Vue d'ensemble: the gate-centric executive view. The per-category table moved
 *  to Dimensions; the run journal + judged metrics stay here as a summary. */
function OverviewTab({
  data,
  temporal,
  railTimeline,
}: {
  data: Data;
  temporal: ReturnType<typeof useTemporalState>;
  railTimeline: ReturnType<typeof useRailTimeline>;
}) {
  const t = useTranslations("agentEvaluations");
  const locale = useLocale();
  return (
    <div className="flex flex-col gap-2.5">
      {/* Verdict leads, with cross-links inline + remediation in the banner. */}
      <VerdictBanner data={data} />
      <LiensUtiles />

      {/* Cycle de vie + active snapshot, side by side (dense, normative order). */}
      <div className="grid gap-2.5 xl:grid-cols-2">
        <LifecycleBar data={data} />
        <Snapshot data={data} onAsof={() => temporal.changeMode("history")} />
      </div>

      {/* Scores right under the verdict — informative, never the verdict. */}
      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
        {(data.kpis ?? []).map((k, i) => (
          <Kpi key={k.key} kpi={k} Icon={KPI_ICONS[i % KPI_ICONS.length] ?? Sparkles} />
        ))}
      </div>
      <p className="-mt-1 text-[10px] text-[var(--tessera-text-muted)]">
        {locale === "de" ? (
          <>
            <span className="font-medium">Informative</span> Scores — sie bestimmen nicht das
            Gate-Urteil (nicht ausnehmbarer Kern + Sockel; vgl. eval-gate-policy §6).
          </>
        ) : locale === "en" ? (
          <>
            <span className="font-medium">Informative</span> scores — they do not determine the gate
            verdict (non-waivable core + socle; cf. eval-gate-policy §6).
          </>
        ) : (
          <>
            Scores <span className="font-medium">informatifs</span> — ils ne déterminent pas le
            verdict du gate (cœur non dérogeable + socle ; cf. eval-gate-policy §6).
          </>
        )}
      </p>

      <GatePolicySection data={data} />

      <TemporalRail
        mode={temporal.mode}
        liveStatus={t("realtime")}
        timeline={railTimeline.data}
        selectedAt={temporal.selectedAt}
        onSelectedAtChange={temporal.setSelectedAt}
        periodKey={temporal.periodKey}
        onPeriodChange={temporal.setPeriodKey}
        windowEnd={temporal.windowEnd}
        onPickDate={temporal.pickDate}
        onModeChange={temporal.changeMode}
      />

      {/* ER-01 (S3/C2): the run journal — distinct from the SR-01 signal scrubber above. */}
      <div className="grid gap-2.5 xl:grid-cols-12">
        <EvaluationRunRail data={data} className="xl:col-span-8" />
        <JudgeMetrics data={data} className="xl:col-span-4" />
      </div>

      <div className="grid gap-2.5 md:grid-cols-3">
        <Watch data={data} />
        <Quick data={data} />
        <Trend data={data} />
      </div>
    </div>
  );
}

/** Dimensions: the per-category evaluation table (pass rate by dimension) with
 *  the full Connaissances treatment — filters, sortable headers, pagination and
 *  a row-click detail panel. Owns its own table state. */
function DimensionsTab({ data }: { data: Data }) {
  const locale = useLocale();
  const [search, setSearch] = useState("");
  const [typeKey, setTypeKey] = useState("all");
  const [qualityKey, setQualityKey] = useState("all");
  const [hallucKey, setHallucKey] = useState("all");
  const [sortCol, setSortCol] = useState<number | null>(4);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const [selected, setSelected] = useState<string | null>(null);

  const allRows = data.table?.rows ?? [];
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return allRows.filter((r) => {
      if (typeKey !== "all" && r.type !== typeKey) return false;
      if (qualityKey !== "all" && r.quality_key !== qualityKey) return false;
      if (hallucKey === "with" && !r.is_fact) return false;
      if (hallucKey === "without" && r.is_fact) return false;
      if (q && !`${r.name} ${r.type} ${r.category_key}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [allRows, search, typeKey, qualityKey, hallucKey]);

  const sorted = useMemo(() => {
    if (sortCol === null) return filtered;
    return [...filtered].sort((a, b) => compareRows(a, b, sortCol, sortDir));
  }, [filtered, sortCol, sortDir]);

  const total = sorted.length;
  const totalPages = Math.max(1, Math.ceil(total / perPage));
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset to page 1 on any filter/sort change
  useEffect(() => setPage(1), [search, typeKey, qualityKey, hallucKey, sortCol, sortDir, perPage]);
  const safePage = Math.min(page, totalPages);
  const startIdx = (safePage - 1) * perPage;
  const pageRows = sorted.slice(startIdx, startIdx + perPage);
  const selectedRow = sorted.find((r) => r.name === selected) ?? pageRows[0] ?? allRows[0] ?? null;

  const resetFilters = useCallback(() => {
    setSearch("");
    setTypeKey("all");
    setQualityKey("all");
    setHallucKey("all");
  }, []);

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex flex-col gap-0.5">
        <h2 className="text-[0.95rem] font-semibold text-[var(--tessera-text)]">
          {pick(locale, "Dimensions", "Dimensionen", "Dimensions")}
        </h2>
        <p className="text-[0.72rem] text-[var(--tessera-text-muted)]">
          {pick(
            locale,
            "Taux de réussite par catégorie du catalogue et métriques du juge.",
            "Erfolgsrate je Katalogkategorie und Richter-Metriken.",
            "Pass rate per catalogue category and judge metrics.",
          )}
        </p>
      </div>
      <div className="grid gap-2.5 xl:grid-cols-12">
        <div className="flex min-w-0 flex-col gap-2.5 xl:col-span-8">
          <Filters
            data={data}
            search={search}
            setSearch={setSearch}
            typeKey={typeKey}
            setTypeKey={setTypeKey}
            qualityKey={qualityKey}
            setQualityKey={setQualityKey}
            hallucKey={hallucKey}
            setHallucKey={setHallucKey}
            onReset={resetFilters}
          />
          <RunsTable
            data={data}
            rows={pageRows}
            total={total}
            selected={selectedRow?.name ?? null}
            onSelect={setSelected}
            sortCol={sortCol}
            sortDir={sortDir}
            onSort={(col) => {
              if (col === sortCol) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
              else {
                setSortCol(col);
                setSortDir("asc");
              }
            }}
            page={safePage}
            totalPages={totalPages}
            start={total === 0 ? 0 : startIdx + 1}
            end={Math.min(startIdx + perPage, total)}
            perPage={perPage}
            onPage={setPage}
            onPerPage={setPerPage}
          />
          <JudgeMetrics data={data} />
        </div>
        <Detail data={data} row={selectedRow} className="xl:col-span-4" />
      </div>
    </div>
  );
}

function pct(value: number | null | undefined): string {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "—";
}

function ReleaseControl() {
  const locale = useLocale();
  const agentId = useAgentId();
  const [state, setState] = useState<"idle" | "pending" | "done">("idle");
  const [result, setResult] = useState<{ allowed: boolean; reason: string } | null>(null);

  async function onClick() {
    setState("pending");
    try {
      const r = await requestAgentRelease(agentId);
      setResult({ allowed: r.allowed, reason: r.reason });
    } catch {
      setResult({
        allowed: false,
        reason: pick(
          locale,
          "échec de la demande de mise en prod.",
          "Produktionsfreigabe-Anfrage fehlgeschlagen.",
          "production release request failed.",
        ),
      });
    } finally {
      setState("done");
    }
  }

  return (
    <div className="mt-1 flex flex-col gap-1">
      <button
        type="button"
        onClick={onClick}
        disabled={state === "pending"}
        className="self-start rounded-md border border-current px-2 py-1 text-[11px] font-medium hover:opacity-80 disabled:opacity-50"
      >
        {pick(
          locale,
          "Promouvoir en prod (gated)",
          "In Produktion freigeben (gated)",
          "Promote to prod (gated)",
        )}
      </button>
      {result ? (
        <span className="text-[10px] opacity-90">
          {result.allowed
            ? pick(locale, "✓ Promu (live)", "✓ Freigegeben (live)", "✓ Promoted (live)")
            : pick(locale, "✗ Bloqué", "✗ Blockiert", "✗ Blocked")}{" "}
          — {result.reason}
        </span>
      ) : null}
    </div>
  );
}

/** P5 — release lifecycle bar: candidat → déployé → cible, + run environment,
 *  model, run-id and period. Real data (gate.candidate, meta.model, the run
 *  timestamp); the **deployed** version has no real release pointer yet, so it
 *  renders an honest empty state — never a fabricated REL. */
function fmtRunStamp(stamp: string): string {
  // "20260618T083906Z" → "18/06/2026 08:39 UTC"
  const m = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})/.exec(stamp);
  if (!m) return stamp || "—";
  return `${m[3]}/${m[2]}/${m[1]} ${m[4]}:${m[5]} UTC`;
}

function LifecycleBar({ data }: { data: Data }) {
  const locale = useLocale();
  const gate = data.gate;
  const meta = data.meta;
  const candidate = gate?.candidate ?? "";
  const cells: { label: string; value: string; tone?: "muted" }[] = [
    {
      label: pick(locale, "Candidat (run-id)", "Kandidat (Run-ID)", "Candidate (run-id)"),
      value: candidate || "—",
    },
    // No deployed-release pointer exists yet → honest empty, not a fabricated REL.
    {
      label: pick(locale, "Version déployée", "Bereitgestellte Version", "Deployed version"),
      value: pick(
        locale,
        "Aucune release déployée",
        "Keine Release bereitgestellt",
        "No release deployed",
      ),
      tone: "muted",
    },
    { label: pick(locale, "Cible", "Ziel", "Target"), value: "Production" },
    {
      label: pick(locale, "Env du run", "Lauf-Umgebung", "Run env"),
      value: pick(locale, "Préprod d'évaluation", "Evaluierungs-Preprod", "Evaluation preprod"),
    },
    {
      label: pick(locale, "Modèle évalué", "Evaluiertes Modell", "Evaluated model"),
      value: meta?.model ?? "—",
    },
    {
      label: pick(locale, "Période du run", "Lauf-Zeitraum", "Run period"),
      value: candidate ? fmtRunStamp(candidate) : "—",
    },
  ];
  const title = pick(locale, "Cycle de vie", "Lebenszyklus", "Lifecycle");
  return (
    <section className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2">
      <span className="flex items-center gap-1 text-[10px] uppercase tracking-wide text-[var(--tessera-fg-accent)]">
        {title}
        <CardInfo ns="agentEvaluations" k="lifecycle" title={title} />
      </span>
      {cells.map((c) => (
        <div key={c.label} className="flex flex-col gap-0.5">
          <span className="text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            {c.label}
          </span>
          <span
            className={`text-[0.8rem] font-medium tabular-nums ${
              c.tone === "muted" ? "text-[var(--tessera-text-muted)]" : "text-[var(--tessera-text)]"
            }`}
          >
            {c.value}
          </span>
        </div>
      ))}
    </section>
  );
}

/** P3 — cross-links making the control plane navigable: definition (CONFIGURER),
 *  governance (AGIR Release Control), linked data (applied garde-fous, knowledge). */
function LiensUtiles() {
  const locale = useLocale();
  const agentId = useAgentId();
  const items: { href: Route; label: string }[] = [
    {
      href: `/agir/release-control?agent=${agentId}` as Route,
      label: pick(
        locale,
        "Gouvernance · Release Control",
        "Governance · Release Control",
        "Governance · Release Control",
      ),
    },
    {
      href: "/configurer/parametres" as Route,
      label: pick(
        locale,
        "Définition · jeu d'éval (CONFIGURER)",
        "Definition · Eval-Set (KONFIGURIEREN)",
        "Definition · eval set (CONFIGURE)",
      ),
    },
    {
      href: agentPath(agentId, "garde-fous") as Route,
      label: pick(locale, "Garde-fous appliqués", "Angewandte Schutzregeln", "Applied guardrails"),
    },
    {
      href: agentPath(agentId, "connaissances") as Route,
      label: pick(locale, "Connaissances liées", "Verknuepftes Wissen", "Linked knowledge"),
    },
  ];
  return (
    <section className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2">
      <span className="text-[10px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
        {pick(locale, "Liens utiles", "Nuetzliche Links", "Useful links")}
      </span>
      {items.map((it) => (
        <Link
          key={it.label}
          href={it.href}
          className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface-2)] px-2 py-1 text-[11px] text-[var(--tessera-text)] transition-colors hover:border-[#7c5cf5]/50 hover:text-[var(--tessera-text-strong)]"
        >
          {it.label} →
        </Link>
      ))}
    </section>
  );
}

/** What the model EARNED over this set's own null floor — the domain bar's replacement.
 *
 *  ADR 0021 deleted the absolute bar and put no decoration in its place. Every number
 *  here is measured: the floor is the committed null control restricted to this set's
 *  cases, and the tile shows the model's delta over it. Two things it deliberately does
 *  NOT do — print a threshold (there is none), and call a break a regression (a break
 *  counts only once replayed, and a dashboard cannot replay). */
function ContributionTile({
  contribution,
  locale,
}: {
  contribution: NonNullable<Data["gate"]>["contribution"];
  locale: string;
}) {
  const shell = "rounded-md border border-[var(--tessera-border)]/60 bg-black/15 px-2.5 py-2";
  const heading = pick(locale, "Contribution du modèle", "Modellbeitrag", "Model contribution");
  // Honest-empty: no set bound, no committed floor, or NO MODEL SPOKE. Printing "0
  // regressions, 0 contribution" for a run no model answered would read as a pass.
  //
  // And it says WHY. The backend has carried `refusal` since 34b59c0d, and this tile dropped
  // it on the floor for a static "Non mesurable" — a reason written where nobody reads it is a
  // FALSE ASSURANCE, not a fix. "No model answered" and "the catalogue moved under this floor"
  // are different facts with different remedies, and the operator is the one who has to act on
  // them. The reason is the backend's own English (eval_floor.py does not localise it): showing
  // the real one untranslated beats showing a translated nothing.
  if (!contribution?.available) {
    return (
      <div className={shell}>
        <span className="text-[var(--tessera-text-muted)]">{heading}</span>
        <p className="mt-0.5 font-medium text-[var(--tessera-text-muted)]">
          {pick(locale, "Non mesurable", "Nicht messbar", "Not measurable")}
        </p>
        {contribution?.refusal ? (
          <p className="mt-1 text-[10px] text-[var(--tessera-text-muted)] leading-snug">
            {contribution.refusal}
          </p>
        ) : null}
      </div>
    );
  }
  const breaks = contribution.regression_candidates.length;
  return (
    <div className={shell} title={contribution.note}>
      <span className="text-[var(--tessera-text-muted)]">
        {heading}{" "}
        <span className="opacity-70">
          ({pick(locale, "plancher du set", "Sockel des Sets", "the set's own floor")}{" "}
          {contribution.floor_passed}/{contribution.floor_total})
        </span>
      </span>
      <p className="mt-0.5 font-medium text-[var(--tessera-text)]">
        +{contribution.contribution}/{contribution.contribution_population}{" "}
        <span
          className={
            breaks > 0 ? "text-[var(--tessera-fg-warning)]" : "text-[var(--tessera-fg-success)]"
          }
        >
          ·{" "}
          {breaks > 0
            ? `${breaks} ${pick(locale, "régression candidate", "Regressionskandidat", "candidate regression")}${breaks > 1 ? "s" : ""}`
            : pick(locale, "0 régression", "0 Regression", "0 regressions")}
        </span>
      </p>
    </div>
  );
}

/** Release-gate verdict as the page headline (policy §6: the verdict — not the
 *  aggregate score — is the title). Full-width banner, colour tied to conformity. */
function VerdictBanner({ data }: { data: Data }) {
  const locale = useLocale();
  const agentId = useAgentId();
  const gate = data.gate;
  if (!gate) return null;
  const blocked = gate.passed === false;
  const passed = gate.passed === true;
  // P2 — name the concrete blocking socle (T0) cases in the hero, not buried in
  // the table below. Derived from the real critical-cases rows (socle = T0).
  const socleFails = Array.from(
    new Set((gate.critical_cases?.rows ?? []).filter((r) => r.socle).map((r) => r.case_id)),
  );
  const tone = blocked
    ? "border-[#e0566f] bg-[#2a1320]"
    : passed
      ? "border-[#3fb37f] bg-[#10231b]"
      : "border-[var(--tessera-border)] bg-[var(--tessera-surface)]";
  const labelColor = blocked
    ? "text-[var(--tessera-fg-danger)]"
    : passed
      ? "text-[var(--tessera-fg-success)]"
      : "text-[var(--tessera-text)]";
  const bd = gate.breakdown;
  const bg = gate.breakdown_grain;
  return (
    <section className={`flex flex-col gap-2 rounded-lg border p-3 ${tone}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          {blocked ? (
            <ShieldAlert className="h-6 w-6 shrink-0 text-[var(--tessera-fg-danger)]" />
          ) : passed ? (
            <ShieldCheck className="h-6 w-6 shrink-0 text-[var(--tessera-fg-success)]" />
          ) : (
            <Shield className="h-6 w-6 shrink-0 text-[var(--tessera-text-muted)]" />
          )}
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {pick(
                locale,
                "Verdict du gate de release",
                "Release-Gate-Urteil",
                "Release gate verdict",
              )}
            </p>
            <p
              className={`flex items-center gap-1.5 text-[1.15rem] font-semibold leading-tight ${labelColor}`}
            >
              {gate.label}
              <CardInfo ns="agentEvaluations" k="verdict" title={gate.label} />
            </p>
            {gate.reason ? (
              <p className="mt-0.5 text-[11px] text-[var(--tessera-text-muted)]">{gate.reason}</p>
            ) : null}
            {blocked && socleFails.length > 0 ? (
              <p className="mt-1 text-[11px] text-[var(--tessera-fg-danger)]">
                <span className="text-[var(--tessera-text-muted)]">
                  {pick(
                    locale,
                    "Cœur non dérogeable en échec : ",
                    "Nicht ausnehmbarer Kern fehlgeschlagen: ",
                    "Non-waivable core failed: ",
                  )}
                </span>
                <span className="font-mono font-medium">{socleFails.join(", ")}</span>
                {" — "}
                <Link
                  href={`/agir/release-control?agent=${agentId}` as Route}
                  className="underline underline-offset-2 hover:text-[var(--tessera-text-strong)]"
                >
                  {pick(
                    locale,
                    "remédier dans Release Control →",
                    "in Release Control beheben →",
                    "remediate in Release Control →",
                  )}
                </Link>
              </p>
            ) : null}
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          {gate.grains ? (
            <span className="text-[10px] text-[var(--tessera-text-muted)]">
              {gate.grains.executions} {pick(locale, "exéc.", "Ausf.", "exec.")} ·{" "}
              {gate.grains.distinct_cases} {pick(locale, "cas", "Faelle", "cases")} ·{" "}
              {gate.grains.socle_cases} {pick(locale, "socle", "Sockel", "core")}
            </span>
          ) : null}
          <ReleaseControl />
        </div>
      </div>
      <div className="grid gap-2 text-[11px] sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-md border border-[var(--tessera-border)]/60 bg-black/15 px-2.5 py-2">
          <span className="text-[var(--tessera-text-muted)]">
            {pick(
              locale,
              "Socle dur (T0, zéro tolérance)",
              "Harter Sockel (T0, null Toleranz)",
              "Hard core (T0, zero tolerance)",
            )}
          </span>
          <p
            className={`mt-0.5 font-medium ${gate.socle?.ok ? "text-[var(--tessera-fg-success)]" : "text-[var(--tessera-fg-danger)]"}`}
          >
            {gate.socle
              ? gate.socle.ok
                ? `${pick(locale, "Conforme", "Konform", "Compliant")} — ${gate.socle.passed}/${gate.socle.total}`
                : `${pick(locale, "ÉCHEC", "FEHLER", "FAILURE")} — ${gate.socle.passed}/${gate.socle.total} ${pick(locale, "réussis", "bestanden", "passed")}`
              : gate.failed_critical.length > 0
                ? pick(locale, "Échec", "Fehler", "Failure")
                : pick(locale, "Conforme", "Konform", "Compliant")}
          </p>
        </div>
        {/* T2 used to print "(seuil 55 %)" next to this count. The threshold is gone —
            all three sat BELOW the catalogue's measured null floor, so an agent with no
            model at all cleared them (ADR 0021). What is left is the measurement, said
            to be one. No tone is applied: there is nothing to be compliant WITH. */}
        <div className="rounded-md border border-[var(--tessera-border)]/60 bg-black/15 px-2.5 py-2">
          <span className="text-[var(--tessera-text-muted)]">
            {pick(
              locale,
              "Domaine (T2) — mesuré, ne bloque pas",
              "Domaene (T2) — gemessen, nicht blockierend",
              "Domain (T2) — measured, non-blocking",
            )}
          </span>
          <p className="mt-0.5 font-medium text-[var(--tessera-text)]">
            {gate.domain
              ? `${gate.domain.passed}/${gate.domain.total} (${Math.round(gate.domain.rate * 100)}%)`
              : `${gate.standard_passed}/${gate.standard_total}`}
          </p>
        </div>
        <ContributionTile contribution={gate.contribution} locale={locale} />
        <div className="rounded-md border border-[var(--tessera-border)]/60 bg-black/15 px-2.5 py-2">
          <span className="text-[var(--tessera-text-muted)]">
            {pick(
              locale,
              "Critiques (cas × langue)",
              "Kritische (Fall × Sprache)",
              "Critical (case × language)",
            )}
          </span>
          <p className="mt-0.5 font-medium text-[var(--tessera-text)]">
            {bg
              ? `${bg.blocking_socle + bg.blocking_t1} ${pick(locale, "bloquants", "blockierend", "blocking")} · ${bg.waived_active} ${pick(locale, "dérogé", "ausgenommen", "waived")}${bg.waived_active > 1 && locale === "fr" ? "s" : ""}`
              : bd
                ? `${bd.critical_blocking} ${pick(locale, "bloquants", "blockierend", "blocking")} · ${bd.waived} ${pick(locale, "dérogé", "ausgenommen", "waived")}`
                : "—"}
            {bg && bg.non_executed_critical > 0
              ? ` · ${bg.non_executed_critical} ${pick(locale, "non exéc.", "nicht ausgef.", "not exec.")}`
              : ""}
          </p>
        </div>
      </div>
      {blocked ? <ActionsRequises gate={gate} socleFails={socleFails.length} /> : null}
    </section>
  );
}

/** P2 — concrete remediation steps to reach a PASSE gate, derived from the real
 *  gate state. No fabrication: each line only shows when its condition holds. */
function ActionsRequises({
  gate,
  socleFails,
}: {
  gate: NonNullable<Data["gate"]>;
  socleFails: number;
}) {
  const locale = useLocale();
  const bg = gate.breakdown_grain;
  const actions: string[] = [];
  if (gate.socle ? !gate.socle.ok : socleFails > 0)
    actions.push(
      pick(
        locale,
        "Corriger les cas du socle (T0) — cœur non dérogeable",
        "Sockel-Faelle (T0) beheben — nicht ausnehmbarer Kern",
        "Fix the core (T0) cases — non-waivable core",
      ),
    );
  if (bg && bg.blocking_t1 > 0)
    actions.push(
      pick(
        locale,
        `Corriger ou déroger ${bg.blocking_t1} cas critique(s) T1`,
        `${bg.blocking_t1} kritische(n) T1-Fall/Faelle beheben oder ausnehmen`,
        `Fix or waive ${bg.blocking_t1} critical T1 case(s)`,
      ),
    );
  if (bg && bg.non_executed_critical > 0)
    actions.push(
      pick(
        locale,
        `Rejouer ${bg.non_executed_critical} cas critique(s) non exécuté(s)`,
        `${bg.non_executed_critical} nicht ausgefuehrte(n) kritische(n) Fall/Faelle erneut ausfuehren`,
        `Replay ${bg.non_executed_critical} non-executed critical case(s)`,
      ),
    );
  // "Raise the domain rate to the threshold" is gone with the threshold (ADR 0021). It was
  // never an action either: no domain rate has ever blocked a release, so no domain rate has
  // ever been required to reach anything. A T2 failure is now surfaced where it is true —
  // the measured tile and the case table — never as a condition of shipping.
  actions.push(
    pick(
      locale,
      "Obtenir un gate PASSE avant toute promotion en prod",
      "Ein PASS-Gate vor jeder Produktionsfreigabe erreichen",
      "Reach a PASS gate before any production promotion",
    ),
  );
  return (
    <div className="rounded-md border border-[#e0566f]/40 bg-black/20 px-2.5 py-2 text-[11px]">
      <p className="mb-1 text-[10px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
        {pick(locale, "Actions requises", "Erforderliche Aktionen", "Required actions")}
      </p>
      <ul className="flex flex-col gap-0.5">
        {actions.map((a) => (
          <li key={a} className="flex items-start gap-1.5 text-[var(--tessera-text)]">
            <span className="mt-[3px] h-1.5 w-1.5 shrink-0 rounded-full bg-[#ff9bb0]" />
            {a}
          </li>
        ))}
      </ul>
    </div>
  );
}

const VENN_TONE: Record<string, string> = {
  crit: "border-[#e0566f]/50 bg-[#e0566f]/12 text-[var(--tessera-fg-danger)]",
  warn: "border-amber-500/40 bg-amber-500/12 text-[var(--tessera-fg-warning)]",
  muted: "border-[var(--tessera-border)] bg-black/15 text-[var(--tessera-text-muted)]",
};
const STATUS_PILL: Record<string, string> = {
  crit: "border-[#e0566f]/50 bg-[#e0566f]/15 text-[var(--tessera-fg-danger)]",
  warn: "border-amber-500/40 bg-amber-500/15 text-[var(--tessera-fg-warning)]",
  bad: "border-orange-500/40 bg-orange-500/15 text-[var(--tessera-fg-warning)]",
  good: "border-emerald-500/40 bg-emerald-500/15 text-[var(--tessera-fg-success)]",
};

/** Policy gate detail (eval-gate-policy.md): three tiers + structural Venn, the
 *  per-category socle markers, the critical-cases table (case × langue) and the
 *  governed-waiver registry. Every count reconciles with the verdict banner. */
function GatePolicySection({ data }: { data: Data }) {
  const locale = useLocale();
  const gate = data.gate;
  if (!gate || !gate.venn || !gate.tiers) return null;
  const v = gate.venn;
  const cc = gate.critical_cases;
  const wv = gate.waivers;
  const socleCats = gate.socle_by_category ?? [];
  const vennTitle = pick(
    locale,
    "Appartenance structurelle (Venn) — somme = exécutions",
    "Strukturelle Zugehoerigkeit (Venn) — Summe = Ausfuehrungen",
    "Structural membership (Venn) — sum = executions",
  );

  return (
    <div className="flex flex-col gap-2.5">
      {/* Tiers + structural Venn + socle-by-category markers */}
      <div className="grid gap-2.5 xl:grid-cols-12">
        <section className="flex min-w-0 flex-col gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3 xl:col-span-7">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1 text-[11px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {vennTitle}
              <CardInfo ns="agentEvaluations" k="gatePolicy" title={vennTitle} />
            </span>
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-[10px]",
                v.reconciles
                  ? "text-[var(--tessera-fg-success)]"
                  : "text-[var(--tessera-fg-danger)]",
              )}
            >
              {v.socle} + {v.t1} + {v.domaine} = {v.universe}
            </span>
          </div>
          {/* Nested: Critiques contains Socle; dérogations ⊂ T1, jamais socle */}
          <div className="rounded-md border border-[#e0566f]/40 bg-[#e0566f]/[0.06] p-2">
            <div className="mb-1 flex items-center justify-between text-[10px] text-[var(--tessera-fg-danger)]">
              <span>
                {pick(locale, "Critiques (T0 ∪ T1)", "Kritische (T0 ∪ T1)", "Critical (T0 ∪ T1)")}
              </span>
              <span className="tabular-nums">{v.critiques}</span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className={cn("rounded border px-2 py-1.5", VENN_TONE.crit)}>
                <p className="text-[10px] opacity-80">
                  {pick(
                    locale,
                    "Socle (T0) · non-dérogeable",
                    "Sockel (T0) · nicht ausnehmbar",
                    "Core (T0) · non-waivable",
                  )}
                </p>
                <p className="text-sm font-semibold tabular-nums">{v.socle}</p>
              </div>
              <div className={cn("rounded border px-2 py-1.5", VENN_TONE.warn)}>
                <p className="text-[10px] opacity-80">
                  {pick(
                    locale,
                    "Critique (T1) · dérogeable",
                    "Kritisch (T1) · ausnehmbar",
                    "Critical (T1) · waivable",
                  )}
                </p>
                <p className="text-sm font-semibold tabular-nums">
                  {v.t1}
                  <span className="ml-1 text-[10px] font-normal opacity-80">
                    {pick(locale, "dont", "davon", "incl.")} {v.deroges}{" "}
                    {pick(locale, "dérogé", "ausgenommen", "waived")}
                    {v.deroges > 1 && locale === "fr" ? "s" : ""}
                  </span>
                </p>
              </div>
            </div>
          </div>
          <div className={cn("rounded border px-2 py-1.5", VENN_TONE.muted)}>
            <div className="flex items-center justify-between">
              <span className="text-[10px]">
                {pick(
                  locale,
                  "Domaine (T2) · gradé",
                  "Domaene (T2) · gradiert",
                  "Domain (T2) · graded",
                )}
              </span>
              <span className="text-sm font-semibold tabular-nums">{v.domaine}</span>
            </div>
          </div>
          <p className="text-[10px] text-[var(--tessera-text-muted)]">
            {pick(
              locale,
              "Socle ∩ dérogations = ∅ — une dérogation n'est jamais effective sur le socle.",
              "Sockel ∩ Ausnahmen = ∅ — eine Ausnahme ist nie auf dem Sockel wirksam.",
              "Core ∩ waivers = ∅ — a waiver is never effective on the core.",
            )}
          </p>
        </section>

        {/* Socle OK / ÉCHEC per category — no green score may mask a breach */}
        <section className="flex min-w-0 flex-col gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3 xl:col-span-5">
          <span className="text-[11px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            {pick(locale, "Socle par catégorie", "Sockel nach Kategorie", "Core by category")}
          </span>
          {socleCats.length === 0 ? (
            <span className="text-[11px] text-[var(--tessera-text-muted)]">
              {pick(
                locale,
                "Aucune catégorie socle.",
                "Keine Sockel-Kategorie.",
                "No core category.",
              )}
            </span>
          ) : (
            <div className="flex flex-col gap-1.5">
              {socleCats.map((c) => (
                <div
                  key={c.category}
                  className="flex items-center justify-between rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1.5"
                >
                  <Truncate full={c.label} className="text-[11px] text-[var(--tessera-text)]">
                    {c.label}
                  </Truncate>
                  <span
                    className={cn(
                      "shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium",
                      c.ok ? STATUS_PILL.good : STATUS_PILL.crit,
                    )}
                  >
                    {c.ok
                      ? pick(locale, "Socle OK", "Sockel OK", "Core OK")
                      : pick(locale, "Socle ÉCHEC", "Sockel FEHLER", "Core FAIL")}{" "}
                    · {c.passed}/{c.total}
                  </span>
                </div>
              ))}
            </div>
          )}
          {gate.tiers ? (
            <div className="mt-1 grid grid-cols-3 gap-1.5">
              {gate.tiers.map((t) => (
                <div
                  key={t.tier}
                  className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1.5"
                >
                  <p className="text-[9px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
                    {t.tier} ·{" "}
                    {t.tier === "T2"
                      ? pick(locale, "gradé", "gradiert", "graded")
                      : t.waivable
                        ? pick(locale, "dérogeable", "ausnehmbar", "waivable")
                        : pick(locale, "non-dérog.", "nicht ausn.", "non-waiv.")}
                  </p>
                  <p className="text-sm font-semibold tabular-nums text-[var(--tessera-text)]">
                    {t.count}
                  </p>
                </div>
              ))}
            </div>
          ) : null}
        </section>
      </div>

      {/* Critical-cases table (case × langue) + waiver registry */}
      <div className="grid gap-2.5 xl:grid-cols-12">
        {cc ? (
          <section className="flex min-w-0 flex-col gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3 xl:col-span-7">
            <div className="flex items-center justify-between">
              <span className="text-[11px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
                {cc.title}
              </span>
              <span className="text-[10px] text-[var(--tessera-text-muted)]">
                {cc.total} {pick(locale, "cas", "Faelle", "cases")}
              </span>
            </div>
            {cc.rows.length === 0 ? (
              <span className="text-[11px] text-[var(--tessera-fg-success)]">
                {pick(
                  locale,
                  "Aucun cas critique non concluant.",
                  "Kein nicht schluessiger kritischer Fall.",
                  "No inconclusive critical case.",
                )}
              </span>
            ) : (
              <div className="max-h-[19rem] overflow-auto">
                <table className="w-full text-left text-[11px]">
                  <thead className="sticky top-0 bg-[var(--tessera-surface)] text-[10px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
                    <tr>
                      <th className="py-1 pr-2 font-medium">
                        {pick(locale, "Cas", "Fall", "Case")}
                      </th>
                      <th className="py-1 pr-2 font-medium">Tier</th>
                      <th className="py-1 pr-2 font-medium">{pick(locale, "Lg", "Spr", "Lng")}</th>
                      <th className="py-1 pr-2 font-medium">
                        {pick(locale, "Statut gate", "Gate-Status", "Gate status")}
                      </th>
                      <th className="py-1 font-medium">
                        {pick(locale, "Socle", "Sockel", "Core")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {cc.rows.map((r, i) => (
                      <tr
                        key={`${r.case_id}-${r.language}-${i}`}
                        className="border-t border-[var(--tessera-border)]/40"
                      >
                        <td className="max-w-[12rem] truncate py-1 pr-2" title={r.title}>
                          {r.case_id}
                        </td>
                        <td className="py-1 pr-2">
                          <span
                            className={cn(
                              "rounded px-1 py-0.5 text-[9px] font-medium",
                              STATUS_PILL[r.tier_tone] ?? STATUS_PILL.warn,
                            )}
                          >
                            {r.tier}
                          </span>
                        </td>
                        <td className="py-1 pr-2 text-[var(--tessera-text-muted)]">{r.language}</td>
                        <td className="py-1 pr-2">
                          <span
                            className={cn(
                              "rounded px-1.5 py-0.5 text-[10px] font-medium",
                              STATUS_PILL[r.status_tone] ?? STATUS_PILL.bad,
                            )}
                          >
                            {r.status_label}
                          </span>
                        </td>
                        <td className="py-1 text-[var(--tessera-text-muted)]">
                          {r.socle ? pick(locale, "Socle", "Sockel", "Core") : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        ) : null}

        {wv ? (
          <section className="flex min-w-0 flex-col gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3 xl:col-span-5">
            <div className="flex items-center justify-between">
              <span className="text-[11px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
                {wv.title}
              </span>
              <span
                className={cn(
                  "rounded px-1.5 py-0.5 text-[10px]",
                  wv.chain_verified
                    ? "text-[var(--tessera-fg-success)]"
                    : "text-[var(--tessera-fg-danger)]",
                )}
                title={pick(
                  locale,
                  "Intégrité de la chaîne de hash",
                  "Integritaet der Hash-Kette",
                  "Hash-chain integrity",
                )}
              >
                {wv.chain_verified
                  ? pick(locale, "chaîne ✓", "Kette ✓", "chain ✓")
                  : pick(locale, "chaîne ✗", "Kette ✗", "chain ✗")}{" "}
                · {wv.active} {pick(locale, "active", "aktiv", "active")}
                {wv.active > 1 && locale === "fr" ? "s" : ""}/{wv.total}
              </span>
            </div>
            <p className="text-[10px] text-[var(--tessera-text-muted)]">{wv.subtitle}</p>
            <div className="flex max-h-[19rem] flex-col gap-1.5 overflow-auto">
              {wv.items.length === 0 ? (
                <span className="text-[11px] text-[var(--tessera-text-muted)]">
                  {pick(locale, "Aucune dérogation.", "Keine Ausnahme.", "No waiver.")}
                </span>
              ) : (
                wv.items.map((it) => (
                  <div
                    key={it.id}
                    className={cn(
                      "rounded-md border px-2 py-1.5",
                      it.active
                        ? "border-amber-500/40 bg-amber-500/[0.07]"
                        : "border-[var(--tessera-border)] bg-[var(--tessera-bg)]",
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <Truncate
                        full={`${it.case_id} · ${it.language}`}
                        className="text-[11px] font-medium text-[var(--tessera-text)]"
                      >
                        {it.case_id} · {it.language}
                      </Truncate>
                      <span
                        className={cn(
                          "shrink-0 rounded px-1.5 py-0.5 text-[9px] font-medium",
                          it.active
                            ? STATUS_PILL.warn
                            : "border border-[var(--tessera-border)] text-[var(--tessera-text-muted)]",
                        )}
                      >
                        {it.status_label}
                      </span>
                    </div>
                    <p
                      title={it.justification}
                      className="mt-0.5 line-clamp-2 text-[10px] text-[var(--tessera-text-muted)]"
                    >
                      {it.justification}
                    </p>
                    <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[9px] text-[var(--tessera-text-muted)]">
                      <span>
                        {pick(locale, "Demande", "Antrag", "Request")} : {it.requester}
                      </span>
                      <span>
                        {pick(locale, "Appro.", "Genehm.", "Appr.")} : {it.approver}
                      </span>
                      <span>
                        {pick(locale, "Échéance", "Frist", "Due")} : {it.expires_at}
                      </span>
                      {it.incident_ref ? <span>{it.incident_ref}</span> : null}
                    </div>
                    {it.controls.length > 0 ? (
                      <p className="mt-0.5 text-[9px] text-[var(--tessera-text-muted)]">
                        {pick(locale, "Contrôles", "Kontrollen", "Controls")} :{" "}
                        {it.controls.join(" · ")}
                      </p>
                    ) : null}
                  </div>
                ))
              )}
            </div>
          </section>
        ) : null}
      </div>
    </div>
  );
}

function JudgeMetrics({ data, className }: { data: Data; className?: string }) {
  const locale = useLocale();
  const judge = data.judge;
  if (!judge) return null;
  const title = pick(locale, "Métriques jugées", "Bewertete Metriken", "Judged metrics");

  return (
    <section
      className={cn(
        "flex min-w-0 flex-col gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3",
        className,
      )}
    >
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1 text-[11px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
          {title}
          <CardInfo ns="agentEvaluations" k="judge" title={title} />
        </span>
        <span className="text-[10px] text-[var(--tessera-text-muted)]">
          {judge.available
            ? (judge.judge_model ?? "")
            : pick(locale, "indisponible", "nicht verfuegbar", "unavailable")}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {(
          [
            [pick(locale, "Fidélité", "Treue", "Fidelity"), judge.faithfulness],
            [pick(locale, "Ancrage", "Grounding", "Grounding"), judge.grounding],
            [pick(locale, "Anti-halluc.", "Anti-Halluz.", "Anti-halluc."), judge.hallucination],
          ] as const
        ).map(([label, value]) => (
          <div key={label} className="flex flex-col">
            <span className="text-base font-semibold text-[var(--tessera-text)]">
              {judge.available ? pct(value) : "—"}
            </span>
            <span className="text-[10px] text-[var(--tessera-text-muted)]">{label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function Snapshot({ data, onAsof }: { data: Data; onAsof: () => void }) {
  const s = data.snapshot;
  if (!s) return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        <Field>
          <span className="text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            {s.tag}
          </span>
          <span className="flex items-center gap-1 text-[0.92rem] font-semibold text-[var(--tessera-text)]">
            {s.label}
            <CardInfo ns="agentEvaluations" k="snapshot" title={s.label} />
          </span>
        </Field>
        <Field>
          <span className="text-[0.6rem] text-[var(--tessera-text-muted)]">{s.updated_label}</span>
          <span className="text-[0.82rem] font-medium tabular-nums text-[var(--tessera-text)]">
            {s.updated}
          </span>
          <span className="text-[0.58rem] text-[var(--tessera-text-muted)]">{s.updated_rel}</span>
        </Field>
        <Field>
          <span className="text-[0.6rem] text-[var(--tessera-text-muted)]">{s.version_label}</span>
          <span className="text-[0.82rem] font-medium text-[var(--tessera-text)]">{s.version}</span>
          <span className="text-[0.58rem] text-[var(--tessera-fg-success)]">
            {s.version_status}
          </span>
        </Field>
        <Field>
          <span className="text-[0.6rem] text-[var(--tessera-text-muted)]">{s.evalset_label}</span>
          <span className="text-[0.82rem] font-medium text-[var(--tessera-text)]">{s.evalset}</span>
        </Field>
        <Field>
          <span className="text-[0.6rem] text-[var(--tessera-text-muted)]">{s.coverage_label}</span>
          <span className="flex items-center gap-2">
            <Gauge pct={s.coverage} />
            <span className="text-[0.7rem] text-[var(--tessera-fg-success)]">
              {s.coverage_tone}
            </span>
          </span>
        </Field>
      </div>
      <div className="flex flex-col items-start gap-1 text-[0.68rem]">
        <button
          type="button"
          onClick={onAsof}
          className="inline-flex items-center gap-1 text-[var(--tessera-fg-accent)] hover:text-[var(--tessera-text-strong)]"
        >
          <CalendarClock className="h-3.5 w-3.5" /> {s.asof}
        </button>
        <Link
          href={"/prouver/etat-a-date" as Route}
          className="inline-flex items-center gap-1 text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          <ChevronRight className="h-3.5 w-3.5" /> {s.compare}
        </Link>
      </div>
    </div>
  );
}

function Field({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col gap-0.5">{children}</div>;
}

function Gauge({ pct }: { pct: number }) {
  const r = 11;
  const c = 2 * Math.PI * r;
  const off = c * (1 - pct / 100);
  return (
    <span className="relative inline-flex h-8 w-8 items-center justify-center">
      <svg viewBox="0 0 28 28" className="h-8 w-8 -rotate-90" aria-hidden="true">
        <circle cx="14" cy="14" r={r} fill="none" stroke="var(--tessera-border)" strokeWidth="3" />
        <circle
          cx="14"
          cy="14"
          r={r}
          fill="none"
          stroke="var(--tessera-fg-success)"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={off}
        />
      </svg>
      <span className="absolute text-[0.52rem] font-semibold tabular-nums text-[var(--tessera-text)]">
        {pct}%
      </span>
    </span>
  );
}

function Kpi({ kpi, Icon }: { kpi: NonNullable<Data["kpis"]>[number]; Icon: LucideIcon }) {
  return (
    <div className="flex h-[96px] flex-col justify-between rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="flex items-center gap-2">
        <Icon className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
        <Truncate full={kpi.label} className="text-[0.64rem] text-[var(--tessera-text-muted)]">
          {kpi.label}
        </Truncate>
        <CardInfo ns="agentEvaluations" k={kpi.key} title={kpi.label} />
      </div>
      {kpi.gauge !== null ? (
        <div className="flex items-center gap-2">
          <Gauge pct={kpi.gauge} />
          <span className="text-[0.78rem] font-medium text-[var(--tessera-fg-success)]">
            {kpi.note}
          </span>
        </div>
      ) : (
        <div>
          <p className="text-[1.25rem] font-semibold tabular-nums leading-tight text-[var(--tessera-text)]">
            {kpi.value}
            {kpi.scale ? (
              <span className="text-[0.66rem] font-normal text-[var(--tessera-text-muted)]">
                {kpi.scale}
              </span>
            ) : null}
          </p>
          {kpi.note ? (
            <p
              className={cn(
                "text-[0.62rem]",
                kpi.note_tone === "good"
                  ? "text-[var(--tessera-fg-success)]"
                  : "text-[var(--tessera-text-muted)]",
              )}
            >
              {kpi.note}
            </p>
          ) : null}
        </div>
      )}
      {kpi.delta ? (
        <p
          className={cn(
            "text-[0.58rem] tabular-nums",
            TONE_TEXT[kpi.delta_tone] ?? TONE_TEXT.muted,
          )}
        >
          {kpi.delta}
        </p>
      ) : null}
    </div>
  );
}

function FilterDropdown({
  label,
  value,
  options,
  onSelect,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onSelect: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useDismiss(
    open,
    useCallback(() => setOpen(false), []),
  );
  const current = options.find((o) => o.value === value)?.label ?? value;
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex h-9 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[0.74rem] hover:border-[var(--tessera-text-muted)]"
      >
        <span className="text-[var(--tessera-text-muted)]">{label}</span>
        <span className="font-medium text-[var(--tessera-text)]">{current}</span>
        <ChevronDown className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 max-h-72 w-52 overflow-y-auto rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-1 shadow-lg"
        >
          {options.map((o) => (
            <button
              key={o.value}
              type="button"
              role="menuitem"
              onClick={() => {
                onSelect(o.value);
                setOpen(false);
              }}
              className={cn(
                "flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-[0.72rem] hover:bg-[var(--tessera-bg)]",
                o.value === value
                  ? "text-[var(--tessera-text)]"
                  : "text-[var(--tessera-text-muted)]",
              )}
            >
              {o.label}
              {o.value === value ? (
                <span className="text-[var(--tessera-fg-accent)]">&bull;</span>
              ) : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

type FiltersProps = {
  data: Data;
  search: string;
  setSearch: (v: string) => void;
  typeKey: string;
  setTypeKey: (v: string) => void;
  qualityKey: string;
  setQualityKey: (v: string) => void;
  hallucKey: string;
  setHallucKey: (v: string) => void;
  onReset: () => void;
};

function Filters(p: FiltersProps) {
  const locale = useLocale();
  const f = p.data.filters;
  if (!f) return null;
  const all = pick(locale, "Tous", "Alle", "All");
  const allF = pick(locale, "Toutes", "Alle", "All");
  const opt = (
    items: { key: string; label: string }[],
    allLabel: string,
  ): { value: string; label: string }[] => [
    { value: "all", label: allLabel },
    ...items.map((i) => ({ value: i.key, label: i.label })),
  ];
  const anyActive =
    p.search !== "" || p.typeKey !== "all" || p.qualityKey !== "all" || p.hallucKey !== "all";
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5">
      <div className="flex h-9 min-w-[200px] flex-1 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5">
        <Search className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
        <input
          value={p.search}
          onChange={(e) => p.setSearch(e.target.value)}
          placeholder={f.search}
          aria-label={f.search}
          className="h-full min-w-0 flex-1 bg-transparent text-[0.74rem] text-[var(--tessera-text)] outline-none placeholder:text-[var(--tessera-text-muted)]"
        />
      </div>
      <FilterDropdown
        label={pick(locale, "Type", "Typ", "Type")}
        value={p.typeKey}
        options={opt(f.options.type, all)}
        onSelect={p.setTypeKey}
      />
      <FilterDropdown
        label={pick(locale, "Qualité", "Qualitaet", "Quality")}
        value={p.qualityKey}
        options={opt(f.options.quality, allF)}
        onSelect={p.setQualityKey}
      />
      <FilterDropdown
        label={pick(locale, "Hallucinations", "Halluzinationen", "Hallucinations")}
        value={p.hallucKey}
        options={opt(f.options.halluc, allF)}
        onSelect={p.setHallucKey}
      />
      {anyActive ? (
        <button
          type="button"
          onClick={p.onReset}
          className="flex h-9 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[0.74rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          <X className="h-3.5 w-3.5" /> {pick(locale, "Réinitialiser", "Zuruecksetzen", "Reset")}
        </button>
      ) : null}
    </div>
  );
}

type TableProps = {
  data: Data;
  rows: RowT[];
  total: number;
  selected: string | null;
  onSelect: (name: string) => void;
  sortCol: number | null;
  sortDir: "asc" | "desc";
  onSort: (col: number) => void;
  page: number;
  totalPages: number;
  start: number;
  end: number;
  perPage: number;
  onPage: (p: number) => void;
  onPerPage: (n: number) => void;
};

function RunsTable(p: TableProps) {
  const tbl = p.data.table;
  if (!tbl) return null;
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[820px] border-collapse text-left">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {tbl.columns.map((c, i) => (
                <th
                  key={c}
                  aria-sort={
                    p.sortCol === i ? (p.sortDir === "asc" ? "ascending" : "descending") : "none"
                  }
                  className={cn("px-3 py-2 font-medium", i === 0 ? "" : "whitespace-nowrap")}
                >
                  <button
                    type="button"
                    onClick={() => p.onSort(i)}
                    className={cn(
                      "inline-flex items-center gap-1 hover:text-[var(--tessera-text)]",
                      p.sortCol === i ? "text-[var(--tessera-text)]" : "",
                    )}
                  >
                    {c}
                    {p.sortCol === i ? (
                      <ChevronDown className={cn("h-3 w-3", p.sortDir === "asc" && "rotate-180")} />
                    ) : (
                      <ChevronsUpDown className="h-3 w-3 opacity-40" />
                    )}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {p.rows.map((r) => {
              const on = r.name === p.selected;
              return (
                <tr
                  key={r.name}
                  // biome-ignore lint/a11y/useSemanticElements: a table row is the click target here
                  role="button"
                  tabIndex={0}
                  aria-label={`Evaluation ${r.name}`}
                  onClick={() => p.onSelect(r.name)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      p.onSelect(r.name);
                    }
                  }}
                  className={cn(
                    "cursor-pointer border-b border-[var(--tessera-border)]/60 last:border-0 focus:outline-none focus-visible:ring-1 focus-visible:ring-[#8b7cf0]",
                    on ? "bg-[#6d4aed]/10" : "hover:bg-[var(--tessera-bg)]/40",
                  )}
                >
                  <td className="px-3 py-2.5">
                    <div className="flex items-center gap-2">
                      <Sparkles className="h-4 w-4 shrink-0 text-[var(--tessera-fg-info)]" />
                      <Truncate
                        full={r.name}
                        className="text-[0.72rem] font-medium text-[var(--tessera-text)]"
                      >
                        {r.name}
                      </Truncate>
                    </div>
                  </td>
                  <td className="px-3 py-2.5">
                    <span
                      className={cn(
                        "rounded-full border px-2 py-0.5 text-[0.56rem] font-medium",
                        TYPE_TONE[r.type_tone] ?? TYPE_TONE.tpl,
                      )}
                    >
                      {r.type}
                    </span>
                  </td>
                  <td className="px-3 py-2.5">
                    <span
                      className={cn(
                        "inline-flex items-center gap-1.5 text-[0.66rem]",
                        STATUS_TONE[r.status_tone] ?? STATUS_TONE.good,
                      )}
                    >
                      <span
                        className={cn(
                          "h-1.5 w-1.5 rounded-full",
                          STATUS_DOT[r.status_tone] ?? STATUS_DOT.good,
                        )}
                      />
                      {r.status}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-[0.68rem] tabular-nums text-[var(--tessera-text)]">
                    {r.version}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-[0.68rem] tabular-nums text-[var(--tessera-text)]">
                    {r.score === "-" ? "-" : `${r.score} / 10`}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-[0.68rem] tabular-nums text-[var(--tessera-fg-success)]">
                    {r.success}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-[0.68rem] tabular-nums text-[var(--tessera-text-muted)]">
                    {r.halluc}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-[0.68rem] tabular-nums text-[var(--tessera-text-muted)]">
                    {r.last_run}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-[0.68rem] text-[var(--tessera-text)]">
                    {r.owner}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2.5 text-[0.68rem] tabular-nums text-[var(--tessera-text-muted)]">
                    {r.tests}
                  </td>
                </tr>
              );
            })}
            {p.rows.length === 0 ? (
              <tr>
                <td
                  colSpan={tbl.columns.length}
                  className="px-3 py-8 text-center text-[0.72rem] text-[var(--tessera-text-muted)]"
                >
                  Aucune évaluation ne correspond aux filtres.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <Pagination
        page={p.page}
        totalPages={p.totalPages}
        start={p.start}
        end={p.end}
        total={p.total}
        perPage={p.perPage}
        onPage={p.onPage}
        onPerPage={p.onPerPage}
      />
    </section>
  );
}

function pageWindow(page: number, totalPages: number): number[] {
  const span = Math.min(MAX_PAGE_BUTTONS, totalPages);
  let first = Math.max(1, page - Math.floor(span / 2));
  first = Math.min(first, totalPages - span + 1);
  return Array.from({ length: span }, (_, i) => first + i);
}

function Pagination({
  page,
  totalPages,
  start,
  end,
  total,
  perPage,
  onPage,
  onPerPage,
}: {
  page: number;
  totalPages: number;
  start: number;
  end: number;
  total: number;
  perPage: number;
  onPage: (p: number) => void;
  onPerPage: (n: number) => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--tessera-border)] px-3 py-2 text-[0.7rem] text-[var(--tessera-text-muted)]">
      <span className="tabular-nums" aria-live="polite">
        {start}-{end} sur {total} jeux
      </span>
      <div className="flex items-center gap-1">
        <PageArrow dir="prev" disabled={page <= 1} onClick={() => onPage(Math.max(1, page - 1))} />
        {pageWindow(page, totalPages).map((n) => (
          <button
            key={n}
            type="button"
            aria-current={n === page ? "page" : undefined}
            onClick={() => onPage(n)}
            className={cn(
              "flex h-7 min-w-7 items-center justify-center rounded-md border px-1.5 text-[0.72rem] tabular-nums",
              n === page
                ? "border-[#b9a6ff]/60 bg-[#b9a6ff]/15 font-medium text-[var(--tessera-text-strong)]"
                : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
            )}
          >
            {n}
          </button>
        ))}
        <PageArrow
          dir="next"
          disabled={page >= totalPages}
          onClick={() => onPage(Math.min(totalPages, page + 1))}
        />
      </div>
      <label className="flex items-center gap-2">
        <span>Lignes par page</span>
        <select
          value={perPage}
          onChange={(e) => onPerPage(Number(e.target.value))}
          className="h-7 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 text-[0.72rem] text-[var(--tessera-text)] focus:outline-none"
        >
          {PER_PAGE_OPTS.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

function PageArrow({
  dir,
  disabled,
  onClick,
}: {
  dir: "prev" | "next";
  disabled: boolean;
  onClick: () => void;
}) {
  const locale = useLocale();
  const Icon = dir === "prev" ? ChevronLeft : ChevronRight;
  return (
    <button
      type="button"
      disabled={disabled}
      aria-label={
        dir === "prev"
          ? pick(locale, "Page précédente", "Vorherige Seite", "Previous page")
          : pick(locale, "Page suivante", "Naechste Seite", "Next page")
      }
      onClick={onClick}
      className="flex h-7 w-7 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] enabled:hover:text-[var(--tessera-text)] disabled:opacity-40"
    >
      <Icon className="h-3.5 w-3.5" />
    </button>
  );
}

function PanelCard({
  title,
  info,
  cta,
  ctaHref,
  children,
}: {
  title: string;
  info?: React.ReactNode;
  cta?: string;
  ctaHref?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <h3 className="mb-2 flex items-center gap-1 text-[0.74rem] font-semibold text-[var(--tessera-text)]">
        {title}
        {info}
      </h3>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
      {cta && ctaHref ? (
        <Link
          href={ctaHref as Route}
          className="mt-2.5 flex items-center gap-1 self-start text-[0.66rem] text-[var(--tessera-fg-accent)] hover:text-[var(--tessera-text-strong)]"
        >
          {cta} <ChevronRight className="h-3.5 w-3.5" />
        </Link>
      ) : null}
    </section>
  );
}

function Watch({ data }: { data: Data }) {
  const w = data.watch;
  if (!w) return null;
  return (
    <PanelCard
      title={w.title}
      info={<CardInfo ns="agentEvaluations" k="watch" title={w.title} />}
      cta={w.cta}
      ctaHref={w.cta_href}
    >
      <ul className="flex flex-col gap-2.5">
        {w.items.map((it) => (
          <li key={it.title} className="flex items-start gap-2">
            <span
              className={cn(
                "mt-1 h-1.5 w-1.5 shrink-0 rounded-full",
                WATCH_DOT[it.tone] ?? "bg-slate-400",
              )}
            />
            <span className="min-w-0">
              <Truncate full={it.title} className="text-[0.72rem] text-[var(--tessera-text)]">
                {it.title}
              </Truncate>
              <Truncate
                full={it.detail}
                className="text-[0.62rem] text-[var(--tessera-text-muted)]"
              >
                {it.detail}
              </Truncate>
            </span>
          </li>
        ))}
      </ul>
    </PanelCard>
  );
}

function Quick({ data }: { data: Data }) {
  const q = data.quick;
  const agentId = useAgentId();
  if (!q) return null;
  const icons = [Play, GitCompare, BarChart3, Layers];
  const hrefs = quickHref(agentId);
  return (
    <PanelCard title={q.title} info={<CardInfo ns="agentEvaluations" k="quick" title={q.title} />}>
      <div className="grid grid-cols-2 gap-2">
        {q.items.map((it, i) => {
          const Icon = icons[i % icons.length] ?? Play;
          return (
            <Link
              key={it.key}
              href={hrefs[it.key] ?? (agentPath(agentId, "evaluations") as Route)}
              className="flex flex-col items-start gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2 text-left text-[0.68rem] text-[var(--tessera-text)] hover:border-[#7c5cf5]/50"
            >
              <Icon className="h-4 w-4 text-[var(--tessera-fg-accent)]" />
              <Truncate full={it.label} className="min-w-0">
                {it.label}
              </Truncate>
            </Link>
          );
        })}
      </div>
    </PanelCard>
  );
}

function Trend({ data }: { data: Data }) {
  const tr = data.trend;
  if (!tr) return null;
  return (
    <PanelCard
      title={tr.title}
      info={<CardInfo ns="agentEvaluations" k="trend" title={tr.title} />}
    >
      <div className="mb-2 flex items-baseline gap-1">
        <span className="text-[1.25rem] font-semibold tabular-nums text-[var(--tessera-text)]">
          {tr.value}
        </span>
        <span className="text-[0.66rem] text-[var(--tessera-text-muted)]">{tr.scale}</span>
      </div>
      <AreaChart values={tr.series} />
      <p className="mt-2 flex items-center gap-1.5 text-[0.62rem] text-[var(--tessera-text-muted)]">
        <span className="h-1.5 w-1.5 rounded-full bg-[#8b7cf0]" /> {tr.legend}
      </p>
    </PanelCard>
  );
}

function AreaChart({ values }: { values: number[] }) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const W = 100;
  const H = 40;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * W;
    const y = H - ((v - min) / span) * (H - 4) - 2;
    return [x, y] as const;
  });
  const line = pts
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`)
    .join(" ");
  const area = `${line} L${W},${H} L0,${H} Z`;
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-12 w-full"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <path d={area} fill="#8b7cf0" opacity="0.12" />
      <path
        d={line}
        fill="none"
        stroke="#8b7cf0"
        strokeWidth="1.4"
        vectorEffect="non-scaling-stroke"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function Detail({
  data,
  row,
  className,
}: {
  data: Data;
  row: RowT | null;
  className?: string;
}) {
  const locale = useLocale();
  const agentId = useAgentId();
  const labels = data.detail_labels;
  const meta = data.meta;
  const tabs = labels?.tabs ?? ["Résumé", "Configuration", "Résultats", "Activité"];
  const [tab, setTab] = useState(tabs[0] ?? "Résumé");
  if (!labels || !meta || !row) return null;

  const description = pick(
    locale,
    `Sondes de la catégorie '${row.name}' du catalogue d'échecs, exécutées sur le plus petit modèle (${meta.model}). Sur ce run, ${row.passed} cas sur ${row.total} passent.`,
    `Sonden der Kategorie '${row.name}' aus dem Fehlerkatalog, ausgefuehrt auf dem kleinsten Modell (${meta.model}). In diesem Lauf bestehen ${row.passed} von ${row.total} Faellen.`,
    `Probes of the '${row.name}' category from the failure catalogue, run on the smallest model (${meta.model}). In this run, ${row.passed} of ${row.total} cases pass.`,
  );
  const fields: { label: string; value: string; tone?: string }[] = [
    { label: pick(locale, "Type", "Typ", "Type"), value: row.type },
    { label: pick(locale, "Catégorie", "Kategorie", "Category"), value: row.category_key },
    {
      label: pick(locale, "Version catalogue", "Katalogversion", "Catalogue version"),
      value: meta.catalogue_version,
    },
    { label: pick(locale, "Statut", "Status", "Status"), value: row.status, tone: row.status_tone },
    {
      label: pick(locale, "Dernière exécution", "Letzte Ausfuehrung", "Last run"),
      value: row.last_run,
    },
    {
      label: pick(locale, "Modèle évalué", "Evaluiertes Modell", "Evaluated model"),
      value: meta.model,
    },
    { label: pick(locale, "Cas", "Faelle", "Cases"), value: String(row.total) },
    { label: pick(locale, "Langues", "Sprachen", "Languages"), value: meta.languages },
    { label: pick(locale, "Propriétaire", "Eigentuemer", "Owner"), value: row.owner },
  ];
  const results: { label: string; value: string }[] = [
    { label: pick(locale, "Score", "Score", "Score"), value: `${row.score} / 10` },
    { label: pick(locale, "Taux de réussite", "Erfolgsrate", "Pass rate"), value: row.success },
    {
      label: pick(locale, "Cas réussis", "Bestandene Faelle", "Passed cases"),
      value: `${row.passed} / ${row.total}`,
    },
    {
      label: pick(locale, "Cas échoués", "Fehlgeschlagene Faelle", "Failed cases"),
      value: `${row.failed} / ${row.total}`,
    },
    {
      label: pick(
        locale,
        "Score global du run (informatif)",
        "Gesamtscore des Laufs (informativ)",
        "Global run score (informative)",
      ),
      value: `${meta.score10} / 10`,
    },
    {
      label: pick(
        locale,
        "Escalades requises",
        "Erforderliche Eskalationen",
        "Required escalations",
      ),
      value: String(meta.escalations),
    },
    {
      label: pick(locale, "Invocations d'outils", "Tool-Aufrufe", "Tool invocations"),
      value: String(meta.tool_invocations),
    },
  ];
  const config: { label: string; value: string }[] = [
    { label: pick(locale, "Modèle", "Modell", "Model"), value: meta.model },
    {
      label: pick(locale, "Version catalogue", "Katalogversion", "Catalogue version"),
      value: meta.catalogue_version,
    },
    { label: pick(locale, "Type", "Typ", "Type"), value: row.type },
    { label: pick(locale, "Qualité", "Qualitaet", "Quality"), value: row.quality_label },
    { label: pick(locale, "Langues", "Sprachen", "Languages"), value: meta.languages },
  ];
  const activity: { label: string; time: string }[] = [
    { label: pick(locale, "Jeu exécuté", "Set ausgefuehrt", "Set run"), time: row.last_run },
    {
      label:
        row.pass_rate >= 0.7
          ? pick(locale, "Évaluation réussie", "Evaluierung bestanden", "Evaluation passed")
          : pick(
              locale,
              "Évaluation sous le seuil",
              "Evaluierung unter Schwelle",
              "Evaluation below threshold",
            ),
      time: row.last_run,
    },
  ];

  return (
    <section
      className={cn(
        "flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]",
        className,
      )}
    >
      <div className="border-b border-[var(--tessera-border)] px-3.5 py-3">
        <p className="text-[0.62rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
          {labels.eyebrow}
        </p>
        <div className="mt-1 flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <Sparkles className="h-4 w-4 shrink-0 text-[var(--tessera-fg-info)]" />
            <Truncate
              full={row.name}
              className="min-w-0 text-[0.85rem] font-semibold text-[var(--tessera-text)]"
            >
              {row.name}
            </Truncate>
          </div>
          <span className="shrink-0 rounded-full border border-emerald-500/30 bg-emerald-500/15 px-2 py-0.5 text-[0.6rem] font-medium text-[var(--tessera-fg-success)]">
            {row.status}
          </span>
        </div>
      </div>

      <nav className="flex items-center gap-4 border-b border-[var(--tessera-border)] px-3.5">
        {tabs.map((tb) => {
          const on = tb === tab;
          return (
            <button
              key={tb}
              type="button"
              onClick={() => setTab(tb)}
              className={cn(
                "-mb-px border-b-2 py-2.5 text-[0.72rem] transition-colors",
                on
                  ? "border-[#8b7cf0] font-medium text-[var(--tessera-text)]"
                  : "border-transparent text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
              )}
            >
              {tb}
            </button>
          );
        })}
      </nav>

      <div className="flex flex-col gap-4 p-3.5">
        {tab === tabs[0] ? (
          <>
            <div>
              <h3 className="mb-1 text-[0.7rem] font-semibold text-[var(--tessera-text)]">
                Description
              </h3>
              <p className="text-[0.72rem] leading-relaxed text-[var(--tessera-text-muted)]">
                {description}
              </p>
            </div>
            <ul className="flex flex-col gap-1.5 text-[0.72rem]">
              {fields.map((f) => (
                <li key={f.label} className="flex items-center justify-between gap-2">
                  <span className="text-[var(--tessera-text-muted)]">{f.label}</span>
                  <span
                    className={cn(
                      "font-medium",
                      f.tone === "good"
                        ? "text-[var(--tessera-fg-success)]"
                        : "text-[var(--tessera-text)]",
                    )}
                  >
                    {f.value}
                  </span>
                </li>
              ))}
            </ul>
          </>
        ) : null}

        {tab === tabs[1] ? (
          <>
            <DetailBlock title={labels.config_title}>
              <ul className="flex flex-col gap-1.5 text-[0.72rem]">
                {config.map((c) => (
                  <li key={c.label} className="flex items-center justify-between gap-2">
                    <span className="text-[var(--tessera-text-muted)]">{c.label}</span>
                    <span className="font-medium text-[var(--tessera-text)]">{c.value}</span>
                  </li>
                ))}
              </ul>
            </DetailBlock>
            <DetailBlock title={labels.rbac_title}>
              <ul className="flex flex-col gap-1.5 text-[0.72rem]">
                {meta.rbac.map((r) => (
                  <li key={r.role} className="flex items-center justify-between gap-2">
                    <span className="text-[var(--tessera-text-muted)]">{r.role}</span>
                    <span className="font-medium text-[var(--tessera-text)]">{r.access}</span>
                  </li>
                ))}
              </ul>
            </DetailBlock>
          </>
        ) : null}

        {tab === tabs[2] ? (
          <DetailBlock title={labels.results_title}>
            <ul className="flex flex-col gap-1.5 text-[0.72rem]">
              {results.map((r) => (
                <li key={r.label} className="flex items-center justify-between gap-2">
                  <span className="text-[var(--tessera-text-muted)]">{r.label}</span>
                  <span className="font-medium tabular-nums text-[var(--tessera-text)]">
                    {r.value}
                  </span>
                </li>
              ))}
            </ul>
            <Link
              href={agentPath(agentId, "historique") as Route}
              className="mt-2 flex items-center gap-1 self-start text-[0.66rem] text-[var(--tessera-fg-accent)] hover:text-[var(--tessera-text-strong)]"
            >
              {labels.results_cta} <ChevronRight className="h-3.5 w-3.5" />
            </Link>
          </DetailBlock>
        ) : null}

        {tab === tabs[3] ? (
          <div>
            <h3 className="mb-2 text-[0.7rem] font-semibold text-[var(--tessera-text)]">
              {labels.activity_title}
            </h3>
            <ul className="flex flex-col gap-2 text-[0.72rem]">
              {activity.map((it) => (
                <li key={it.label} className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />
                  <span className="text-[var(--tessera-text)]">{it.label}</span>
                  <span className="ml-auto shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
                    {it.time}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </section>
  );
}

function DetailBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5">
      <h3 className="mb-2 text-[0.7rem] font-semibold text-[var(--tessera-text)]">{title}</h3>
      {children}
    </div>
  );
}
