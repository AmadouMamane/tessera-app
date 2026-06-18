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
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  TemporalRail,
  useRailTimeline,
  useTemporalState,
} from "@/components/overview/temporal-rail";
import { Link } from "@/i18n/navigation";
import { agentPath } from "@/lib/agent-context";
import { fetchAgentEvaluations, requestAgentRelease } from "@/lib/api/client";
import type { AgentEvaluations as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import { useAgentId } from "@/lib/use-agent-id";
import { AgentSubtabs } from "./agent-subtabs";

type RowT = NonNullable<Data["table"]>["rows"][number];

const KPI_ICONS: LucideIcon[] = [Sparkles, Target, ShieldCheck, BarChart3, Layers, Target];
const TYPE_TONE: Record<string, string> = {
  sys: "border-violet-500/30 bg-violet-500/15 text-violet-300",
  tpl: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  agt: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
};
const STATUS_TONE: Record<string, string> = {
  good: "text-emerald-300",
  info: "text-sky-300",
  off: "text-[var(--tessera-text-muted)]",
};
const STATUS_DOT: Record<string, string> = {
  good: "bg-emerald-400",
  info: "bg-sky-400",
  off: "bg-slate-500",
};
const TONE_TEXT: Record<string, string> = {
  good: "text-emerald-400",
  bad: "text-red-400",
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
  const temporal = useTemporalState();
  const railTimeline = useRailTimeline();
  const [subtab, setSubtab] = useState("");
  const agentId = useAgentId();
  const { data } = useQuery({
    queryKey: ["agent-evaluations", agentId],
    queryFn: ({ signal }) => fetchAgentEvaluations(agentId, signal),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  const [search, setSearch] = useState("");
  const [typeKey, setTypeKey] = useState("all");
  const [qualityKey, setQualityKey] = useState("all");
  const [hallucKey, setHallucKey] = useState("all");
  const [sortCol, setSortCol] = useState<number | null>(4);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const [selected, setSelected] = useState<string | null>(null);

  const allRows = data?.table?.rows ?? [];
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
  return (
    <div className="flex flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <button
          type="button"
          onClick={() => temporal.changeMode("replay")}
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

      <VerdictBanner data={data} />

      <LiensUtiles />

      <GatePolicySection data={data} />

      <TemporalRail
        mode={temporal.mode}
        liveStatus={t("realtime")}
        timeline={railTimeline.data}
        selectedAt={temporal.selectedAt}
        onSelectedAtChange={temporal.setSelectedAt}
        periodKey={temporal.periodKey}
        onPeriodChange={temporal.setPeriodKey}
        onModeChange={temporal.changeMode}
      />

      <Snapshot data={data} onAsof={() => temporal.changeMode("replay")} />

      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
        {(data.kpis ?? []).map((k, i) => (
          <Kpi key={k.key} kpi={k} Icon={KPI_ICONS[i % KPI_ICONS.length] ?? Sparkles} />
        ))}
      </div>

      <GateJudgeRail data={data} />

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
          <div className="grid gap-2.5 md:grid-cols-3">
            <Watch data={data} />
            <Quick data={data} />
            <Trend data={data} />
          </div>
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
  const agentId = useAgentId();
  const [state, setState] = useState<"idle" | "pending" | "done">("idle");
  const [result, setResult] = useState<{ allowed: boolean; reason: string } | null>(null);

  async function onClick() {
    setState("pending");
    try {
      const r = await requestAgentRelease(agentId);
      setResult({ allowed: r.allowed, reason: r.reason });
    } catch {
      setResult({ allowed: false, reason: "échec de la demande de mise en prod." });
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
        Promouvoir en prod (gated)
      </button>
      {result ? (
        <span className="text-[10px] opacity-90">
          {result.allowed ? "✓ Promu (live)" : "✗ Bloqué"} — {result.reason}
        </span>
      ) : null}
    </div>
  );
}

/** P3 — cross-links making the control plane navigable: definition (CONFIGURER),
 *  governance (AGIR Release Control), linked data (applied garde-fous, knowledge). */
function LiensUtiles() {
  const agentId = useAgentId();
  const items: { href: Route; label: string }[] = [
    { href: ("/agir/release-control?agent=" + agentId) as Route, label: "Gouvernance · Release Control" },
    { href: "/configurer/parametres" as Route, label: "Définition · jeu d'éval (CONFIGURER)" },
    { href: agentPath(agentId, "garde-fous") as Route, label: "Garde-fous appliqués" },
    { href: agentPath(agentId, "connaissances") as Route, label: "Connaissances liées" },
  ];
  return (
    <section className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2">
      <span className="text-[10px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
        Liens utiles
      </span>
      {items.map((it) => (
        <Link
          key={it.label}
          href={it.href}
          className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface-2)] px-2 py-1 text-[11px] text-[var(--tessera-text)] transition-colors hover:border-[#7c5cf5]/50 hover:text-white"
        >
          {it.label} →
        </Link>
      ))}
    </section>
  );
}

/** Release-gate verdict as the page headline (policy §6: the verdict — not the
 *  aggregate score — is the title). Full-width banner, colour tied to conformity. */
function VerdictBanner({ data }: { data: Data }) {
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
    ? "text-[#ff9bb0]"
    : passed
      ? "text-[#7fe3b3]"
      : "text-[var(--tessera-text)]";
  const bd = gate.breakdown;
  const bg = gate.breakdown_grain;
  return (
    <section className={`flex flex-col gap-2 rounded-lg border p-3.5 ${tone}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          {blocked ? (
            <ShieldAlert className="h-6 w-6 shrink-0 text-[#ff9bb0]" />
          ) : passed ? (
            <ShieldCheck className="h-6 w-6 shrink-0 text-[#7fe3b3]" />
          ) : (
            <Shield className="h-6 w-6 shrink-0 text-[var(--tessera-text-muted)]" />
          )}
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              Verdict du gate de release
            </p>
            <p className={`text-[1.15rem] font-semibold leading-tight ${labelColor}`}>
              {gate.label}
            </p>
            {gate.reason ? (
              <p className="mt-0.5 text-[11px] text-[var(--tessera-text-muted)]">{gate.reason}</p>
            ) : null}
            {blocked && socleFails.length > 0 ? (
              <p className="mt-1 text-[11px] text-[#ff9bb0]">
                <span className="text-[var(--tessera-text-muted)]">Cœur non dérogeable en échec : </span>
                <span className="font-mono font-medium">{socleFails.join(", ")}</span>
                {" — "}
                <Link
                  href={"/agir/release-control?agent=" + agentId as Route}
                  className="underline underline-offset-2 hover:text-white"
                >
                  remédier dans Release Control →
                </Link>
              </p>
            ) : null}
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          {gate.grains ? (
            <span className="text-[10px] text-[var(--tessera-text-muted)]">
              {gate.grains.executions} exéc. · {gate.grains.distinct_cases} cas ·{" "}
              {gate.grains.socle_cases} socle
            </span>
          ) : null}
          <ReleaseControl />
        </div>
      </div>
      <div className="grid gap-2 text-[11px] sm:grid-cols-3">
        <div className="rounded-md border border-[var(--tessera-border)]/60 bg-black/15 px-2.5 py-2">
          <span className="text-[var(--tessera-text-muted)]">Socle dur (T0, zéro tolérance)</span>
          <p
            className={`mt-0.5 font-medium ${gate.socle?.ok ? "text-[#7fe3b3]" : "text-[#ff9bb0]"}`}
          >
            {gate.socle
              ? gate.socle.ok
                ? `Conforme — ${gate.socle.passed}/${gate.socle.total}`
                : `ÉCHEC — ${gate.socle.passed}/${gate.socle.total} réussis`
              : gate.failed_critical.length > 0
                ? "Échec"
                : "Conforme"}
          </p>
        </div>
        <div className="rounded-md border border-[var(--tessera-border)]/60 bg-black/15 px-2.5 py-2">
          <span className="text-[var(--tessera-text-muted)]">Gate domaine (T2)</span>
          <p
            className={`mt-0.5 font-medium ${gate.domain?.ok ? "text-[#7fe3b3]" : "text-[#ffce8a]"}`}
          >
            {gate.domain ? `${gate.domain.passed}/${gate.domain.total}` : `${gate.standard_passed}/${gate.standard_total}`}
            {typeof gate.min_pass_rate === "number"
              ? ` (seuil ${Math.round(gate.min_pass_rate * 100)}%)`
              : ""}
          </p>
        </div>
        <div className="rounded-md border border-[var(--tessera-border)]/60 bg-black/15 px-2.5 py-2">
          <span className="text-[var(--tessera-text-muted)]">Critiques (cas × langue)</span>
          <p className="mt-0.5 font-medium text-[var(--tessera-text)]">
            {bg
              ? `${bg.blocking_socle + bg.blocking_t1} bloquants · ${bg.waived_active} dérogé${bg.waived_active > 1 ? "s" : ""}`
              : bd
                ? `${bd.critical_blocking} bloquants · ${bd.waived} dérogé`
                : "—"}
            {bg && bg.non_executed_critical > 0 ? ` · ${bg.non_executed_critical} non exéc.` : ""}
          </p>
        </div>
      </div>
    </section>
  );
}

const VENN_TONE: Record<string, string> = {
  crit: "border-[#e0566f]/50 bg-[#e0566f]/12 text-[#ff9bb0]",
  warn: "border-amber-500/40 bg-amber-500/12 text-amber-200",
  muted: "border-[var(--tessera-border)] bg-black/15 text-[var(--tessera-text-muted)]",
};
const STATUS_PILL: Record<string, string> = {
  crit: "border-[#e0566f]/50 bg-[#e0566f]/15 text-[#ff9bb0]",
  warn: "border-amber-500/40 bg-amber-500/15 text-amber-200",
  bad: "border-orange-500/40 bg-orange-500/15 text-orange-200",
  good: "border-emerald-500/40 bg-emerald-500/15 text-emerald-200",
};

/** Policy gate detail (eval-gate-policy.md): three tiers + structural Venn, the
 *  per-category socle markers, the critical-cases table (case × langue) and the
 *  governed-waiver registry. Every count reconciles with the verdict banner. */
function GatePolicySection({ data }: { data: Data }) {
  const gate = data.gate;
  if (!gate || !gate.venn || !gate.tiers) return null;
  const v = gate.venn;
  const cc = gate.critical_cases;
  const wv = gate.waivers;
  const socleCats = gate.socle_by_category ?? [];

  return (
    <div className="flex flex-col gap-2.5">
      {/* Tiers + structural Venn + socle-by-category markers */}
      <div className="grid gap-2.5 xl:grid-cols-12">
        <section className="flex min-w-0 flex-col gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3 xl:col-span-7">
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              Appartenance structurelle (Venn) — somme = exécutions
            </span>
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-[10px]",
                v.reconciles ? "text-emerald-300" : "text-red-300",
              )}
            >
              {v.socle} + {v.t1} + {v.domaine} = {v.universe}
            </span>
          </div>
          {/* Nested: Critiques contains Socle; dérogations ⊂ T1, jamais socle */}
          <div className="rounded-md border border-[#e0566f]/40 bg-[#e0566f]/[0.06] p-2">
            <div className="mb-1 flex items-center justify-between text-[10px] text-[#ff9bb0]">
              <span>Critiques (T0 ∪ T1)</span>
              <span className="tabular-nums">{v.critiques}</span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className={cn("rounded border px-2 py-1.5", VENN_TONE.crit)}>
                <p className="text-[10px] opacity-80">Socle (T0) · non-dérogeable</p>
                <p className="text-sm font-semibold tabular-nums">{v.socle}</p>
              </div>
              <div className={cn("rounded border px-2 py-1.5", VENN_TONE.warn)}>
                <p className="text-[10px] opacity-80">Critique (T1) · dérogeable</p>
                <p className="text-sm font-semibold tabular-nums">
                  {v.t1}
                  <span className="ml-1 text-[10px] font-normal opacity-80">
                    dont {v.deroges} dérogé{v.deroges > 1 ? "s" : ""}
                  </span>
                </p>
              </div>
            </div>
          </div>
          <div className={cn("rounded border px-2 py-1.5", VENN_TONE.muted)}>
            <div className="flex items-center justify-between">
              <span className="text-[10px]">Domaine (T2) · gradé</span>
              <span className="text-sm font-semibold tabular-nums">{v.domaine}</span>
            </div>
          </div>
          <p className="text-[10px] text-[var(--tessera-text-muted)]">
            Socle ∩ dérogations = ∅ — une dérogation n&apos;est jamais effective sur le socle.
          </p>
        </section>

        {/* Socle OK / ÉCHEC per category — no green score may mask a breach */}
        <section className="flex min-w-0 flex-col gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3 xl:col-span-5">
          <span className="text-[11px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            Socle par catégorie
          </span>
          {socleCats.length === 0 ? (
            <span className="text-[11px] text-[var(--tessera-text-muted)]">
              Aucune catégorie socle.
            </span>
          ) : (
            <div className="flex flex-col gap-1.5">
              {socleCats.map((c) => (
                <div
                  key={c.category}
                  className="flex items-center justify-between rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1.5"
                >
                  <span className="truncate text-[11px] text-[var(--tessera-text)]">{c.label}</span>
                  <span
                    className={cn(
                      "shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium",
                      c.ok ? STATUS_PILL.good : STATUS_PILL.crit,
                    )}
                  >
                    {c.ok ? "Socle OK" : "Socle ÉCHEC"} · {c.passed}/{c.total}
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
                    {t.tier} · {t.waivable ? "dérogeable" : "non-dérog."}
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
              <span className="text-[10px] text-[var(--tessera-text-muted)]">{cc.total} cas</span>
            </div>
            {cc.rows.length === 0 ? (
              <span className="text-[11px] text-emerald-300">
                Aucun cas critique non concluant.
              </span>
            ) : (
              <div className="max-h-[19rem] overflow-auto">
                <table className="w-full text-left text-[11px]">
                  <thead className="sticky top-0 bg-[var(--tessera-surface)] text-[10px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
                    <tr>
                      <th className="py-1 pr-2 font-medium">Cas</th>
                      <th className="py-1 pr-2 font-medium">Tier</th>
                      <th className="py-1 pr-2 font-medium">Lg</th>
                      <th className="py-1 pr-2 font-medium">Statut gate</th>
                      <th className="py-1 font-medium">Socle</th>
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
                          {r.socle ? "Socle" : "—"}
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
                  wv.chain_verified ? "text-emerald-300" : "text-red-300",
                )}
                title="Intégrité de la chaîne de hash"
              >
                {wv.chain_verified ? "chaîne ✓" : "chaîne ✗"} · {wv.active} active
                {wv.active > 1 ? "s" : ""}/{wv.total}
              </span>
            </div>
            <p className="text-[10px] text-[var(--tessera-text-muted)]">{wv.subtitle}</p>
            <div className="flex max-h-[19rem] flex-col gap-1.5 overflow-auto">
              {wv.items.length === 0 ? (
                <span className="text-[11px] text-[var(--tessera-text-muted)]">
                  Aucune dérogation.
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
                      <span className="truncate text-[11px] font-medium text-[var(--tessera-text)]">
                        {it.case_id} · {it.language}
                      </span>
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
                    <p className="mt-0.5 line-clamp-2 text-[10px] text-[var(--tessera-text-muted)]">
                      {it.justification}
                    </p>
                    <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[9px] text-[var(--tessera-text-muted)]">
                      <span>Demande : {it.requester}</span>
                      <span>Appro. : {it.approver}</span>
                      <span>Échéance : {it.expires_at}</span>
                      {it.incident_ref ? <span>{it.incident_ref}</span> : null}
                    </div>
                    {it.controls.length > 0 ? (
                      <p className="mt-0.5 text-[9px] text-[var(--tessera-text-muted)]">
                        Contrôles : {it.controls.join(" · ")}
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

function GateJudgeRail({ data }: { data: Data }) {
  const judge = data.judge;
  const runs = data.runs;
  if (!judge && !runs) return null;

  return (
    <div className="grid gap-2.5 xl:grid-cols-12">
      {/* Per-agent judged metrics (real local judge) */}
      <section className="flex min-w-0 flex-col gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3 xl:col-span-6">
        <div className="flex items-center justify-between">
          <span className="text-[11px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            Métriques jugées
          </span>
          <span className="text-[10px] text-[var(--tessera-text-muted)]">
            {judge?.available ? (judge.judge_model ?? "") : "indisponible"}
          </span>
        </div>
        <div className="grid grid-cols-3 gap-2">
          {(
            [
              ["Fidélité", judge?.faithfulness],
              ["Ancrage", judge?.grounding],
              ["Anti-halluc.", judge?.hallucination],
            ] as const
          ).map(([label, value]) => (
            <div key={label} className="flex flex-col">
              <span className="text-base font-semibold text-[var(--tessera-text)]">
                {judge?.available ? pct(value) : "—"}
              </span>
              <span className="text-[10px] text-[var(--tessera-text-muted)]">{label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ER-01 rail: per-agent run history */}
      <section className="flex min-w-0 flex-col gap-1.5 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3 xl:col-span-6">
        <span className="text-[11px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
          {runs?.title ?? "Historique des runs"}
        </span>
        <div className="flex flex-wrap gap-1.5">
          {(runs?.items ?? []).length === 0 ? (
            <span className="text-[11px] text-[var(--tessera-text-muted)]">Aucun run.</span>
          ) : (
            (runs?.items ?? []).map((r) => (
              <div
                key={r.run_at}
                title={`${r.label} — ${r.score}/10 — ${r.gate_passed ? "validé" : "bloqué"}`}
                className="flex items-center gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 py-1"
              >
                <span
                  className={`inline-block h-1.5 w-1.5 rounded-full ${
                    r.gate_passed ? "bg-[#3fb37f]" : "bg-[#e0566f]"
                  }`}
                />
                <span className="text-[10px] text-[var(--tessera-text-muted)]">{r.label}</span>
                <span className="text-[10px] font-medium text-[var(--tessera-text)]">
                  {r.score}
                </span>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}

function Snapshot({ data, onAsof }: { data: Data; onAsof: () => void }) {
  const s = data.snapshot;
  if (!s) return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3.5 py-2.5">
      <div className="flex flex-wrap items-center gap-x-7 gap-y-2">
        <Field>
          <span className="text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            {s.tag}
          </span>
          <span className="text-[0.92rem] font-semibold text-[var(--tessera-text)]">{s.label}</span>
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
          <span className="text-[0.58rem] text-emerald-300">{s.version_status}</span>
        </Field>
        <Field>
          <span className="text-[0.6rem] text-[var(--tessera-text-muted)]">{s.evalset_label}</span>
          <span className="text-[0.82rem] font-medium text-[var(--tessera-text)]">{s.evalset}</span>
        </Field>
        <Field>
          <span className="text-[0.6rem] text-[var(--tessera-text-muted)]">{s.coverage_label}</span>
          <span className="flex items-center gap-2">
            <Gauge pct={s.coverage} />
            <span className="text-[0.7rem] text-emerald-300">{s.coverage_tone}</span>
          </span>
        </Field>
      </div>
      <div className="flex flex-col items-start gap-1 text-[0.68rem]">
        <button
          type="button"
          onClick={onAsof}
          className="inline-flex items-center gap-1 text-[#b9a6ff] hover:text-white"
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
          stroke="#34d399"
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
        <span className="truncate text-[0.64rem] text-[var(--tessera-text-muted)]">
          {kpi.label}
        </span>
      </div>
      {kpi.gauge !== null ? (
        <div className="flex items-center gap-2">
          <Gauge pct={kpi.gauge} />
          <span className="text-[0.78rem] font-medium text-emerald-300">{kpi.note}</span>
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
                kpi.note_tone === "good" ? "text-emerald-300" : "text-[var(--tessera-text-muted)]",
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
              {o.value === value ? <span className="text-[#b9a6ff]">&bull;</span> : null}
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
  const f = p.data.filters;
  if (!f) return null;
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
        label="Type"
        value={p.typeKey}
        options={opt(f.options.type, "Tous")}
        onSelect={p.setTypeKey}
      />
      <FilterDropdown
        label="Qualité"
        value={p.qualityKey}
        options={opt(f.options.quality, "Toutes")}
        onSelect={p.setQualityKey}
      />
      <FilterDropdown
        label="Hallucinations"
        value={p.hallucKey}
        options={opt(f.options.halluc, "Toutes")}
        onSelect={p.setHallucKey}
      />
      {anyActive ? (
        <button
          type="button"
          onClick={p.onReset}
          className="flex h-9 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[0.74rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          <X className="h-3.5 w-3.5" /> Réinitialiser
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
                      <Sparkles className="h-4 w-4 shrink-0 text-[#8b7cf0]" />
                      <span className="truncate text-[0.72rem] font-medium text-[var(--tessera-text)]">
                        {r.name}
                      </span>
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
                  <td className="whitespace-nowrap px-3 py-2.5 text-[0.68rem] tabular-nums text-emerald-300">
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
                ? "border-[#b9a6ff]/60 bg-[#b9a6ff]/15 font-medium text-white"
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
  const Icon = dir === "prev" ? ChevronLeft : ChevronRight;
  return (
    <button
      type="button"
      disabled={disabled}
      aria-label={dir === "prev" ? "Page précédente" : "Page suivante"}
      onClick={onClick}
      className="flex h-7 w-7 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] enabled:hover:text-[var(--tessera-text)] disabled:opacity-40"
    >
      <Icon className="h-3.5 w-3.5" />
    </button>
  );
}

function PanelCard({
  title,
  cta,
  ctaHref,
  children,
}: { title: string; cta?: string; ctaHref?: string; children: React.ReactNode }) {
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <h3 className="mb-2 text-[0.74rem] font-semibold text-[var(--tessera-text)]">{title}</h3>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
      {cta && ctaHref ? (
        <Link
          href={ctaHref as Route}
          className="mt-2.5 flex items-center gap-1 self-start text-[0.66rem] text-[#b9a6ff] hover:text-white"
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
    <PanelCard title={w.title} cta={w.cta} ctaHref={w.cta_href}>
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
              <span className="block truncate text-[0.72rem] text-[var(--tessera-text)]">
                {it.title}
              </span>
              <span className="block truncate text-[0.62rem] text-[var(--tessera-text-muted)]">
                {it.detail}
              </span>
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
    <PanelCard title={q.title}>
      <div className="grid grid-cols-2 gap-2">
        {q.items.map((it, i) => {
          const Icon = icons[i % icons.length] ?? Play;
          return (
            <Link
              key={it.key}
              href={hrefs[it.key] ?? (agentPath(agentId, "evaluations") as Route)}
              className="flex flex-col items-start gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2 text-left text-[0.68rem] text-[var(--tessera-text)] hover:border-[#7c5cf5]/50"
            >
              <Icon className="h-4 w-4 text-[#b9a6ff]" />
              <span className="min-w-0 truncate">{it.label}</span>
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
    <PanelCard title={tr.title}>
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
  const agentId = useAgentId();
  const labels = data.detail_labels;
  const meta = data.meta;
  const tabs = labels?.tabs ?? ["Résumé", "Configuration", "Résultats", "Activité"];
  const [tab, setTab] = useState(tabs[0] ?? "Résumé");
  if (!labels || !meta || !row) return null;

  const description = `Sondes de la catégorie '${row.name}' du catalogue d'échecs, exécutées sur le plus petit modèle (${meta.model}). Sur ce run, ${row.passed} cas sur ${row.total} passent.`;
  const fields: { label: string; value: string; tone?: string }[] = [
    { label: "Type", value: row.type },
    { label: "Catégorie", value: row.category_key },
    { label: "Version catalogue", value: meta.catalogue_version },
    { label: "Statut", value: row.status, tone: row.status_tone },
    { label: "Dernière exécution", value: row.last_run },
    { label: "Modèle évalué", value: meta.model },
    { label: "Cas", value: String(row.total) },
    { label: "Langues", value: meta.languages },
    { label: "Propriétaire", value: row.owner },
  ];
  const results: { label: string; value: string }[] = [
    { label: "Score", value: `${row.score} / 10` },
    { label: "Taux de réussite", value: row.success },
    { label: "Cas réussis", value: `${row.passed} / ${row.total}` },
    { label: "Cas échoués", value: `${row.failed} / ${row.total}` },
    { label: "Score global du run", value: `${meta.score10} / 10` },
    { label: "Escalades requises", value: String(meta.escalations) },
    { label: "Invocations d'outils", value: String(meta.tool_invocations) },
  ];
  const config: { label: string; value: string }[] = [
    { label: "Modèle", value: meta.model },
    { label: "Version catalogue", value: meta.catalogue_version },
    { label: "Type", value: row.type },
    { label: "Qualité", value: row.quality_label },
    { label: "Langues", value: meta.languages },
  ];
  const activity: { label: string; time: string }[] = [
    { label: "Jeu exécuté", time: row.last_run },
    {
      label: row.pass_rate >= 0.7 ? "Évaluation réussie" : "Évaluation sous le seuil",
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
            <Sparkles className="h-4 w-4 shrink-0 text-[#8b7cf0]" />
            <span className="min-w-0 truncate text-[0.85rem] font-semibold text-[var(--tessera-text)]">
              {row.name}
            </span>
          </div>
          <span className="shrink-0 rounded-full border border-emerald-500/30 bg-emerald-500/15 px-2 py-0.5 text-[0.6rem] font-medium text-emerald-300">
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
                      f.tone === "good" ? "text-emerald-300" : "text-[var(--tessera-text)]",
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
              className="mt-2 flex items-center gap-1 self-start text-[0.66rem] text-[#b9a6ff] hover:text-white"
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
