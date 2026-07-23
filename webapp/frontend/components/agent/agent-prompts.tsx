"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Boxes,
  CalendarClock,
  Check,
  ChevronDown,
  ChevronRight,
  Code2,
  Copy,
  FileCode2,
  FlaskConical,
  Hash,
  Languages,
  type LucideIcon,
  Plus,
  Ruler,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import type { Route } from "next";
import { useSession } from "next-auth/react";
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
import { fetchAgentPrompts, proposePromptOverlay, reviewPromptOverlay } from "@/lib/api/client";
import type { AgentPrompts as Data, PromptOverlay } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import { useAgentId } from "@/lib/use-agent-id";
import { AgentCrossLinks } from "./agent-cross-links";
import { AgentSubtabs } from "./agent-subtabs";
import { DefineInstanceBanner } from "./define-instance-banner";
import { I18nTab, VariablesTab } from "./prompt-tabs";

type RowT = NonNullable<Data["table"]>["rows"][number];
type DetailT = NonNullable<Data["details"]>[number];

const KPI_ICONS: LucideIcon[] = [FileCode2, Boxes, Languages, Hash, Ruler, Languages];
const TYPE_TONE: Record<string, string> = {
  orch: "border-violet-500/30 bg-violet-500/15 text-violet-300",
  syn: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  rep: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  mem: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
};
const QUALITY_DOT: Record<string, string> = {
  good: "bg-emerald-400",
  warn: "bg-amber-400",
  mut: "bg-slate-500",
};
const WATCH_DOT: Record<string, string> = {
  warn: "bg-amber-400",
  info: "bg-sky-400",
  crit: "bg-red-400",
};
const COV_BAR: Record<string, string> = {
  green: "bg-emerald-500",
  amber: "bg-amber-500",
  red: "bg-red-500",
};

const ALL = "all" as const;

/** Close a popover on outside-click and Escape; attach the returned ref to its root. */
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

export function AgentPrompts() {
  const t = useTranslations("agentPrompts");
  const locale = useLocale();
  const agentId = useAgentId();
  const temporal = useTemporalState();
  const railTimeline = useRailTimeline();
  // OT-01: the SR-01 rail's as-of instant ALSO bounds the per-object overlay
  // decision history at T (one rail drives both readings) and freezes the
  // overlay mutations — one does not act in the past.
  const { asOf } = temporal;
  const [subtab, setSubtab] = useState("");
  const { data } = useQuery({
    queryKey: ["agent-prompts", agentId, locale, asOf ?? null],
    queryFn: ({ signal }) => fetchAgentPrompts(agentId, locale, asOf, signal),
    staleTime: 30_000,
    refetchInterval: asOf ? false : 30_000,
  });

  const [search, setSearch] = useState("");
  const [cat, setCat] = useState<string>(ALL);
  const [vars, setVars] = useState<string>(ALL);
  const [selected, setSelected] = useState<string | null>(null);

  const rows = data?.table?.rows ?? [];
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter(
      (r) =>
        (q === "" || r.name.toLowerCase().includes(q) || r.key.toLowerCase().includes(q)) &&
        (cat === ALL || r.type_tone === cat) &&
        (vars === ALL || (vars === "with" ? r.vars_count > 0 : r.vars_count === 0)),
    );
  }, [rows, search, cat, vars]);

  const details = data?.details ?? [];
  const detail = details.find((d) => d.key === selected) ?? details[0] ?? null;

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
  // Gate by index, not label: subtab labels are localized (FR/DE/EN).
  const activeIdx = Math.max(0, subtabs.indexOf(active));
  const anyFilter = search !== "" || cat !== ALL || vars !== ALL;
  const resetAll = () => {
    setSearch("");
    setCat(ALL);
    setVars(ALL);
  };
  return (
    <div className="flex flex-col gap-2.5 pb-2 text-[var(--tessera-text)]">
      <AgentCrossLinks page="prompts" />
      <div className="flex flex-wrap items-center justify-end gap-2">
        <button
          type="button"
          onClick={() => temporal.changeMode("history")}
          className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          <CalendarClock className="h-4 w-4" /> {a?.asof}
        </button>
        <Link
          href={"/assistant" as Route}
          className="flex h-9 items-center gap-2 rounded-md border border-[#7c5cf5] bg-[#6d4aed] px-3 text-xs font-medium text-white hover:bg-[#7c5cf5]"
        >
          <Plus className="h-4 w-4" /> {a?.create}
        </Link>
      </div>

      <AgentSubtabs tabs={subtabs} active={active} onSelect={setSubtab} />

      {activeIdx === 0 ? (
        <>
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

          <Snapshot data={data} />

          <DefineInstanceBanner
            definition={data.definition}
            governanceBanner={data.governance_banner}
            instanceLabel="Configuration pour cet agent (instance)"
            instanceHint="prompts actifs · édités par PR Git"
          />

          <OverlayPanel overlay={data.overlay} agentId={agentId} frozen={asOf != null} />

          <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
            {(data.kpis ?? []).map((k, i) => (
              <Kpi key={k.key} kpi={k} Icon={KPI_ICONS[i % KPI_ICONS.length] ?? FileCode2} />
            ))}
          </div>

          <div className="grid gap-2.5 xl:grid-cols-12">
            <div className="flex min-w-0 flex-col gap-2.5 xl:col-span-8">
              <Filters
                data={data}
                search={search}
                setSearch={setSearch}
                cat={cat}
                setCat={setCat}
                vars={vars}
                setVars={setVars}
                rows={rows}
                anyFilter={anyFilter}
                onReset={resetAll}
              />
              {anyFilter ? (
                <div className="flex flex-wrap items-center gap-1.5" aria-live="polite">
                  {search !== "" ? (
                    <Chip
                      label={`${t("searchPrefix")}: ${search}`}
                      onRemove={() => setSearch("")}
                    />
                  ) : null}
                  {cat !== ALL ? (
                    <Chip
                      label={labelFor(rows, "type_tone", "type", cat)}
                      onRemove={() => setCat(ALL)}
                    />
                  ) : null}
                  {vars !== ALL ? (
                    <Chip
                      label={vars === "with" ? t("withVariables") : t("withoutVariables")}
                      onRemove={() => setVars(ALL)}
                    />
                  ) : null}
                  <button
                    type="button"
                    onClick={resetAll}
                    className="text-[0.66rem] text-[#b9a6ff] hover:text-white"
                  >
                    {t("clearAll")}
                  </button>
                </div>
              ) : null}
              <PromptsTable
                data={data}
                rows={filtered}
                total={rows.length}
                selected={detail?.key ?? null}
                onSelect={setSelected}
              />
              <div className="grid gap-2.5 md:grid-cols-3">
                <Watch data={data} />
                <Quick data={data} />
                <ByType data={data} />
              </div>
            </div>
            <Detail detail={detail} className="xl:col-span-4" />
          </div>

          <Footer data={data} />
        </>
      ) : null}

      {activeIdx === 1 ? <VariablesTab data={data} /> : null}
      {activeIdx === 2 ? <I18nTab data={data} /> : null}
    </div>
  );
}

function labelFor(
  rows: RowT[],
  keyField: keyof RowT,
  labelField: keyof RowT,
  value: string,
): string {
  const hit = rows.find((r) => String(r[keyField]) === value);
  return hit ? String(hit[labelField]) : value;
}

function Chip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-0.5 text-[0.64rem] text-[var(--tessera-text)]">
      <Truncate full={label} className="max-w-[220px]">
        {label}
      </Truncate>
      <button type="button" onClick={onRemove} aria-label={`Remove ${label}`}>
        <X className="h-3 w-3 text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]" />
      </button>
    </span>
  );
}

function Snapshot({ data }: { data: Data }) {
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
          <span className="font-mono text-[0.8rem] font-medium text-[var(--tessera-text)]">
            {s.version}
          </span>
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
      {/* No as-of control here: this snapshot is the CURRENT prompt base only.
          The inert "as-of" span that used to sit here looked like a control for
          a time-travel the page cannot serve (registre §1); per-object history
          is OT-01, still to build. */}
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
    <div className="flex h-[88px] flex-col justify-between rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="flex items-center gap-2">
        <Icon className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
        <Truncate full={kpi.label} className="text-[0.64rem] text-[var(--tessera-text-muted)]">
          {kpi.label}
        </Truncate>
        <CardInfo ns="agentPrompts" k={kpi.key} title={kpi.label} />
      </div>
      {kpi.gauge !== null ? (
        <div className="flex items-center gap-2">
          <Gauge pct={kpi.gauge} />
          <span className="text-[0.78rem] font-medium text-emerald-300">{kpi.value}</span>
        </div>
      ) : (
        <div>
          <p className="text-[1.3rem] font-semibold tabular-nums text-[var(--tessera-text)]">
            {kpi.value}
          </p>
          {kpi.delta ? (
            <p
              className={cn(
                "text-[0.6rem] tabular-nums",
                kpi.good ? "text-emerald-400" : "text-red-400",
              )}
            >
              {kpi.delta}
            </p>
          ) : null}
        </div>
      )}
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
          className="absolute left-0 z-20 mt-1 w-52 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-1 shadow-lg"
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
              {o.value === value ? <span className="text-[#5fd0c6]">&bull;</span> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function Filters({
  data,
  search,
  setSearch,
  cat,
  setCat,
  vars,
  setVars,
  rows,
  anyFilter,
  onReset,
}: {
  data: Data;
  search: string;
  setSearch: (v: string) => void;
  cat: string;
  setCat: (v: string) => void;
  vars: string;
  setVars: (v: string) => void;
  rows: RowT[];
  anyFilter: boolean;
  onReset: () => void;
}) {
  const t = useTranslations("agentPrompts");
  const f = data.filters;
  if (!f) return null;
  const allF = f.selects[0]?.value ?? "Toutes";
  const catOptions = [{ value: ALL, label: allF }, ...dedupe(rows, "type_tone", "type")];
  const varOptions = f.var_options ?? [{ value: ALL, label: allF }];
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5">
      <div className="flex h-9 min-w-[200px] flex-1 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5">
        <Search className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={f.search}
          aria-label={f.search}
          className="w-full bg-transparent text-[0.74rem] text-[var(--tessera-text)] outline-none placeholder:text-[var(--tessera-text-muted)]"
        />
      </div>
      <FilterDropdown
        label={f.selects[0]?.label ?? t("filterCategory")}
        value={cat}
        options={catOptions}
        onSelect={setCat}
      />
      <FilterDropdown
        label={f.selects[1]?.label ?? t("filterVariables")}
        value={vars}
        options={varOptions}
        onSelect={setVars}
      />
      {anyFilter ? (
        <button
          type="button"
          onClick={onReset}
          className="flex h-9 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[0.74rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          <SlidersHorizontal className="h-3.5 w-3.5" /> {t("reset")}
        </button>
      ) : null}
    </div>
  );
}

function dedupe(rows: RowT[], keyField: keyof RowT, labelField: keyof RowT) {
  const seen = new Map<string, string>();
  for (const r of rows) seen.set(String(r[keyField]), String(r[labelField]));
  return [...seen.entries()].map(([value, label]) => ({ value, label }));
}

function PromptsTable({
  data,
  rows,
  total,
  selected,
  onSelect,
}: {
  data: Data;
  rows: RowT[];
  total: number;
  selected: string | null;
  onSelect: (key: string) => void;
}) {
  const t = useTranslations("agentPrompts");
  const tbl = data.table;
  if (!tbl) return null;
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse text-left">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {tbl.columns.map((c, i) => (
                <th
                  key={c}
                  className={cn("px-3 py-2 font-medium", i === 0 ? "" : "whitespace-nowrap")}
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={tbl.columns.length}
                  className="px-3 py-10 text-center text-[0.74rem] text-[var(--tessera-text-muted)]"
                >
                  {t("noResults")}
                </td>
              </tr>
            ) : (
              rows.map((r) => {
                const on = r.key === selected;
                return (
                  <tr
                    key={r.key}
                    // biome-ignore lint/a11y/useSemanticElements: a data row selects the prompt and stays keyboard reachable
                    role="button"
                    tabIndex={0}
                    aria-label={r.name}
                    aria-pressed={on}
                    onClick={() => onSelect(r.key)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onSelect(r.key);
                      }
                    }}
                    className={cn(
                      "cursor-pointer border-b border-[var(--tessera-border)]/60 last:border-0 focus:outline-none focus-visible:ring-1 focus-visible:ring-[#7c5cf5]",
                      on ? "bg-[#6d4aed]/10" : "hover:bg-[var(--tessera-bg)]/40",
                    )}
                  >
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2">
                        <FileCode2 className="h-4 w-4 shrink-0 text-[#8b7cf0]" />
                        <Truncate
                          full={r.name}
                          className="text-[0.74rem] font-medium text-[var(--tessera-text)]"
                        >
                          {r.name}
                        </Truncate>
                      </div>
                    </td>
                    <td className="px-3 py-2.5">
                      <span
                        className={cn(
                          "rounded-full border px-2 py-0.5 text-[0.58rem] font-medium",
                          TYPE_TONE[r.type_tone] ?? TYPE_TONE.rep,
                        )}
                      >
                        {r.type}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="inline-flex items-center gap-1.5 text-[0.68rem] text-emerald-300">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                        {r.status}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 font-mono text-[0.66rem] text-[var(--tessera-text)]">
                      {r.version}
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="inline-flex items-center gap-1.5 text-[0.7rem] tabular-nums text-[var(--tessera-text)]">
                        <span
                          className={cn(
                            "h-1.5 w-1.5 rounded-full",
                            QUALITY_DOT[r.quality_tone] ?? "bg-slate-400",
                          )}
                        />
                        {r.quality}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-[0.7rem] tabular-nums text-[var(--tessera-text-muted)]">
                      {r.updated}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 font-mono text-[0.64rem] text-[var(--tessera-text-muted)]">
                      {r.owner}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2.5 text-[0.7rem] tabular-nums text-[var(--tessera-text-muted)]">
                      {r.tests}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between border-t border-[var(--tessera-border)] px-3 py-2 text-[0.64rem] text-[var(--tessera-text-muted)]">
        <span>{t("promptCount", { shown: rows.length, total })}</span>
      </div>
    </section>
  );
}

function PanelCard({
  title,
  info,
  cta,
  href,
  children,
}: {
  title: string;
  info?: React.ReactNode;
  cta?: string;
  href?: Route;
  children: React.ReactNode;
}) {
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <h3 className="mb-2 flex items-center gap-1 text-[0.74rem] font-semibold text-[var(--tessera-text)]">
        {title}
        {info}
      </h3>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
      {cta && href ? (
        <Link
          href={href}
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
  const agentId = useAgentId();
  if (!w) return null;
  return (
    <PanelCard
      title={w.title}
      info={<CardInfo ns="agentPrompts" k="watch" title={w.title} />}
      cta={w.cta}
      href={agentPath(agentId, "evaluations") as Route}
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
              <span className="block text-[0.72rem] leading-snug text-[var(--tessera-text)]">
                {it.title}
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
  if (!q) return null;
  const icons = [Code2, FlaskConical, CalendarClock, Boxes];
  return (
    <PanelCard title={q.title} info={<CardInfo ns="agentPrompts" k="quick" title={q.title} />}>
      <div className="grid grid-cols-2 gap-2">
        {q.items.map((it, i) => {
          const Icon = icons[i % icons.length] ?? FlaskConical;
          return (
            <Link
              key={it.href}
              href={it.href as Route}
              className="flex flex-col items-start gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2 text-left text-[0.68rem] text-[var(--tessera-text)] hover:border-[#7c5cf5]/50"
            >
              <Icon className="h-4 w-4 text-[#b9a6ff]" />
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

function ByType({ data }: { data: Data }) {
  const b = data.by_type;
  if (!b) return null;
  return (
    <PanelCard title={b.title} info={<CardInfo ns="agentPrompts" k="by_type" title={b.title} />}>
      <ul className="flex flex-col gap-2.5">
        {b.items.map((it) => (
          <li key={it.label} className="flex flex-col gap-1">
            <div className="flex items-center justify-between text-[0.7rem]">
              <span className="text-[var(--tessera-text)]">{it.label}</span>
              <span className="tabular-nums text-[var(--tessera-text-muted)]">{it.value}</span>
            </div>
            <div className="h-[4px] overflow-hidden rounded-full bg-[var(--tessera-border)]">
              <div
                className={cn("h-full rounded-full", COV_BAR[it.tone] ?? "bg-slate-500")}
                style={{ width: `${it.pct}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </PanelCard>
  );
}

function Detail({ detail, className }: { detail: DetailT | null; className?: string }) {
  const t = useTranslations("agentPrompts");
  const [tab, setTab] = useState(0);
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset tab on prompt change
  useEffect(() => setTab(0), [detail?.key]);
  if (!detail) return null;
  const d = detail;
  return (
    <section
      className={cn(
        "flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]",
        className,
      )}
    >
      <div className="border-b border-[var(--tessera-border)] px-3.5 py-3">
        <p className="text-[0.62rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
          {t("detailEyebrow")}
        </p>
        <div className="mt-1 flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <FileCode2 className="h-4 w-4 shrink-0 text-[#8b7cf0]" />
            <span className="min-w-0">
              <Truncate
                full={d.name}
                className="text-[0.85rem] font-semibold text-[var(--tessera-text)]"
              >
                {d.name}
              </Truncate>
              <Truncate
                full={d.id}
                className="font-mono text-[0.58rem] text-[var(--tessera-text-muted)]"
              >
                {d.id}
              </Truncate>
            </span>
          </div>
          <span className="shrink-0 rounded-full border border-emerald-500/30 bg-emerald-500/15 px-2 py-0.5 text-[0.6rem] font-medium text-emerald-300">
            {d.status}
          </span>
        </div>
      </div>

      <nav className="flex items-center gap-4 border-b border-[var(--tessera-border)] px-3.5">
        {d.tabs.map((tb, i) => {
          const on = i === tab;
          return (
            <button
              key={tb}
              type="button"
              onClick={() => setTab(i)}
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
        {tab === 0 ? (
          <>
            <div>
              <h3 className="mb-1 text-[0.7rem] font-semibold text-[var(--tessera-text)]">
                {t("descriptionLabel")}
              </h3>
              <p className="text-[0.72rem] leading-relaxed text-[var(--tessera-text-muted)]">
                {d.description}
              </p>
            </div>
            <ul className="flex flex-col gap-1.5 text-[0.72rem]">
              {d.fields.map((f) => (
                <li key={f.label} className="flex items-center justify-between gap-2">
                  <span className="text-[var(--tessera-text-muted)]">{f.label}</span>
                  <span className="font-medium text-[var(--tessera-text)]">{f.value}</span>
                </li>
              ))}
            </ul>
            <div>
              <p className="mb-1.5 text-[0.66rem] text-[var(--tessera-text-muted)]">
                {d.tags_label}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {d.tags.map((tg) => (
                  <span
                    key={tg}
                    className="rounded border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-0.5 font-mono text-[0.62rem] text-[var(--tessera-text-muted)]"
                  >
                    {tg}
                  </span>
                ))}
              </div>
            </div>
          </>
        ) : null}

        {tab === 1 ? <Content content={d.content} /> : null}

        {tab === 2 ? (
          <>
            <DetailBlock title={d.config_title}>
              <ul className="flex flex-col gap-1.5 text-[0.72rem]">
                {d.config.map((c) => (
                  <li key={c.label} className="flex items-center justify-between gap-2">
                    <span className="text-[var(--tessera-text-muted)]">{c.label}</span>
                    <Truncate
                      full={c.value}
                      className="min-w-0 font-medium text-[var(--tessera-text)]"
                    >
                      {c.value}
                    </Truncate>
                  </li>
                ))}
              </ul>
            </DetailBlock>
            <DetailBlock title={d.rbac_title}>
              <ul className="flex flex-col gap-1.5 text-[0.72rem]">
                {d.rbac.map((r) => (
                  <li key={r.role} className="flex items-center justify-between gap-2">
                    <span className="text-[var(--tessera-text-muted)]">{r.role}</span>
                    <span className="font-medium tabular-nums text-[var(--tessera-text)]">
                      {r.access}
                    </span>
                  </li>
                ))}
              </ul>
            </DetailBlock>
            <div>
              <h3 className="mb-2 text-[0.7rem] font-semibold text-[var(--tessera-text)]">
                {d.info_title}
              </h3>
              <ul className="flex flex-col gap-1.5 text-[0.72rem]">
                {d.info.map((it) => (
                  <li key={it.label} className="flex items-center justify-between gap-2">
                    <span className="text-[var(--tessera-text-muted)]">{it.label}</span>
                    <span className="font-medium text-[var(--tessera-text)]">{it.value}</span>
                  </li>
                ))}
              </ul>
            </div>
          </>
        ) : null}
      </div>
    </section>
  );
}

function Content({ content }: { content: DetailT["content"] }) {
  const t = useTranslations("agentPrompts");
  const [copied, setCopied] = useState<string | null>(null);
  const copy = async (lang: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(lang);
      setTimeout(() => setCopied((c) => (c === lang ? null : c)), 1500);
    } catch {
      // clipboard may be unavailable; ignore
    }
  };
  return (
    <div className="flex flex-col gap-3">
      {content.map((c) => (
        <div key={c.lang}>
          <div className="mb-1 flex items-center justify-between">
            <span className="font-mono text-[0.62rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {c.lang}
            </span>
            <button
              type="button"
              onClick={() => copy(c.lang, c.text)}
              className="flex items-center gap-1 text-[0.62rem] text-[#b9a6ff] hover:text-white"
            >
              {copied === c.lang ? (
                <>
                  <Check className="h-3 w-3" /> {t("copied")}
                </>
              ) : (
                <>
                  <Copy className="h-3 w-3" /> {t("copy")}
                </>
              )}
            </button>
          </div>
          <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5 font-mono text-[0.66rem] leading-relaxed text-[var(--tessera-text)]">
            {c.text}
          </pre>
        </div>
      ))}
    </div>
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

function Footer({ data }: { data: Data }) {
  const f = data.footer;
  if (!f?.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-1 border-t border-[var(--tessera-border)] pt-2 text-[0.64rem] text-[var(--tessera-text-muted)]">
      {f.map((it) => (
        <span key={it.label}>
          {it.label} : <span className="text-[var(--tessera-text)]">{it.value}</span>
        </span>
      ))}
    </div>
  );
}

/** ADR 0037 — the one governed exception to this page's read-only rule.
 *  An operator proposes an overlay draft (guard-screened server-side); only a
 *  superadmin approves / rejects / revokes, and never the draft's own author
 *  (two-person rule, enforced server-side — the UI reflects it honestly). */
function OverlayPanel({
  overlay,
  agentId,
  frozen = false,
}: { overlay?: PromptOverlay; agentId: string; frozen?: boolean }) {
  const qc = useQueryClient();
  const role = useSession().data?.user?.role;
  const isSuper = role === "superadmin";
  const [text, setText] = useState("");
  const [rawBusy, setBusy] = useState(false);
  // While As-of, every overlay act is frozen (registre §6, agir-rail rule).
  const busy = rawBusy || frozen;
  const [error, setError] = useState<string | null>(null);
  if (!overlay) return null;
  const L = overlay.labels;
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      setText("");
      await qc.invalidateQueries({ queryKey: ["agent-prompts"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };
  const reviewBtn =
    "h-7 rounded-md border px-2.5 text-[0.68rem] font-medium disabled:cursor-not-allowed disabled:opacity-50";
  return (
    <section
      data-testid="prompt-overlay"
      className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3"
    >
      <h3 className="flex items-center gap-1 text-[0.82rem] font-semibold text-[var(--tessera-text)]">
        {overlay.title}
        <CardInfo ns="agentPrompts" k="overlay" title={overlay.title} />
      </h3>
      <p className="mt-0.5 text-[0.64rem] leading-relaxed text-[var(--tessera-text-muted)]">
        {overlay.note}
      </p>

      <div className="mt-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2">
        <span className="text-[0.68rem] font-medium text-[var(--tessera-text)]">{L.serving}</span>
        {overlay.approved ? (
          <>
            <pre className="mt-1 whitespace-pre-wrap font-mono text-[0.68rem] text-[var(--tessera-text)]">
              {overlay.approved.text}
            </pre>
            <p className="mt-1 text-[0.6rem] text-[var(--tessera-text-muted)]">
              {L.provenance} {overlay.approved.author} · {L.approved_by}{" "}
              {overlay.approved.approved_by} ·{" "}
              {new Date(overlay.approved.at).toLocaleString("fr-FR", {
                dateStyle: "short",
                timeStyle: "short",
              })}
            </p>
            <span title={isSuper ? undefined : L.superadmin_only}>
              <button
                type="button"
                disabled={!isSuper || busy}
                onClick={() => run(() => reviewPromptOverlay(agentId, "revoke"))}
                className={cn(reviewBtn, "mt-1.5 border-amber-400/40 text-amber-300")}
              >
                {L.revoke}
              </button>
            </span>
          </>
        ) : (
          <p className="mt-1 text-[0.64rem] italic text-[var(--tessera-text-muted)]">{L.none}</p>
        )}
      </div>

      {overlay.draft ? (
        <div className="mt-2 rounded-md border border-sky-500/30 bg-sky-500/5 px-2.5 py-2">
          <span className="text-[0.68rem] font-medium text-sky-300">{L.pending}</span>
          <pre className="mt-1 whitespace-pre-wrap font-mono text-[0.68rem] text-[var(--tessera-text)]">
            {overlay.draft.text || "∅"}
          </pre>
          <p className="mt-1 text-[0.6rem] text-[var(--tessera-text-muted)]">
            {L.provenance} {overlay.draft.author} ·{" "}
            {new Date(overlay.draft.at).toLocaleString("fr-FR", {
              dateStyle: "short",
              timeStyle: "short",
            })}
          </p>
          <span
            title={isSuper ? undefined : L.superadmin_only}
            className="mt-1.5 inline-flex gap-2"
          >
            <button
              type="button"
              disabled={!isSuper || busy}
              onClick={() => run(() => reviewPromptOverlay(agentId, "approve"))}
              className={cn(reviewBtn, "border-emerald-400/40 text-emerald-300")}
            >
              {L.approve}
            </button>
            <button
              type="button"
              disabled={!isSuper || busy}
              onClick={() => run(() => reviewPromptOverlay(agentId, "reject"))}
              className={cn(reviewBtn, "border-rose-400/40 text-rose-300")}
            >
              {L.reject}
            </button>
          </span>
        </div>
      ) : null}

      {/* OT-01 per-object trace: the lifecycle history the backend has served
          since ADR 0037 — proposed / approved / rejected / revoked, each event
          naming its author (ADR 0024). */}
      {overlay.history.length > 0 ? (
        <div className="mt-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2">
          <span className="text-[0.68rem] font-medium text-[var(--tessera-text)]">{L.history}</span>
          <ul className="mt-1 flex flex-col gap-0.5">
            {overlay.history.map((h) => (
              <li
                key={`${h.at}-${h.event}-${h.author}`}
                className="flex flex-wrap items-center gap-1.5 text-[0.62rem] text-[var(--tessera-text-muted)]"
              >
                <span className="tabular-nums">
                  {new Date(h.at).toLocaleString("fr-FR", {
                    dateStyle: "short",
                    timeStyle: "short",
                  })}
                </span>
                <span className="font-medium text-[var(--tessera-text)]">
                  {L[`event_${h.event}`] ?? h.event}
                </span>
                <span>· {h.author}</span>
                {h.chars > 0 ? (
                  <span className="tabular-nums">
                    · {h.chars} {L.chars}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="mt-2 flex flex-col gap-1.5">
        <textarea
          aria-label={L.propose}
          placeholder={L.placeholder}
          maxLength={overlay.max_chars}
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="min-h-[64px] rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1.5 text-[0.7rem] text-[var(--tessera-text)] placeholder:text-[var(--tessera-text-muted)]"
        />
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => run(() => proposePromptOverlay(agentId, text))}
            className={cn(reviewBtn, "border-[#2e72d2] bg-[#1b4f8a] text-[#d8eaff]")}
          >
            {L.propose}
          </button>
          <span className="text-[0.6rem] tabular-nums text-[var(--tessera-text-muted)]">
            {text.length}/{overlay.max_chars}
          </span>
          {error ? <span className="text-[0.62rem] text-rose-300">{error}</span> : null}
        </div>
      </div>
    </section>
  );
}
