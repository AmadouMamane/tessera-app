"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowUp,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  Clock,
  Link2,
  type LucideIcon,
  Plus,
  Quote,
  Search,
  SlidersHorizontal,
  Target,
  X,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { CardInfo } from "@/components/cockpit/card-info";
import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Skeleton } from "@/components/ui/skeleton";
import { Truncate } from "@/components/ui/truncate";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { fetchAgentConnaissances, mutateConnaissancesSource } from "@/lib/api/client";
import type { AgentConnaissances as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import type { OverviewTone } from "@/lib/overview";

import { AgentCrossLinks } from "./agent-cross-links";

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

type DetailT = NonNullable<Data["details"]>[number];
type RowT = NonNullable<Data["table"]>["rows"][number];

const KPI_ICONS: LucideIcon[] = [Link2, Target, Clock, Quote, Search];
const KPI_TONE: Record<string, OverviewTone> = {
  sources: "info",
  coverage: "success",
  freshness: "neutral",
  citation: "gold",
  hitrate: "success",
};
const STATUS_TONE: Record<string, string> = {
  good: "border-emerald-500/30 bg-emerald-500/15 text-[var(--tessera-fg-success)]",
  off: "border-red-500/30 bg-red-500/15 text-[var(--tessera-fg-danger)]",
};

// Tone keys are locale-stable; display labels come from i18n / the backend.
type Status = "all" | "good" | "off";
type TypeF = "all" | "reg" | "prod";
// "Gerer le catalogue" -> the signal catalogue; "Sources & memoire" -> the memory page.
const CATALOG_HREF = "/configurer/signal-catalog" as const;
const MEMORY_HREF = "/configurer/sources-memoire" as const;
type NavHref = typeof CATALOG_HREF | typeof MEMORY_HREF;

export function AgentConnaissances() {
  return (
    <Suspense fallback={<ConnaissancesSkeleton />}>
      <AgentConnaissancesInner />
    </Suspense>
  );
}

function AgentConnaissancesInner() {
  const t = useTranslations("agentConnaissances");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["agent-connaissances", locale],
    queryFn: ({ signal }) => fetchAgentConnaissances(locale, signal),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
  // Filters + open source are restored from / synced to the URL (shareable view).
  const [search, setSearch] = useState(() => sp.get("q") ?? "");
  const [status, setStatus] = useState<Status>(() => (sp.get("status") as Status) ?? "all");
  const [typeF, setTypeF] = useState<TypeF>(() => (sp.get("type") as TypeF) ?? "all");
  const [period, setPeriod] = useState(() => sp.get("period") ?? "30");
  const [langSel, setLangSel] = useState<string[]>(
    () => sp.get("l")?.split(",").filter(Boolean) ?? [],
  );
  const [minCov, setMinCov] = useState(() => Number(sp.get("cov")) || 0);
  const [groundedOnly, setGroundedOnly] = useState(() => sp.get("grounded") === "1");
  const [selected, setSelected] = useState<string | null>(() => sp.get("sel"));
  const [mutError, setMutError] = useState<string | null>(null);
  const mut = useMutation({
    mutationFn: (body: { key: string; attached?: boolean; active?: boolean }) =>
      mutateConnaissancesSource({ ...body, lang: locale }),
    onSuccess: (fresh) => {
      setMutError(null);
      qc.setQueryData(["agent-connaissances", locale], fresh);
      // The response was built in the same request as the S1 append, which is
      // spooled and drained asynchronously — its own journal fold can miss the
      // just-written act. One refetch lands after the drain; the poll backstops.
      qc.invalidateQueries({ queryKey: ["agent-connaissances", locale] });
    },
    onError: () => setMutError(t("mutationError")),
  });

  // biome-ignore lint/correctness/useExhaustiveDependencies: router/pathname are stable
  useEffect(() => {
    const query: Record<string, string> = {};
    if (search.trim()) query.q = search.trim();
    if (status !== "all") query.status = status;
    if (typeF !== "all") query.type = typeF;
    if (period !== "30") query.period = period;
    if (langSel.length) query.l = langSel.join(",");
    if (minCov) query.cov = String(minCov);
    if (groundedOnly) query.grounded = "1";
    if (selected) query.sel = selected;
    router.replace({ pathname, query }, { scroll: false });
  }, [search, status, typeF, period, langSel, minCov, groundedOnly, selected]);

  if (!data) return <ConnaissancesSkeleton />;
  if (!data.available) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        {t("unavailable")}
      </div>
    );
  }

  const a = data.actions;
  const details = data.details ?? [];
  const detail = details.find((d) => d.key === selected);
  const periodDays = Number(period);
  const q = search.trim().toLowerCase();
  const allRows = data.table?.rows ?? [];
  const allLangs = [...new Set(allRows.flatMap((r) => r.langs ?? []))].sort();
  const advCount = langSel.length + (minCov > 0 ? 1 : 0) + (groundedOnly ? 1 : 0);
  const inlineActive =
    status !== "all" || typeF !== "all" || period !== "30" || search.trim() !== "";
  const canReset = advCount > 0 || inlineActive;
  const resetAll = () => {
    setSearch("");
    setStatus("all");
    setTypeF("all");
    setPeriod("30");
    setLangSel([]);
    setMinCov(0);
    setGroundedOnly(false);
  };
  const rows = allRows.filter(
    (r) =>
      (status === "all" || r.status_tone === status) &&
      (typeF === "all" || r.type_tone === typeF) &&
      (r.fresh_days ?? 0) <= periodDays &&
      (langSel.length === 0 || (r.langs ?? []).some((l) => langSel.includes(l))) &&
      (r.coverage ?? 0) >= minCov &&
      (!groundedOnly || (r.grounded ?? 0) > 0) &&
      (q === "" ||
        r.name.toLowerCase().includes(q) ||
        r.type.toLowerCase().includes(q) ||
        r.path.toLowerCase().includes(q)),
  );

  const periodLabels: Record<string, string> = {
    "30": t("period30"),
    "7": t("period7"),
    "0": t("periodToday"),
    "99999": t("periodAll"),
  };
  const statusLabel =
    status === "good" ? t("statusActive") : status === "off" ? t("statusOff") : "";
  const typeLabel = typeF === "reg" ? t("typeReg") : typeF === "prod" ? t("typeProd") : "";
  const chips: { key: string; label: string; onRemove: () => void }[] = [];
  if (search.trim())
    chips.push({
      key: "q",
      label: `${t("searchPrefix")}: "${search.trim()}"`,
      onRemove: () => setSearch(""),
    });
  if (status !== "all")
    chips.push({
      key: "st",
      label: `${t("filterStatut")}: ${statusLabel}`,
      onRemove: () => setStatus("all"),
    });
  if (typeF !== "all")
    chips.push({
      key: "ty",
      label: `${t("filterType")}: ${typeLabel}`,
      onRemove: () => setTypeF("all"),
    });
  if (period !== "30")
    chips.push({
      key: "pe",
      label: `${t("filterPeriode")}: ${periodLabels[period] ?? period}`,
      onRemove: () => setPeriod("30"),
    });
  for (const l of langSel)
    chips.push({
      key: `lang-${l}`,
      label: `${t("langLabel")}: ${l.toUpperCase()}`,
      onRemove: () => setLangSel(langSel.filter((x) => x !== l)),
    });
  if (minCov > 0)
    chips.push({
      key: "cov",
      label: `${t("volumeMin")}: ${t("coverageGte", { n: minCov })}`,
      onRemove: () => setMinCov(0),
    });
  if (groundedOnly)
    chips.push({ key: "gr", label: t("grounded"), onRemove: () => setGroundedOnly(false) });

  return (
    <div className="relative flex flex-col gap-2.5 pb-2 text-[var(--tessera-text)]">
      <AgentCrossLinks page="connaissances" />
      <div className="flex flex-wrap items-center justify-end gap-2">
        <GhostLink href={CATALOG_HREF} label={a?.manage ?? ""} />
        <GhostLink href={MEMORY_HREF} label={a?.memory ?? ""} />
        <AttachMenu
          label={a?.attach ?? ""}
          items={data.attachable ?? []}
          pending={mut.isPending}
          onAttach={(key) => mut.mutate({ key, attached: true })}
        />
      </div>

      {mutError ? (
        <div
          role="alert"
          className="flex items-center justify-between gap-2 rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-[0.74rem] text-[var(--tessera-fg-danger)]"
        >
          <span>{mutError}</span>
          <button
            type="button"
            aria-label={tCommon("close")}
            onClick={() => setMutError(null)}
            className="flex h-5 w-5 items-center justify-center rounded text-[var(--tessera-fg-danger)]/80 hover:text-[var(--tessera-text-strong)]"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-5">
        {(data.kpis ?? []).map((k, i) => (
          <Kpi key={k.key} kpi={k} Icon={KPI_ICONS[i % KPI_ICONS.length] ?? Link2} />
        ))}
      </div>

      <div className="flex min-w-0 flex-col gap-2.5">
        <Filters
          data={data}
          search={search}
          setSearch={setSearch}
          status={status}
          setStatus={setStatus}
          typeF={typeF}
          setTypeF={setTypeF}
          period={period}
          setPeriod={setPeriod}
          allLangs={allLangs}
          langSel={langSel}
          setLangSel={setLangSel}
          minCov={minCov}
          setMinCov={setMinCov}
          groundedOnly={groundedOnly}
          setGroundedOnly={setGroundedOnly}
          advCount={advCount}
          canReset={canReset}
          onReset={resetAll}
        />
        {chips.length > 0 ? <ActiveFilterChips chips={chips} onClear={resetAll} /> : null}
        <SourcesTable data={data} rows={rows} selected={selected} onSelect={setSelected} />
      </div>

      {detail ? (
        <DetailDrawer
          key={detail.key}
          detail={detail}
          pending={mut.isPending}
          onClose={() => setSelected(null)}
          onDetach={(key) => mut.mutate({ key, attached: false })}
          onToggle={(key, active) => mut.mutate({ key, active })}
        />
      ) : null}
    </div>
  );
}

function GhostLink({ href, label }: { href: NavHref; label: string }) {
  return (
    <Link
      href={href}
      className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
    >
      {label}
    </Link>
  );
}

function AttachMenu({
  label,
  items,
  pending,
  onAttach,
}: {
  label: string;
  items: { key: string; name: string; type: string }[];
  pending: boolean;
  onAttach: (key: string) => void;
}) {
  const t = useTranslations("agentConnaissances");
  const [open, setOpen] = useState(false);
  const ref = useDismiss(
    open,
    useCallback(() => setOpen(false), []),
  );
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        disabled={pending}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex h-9 items-center gap-2 rounded-md border border-[#d98b1f] bg-[#e0a23a] px-3 text-xs font-medium text-[#1b1402] hover:bg-[#eab44e] disabled:opacity-60"
      >
        <Plus className="h-4 w-4" /> {label}
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 w-72 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-1 shadow-lg"
        >
          {items.length === 0 ? (
            <p className="px-2 py-2 text-[0.72rem] text-[var(--tessera-text-muted)]">
              {t("allAttached")}
            </p>
          ) : (
            items.map((it) => (
              <button
                key={it.key}
                type="button"
                role="menuitem"
                disabled={pending}
                onClick={() => {
                  onAttach(it.key);
                  setOpen(false);
                }}
                className="flex w-full items-center justify-between gap-2 rounded px-2 py-1.5 text-left text-[0.72rem] text-[var(--tessera-text)] hover:bg-[var(--tessera-bg)] disabled:opacity-60"
              >
                <Truncate full={it.name}>{it.name}</Truncate>
                <span className="shrink-0 text-[0.62rem] text-[var(--tessera-text-muted)]">
                  {it.type}
                </span>
              </button>
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}

function ActiveFilterChips({
  chips,
  onClear,
}: {
  chips: { key: string; label: string; onRemove: () => void }[];
  onClear: () => void;
}) {
  const t = useTranslations("agentConnaissances");
  return (
    <div className="flex flex-wrap items-center gap-1.5" aria-live="polite">
      {chips.map((c) => (
        <span
          key={c.key}
          className="flex items-center gap-1 rounded-full border border-[var(--tessera-border)] bg-[var(--tessera-surface)] py-1 pl-2.5 pr-1 text-[0.66rem] text-[var(--tessera-text)]"
        >
          {c.label}
          <button
            type="button"
            aria-label={t("removeFilter", { label: c.label })}
            onClick={c.onRemove}
            className="flex h-4 w-4 items-center justify-center rounded-full text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-bg)] hover:text-[var(--tessera-text)]"
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
      <button
        type="button"
        onClick={onClear}
        className="ml-1 text-[0.66rem] font-medium text-[var(--tessera-fg-accent)] hover:text-[var(--tessera-text-strong)]"
      >
        {t("clearAll")}
      </button>
    </div>
  );
}

const KPI_SK = ["a", "b", "c", "d", "e"];
const ROW_SK = ["r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8"];

function ConnaissancesSkeleton() {
  return (
    <div className="flex flex-col gap-3 pb-2">
      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-5">
        {KPI_SK.map((id) => (
          <Skeleton key={id} className="h-[112px] w-full rounded-lg" />
        ))}
      </div>
      <Skeleton className="h-14 w-full rounded-lg" />
      <div className="flex flex-col gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
        {ROW_SK.map((id) => (
          <Skeleton key={id} className="h-10 w-full" />
        ))}
      </div>
    </div>
  );
}

function Kpi({ kpi, Icon }: { kpi: NonNullable<Data["kpis"]>[number]; Icon: LucideIcon }) {
  return (
    <div className="flex h-[112px] flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="flex items-center gap-2">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-[#e0a23a]/30 bg-[#e0a23a]/10 text-[var(--tessera-fg-warning)]">
          <Icon className="h-3.5 w-3.5" />
        </span>
        <Truncate full={kpi.label} className="text-[0.66rem] text-[var(--tessera-text-muted)]">
          {kpi.label}
        </Truncate>
        <CardInfo ns="agentConnaissances" k={kpi.key} title={kpi.label} />
      </div>
      <p className="mt-1.5 text-[1.5rem] font-semibold leading-none tabular-nums text-[var(--tessera-text-strong)]">
        {kpi.value}
      </p>
      <div className="mt-auto pt-1">
        <MetricSparkline values={kpi.series} tone={KPI_TONE[kpi.key] ?? "info"} height={30} />
      </div>
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
          className="absolute right-0 z-20 mt-1 w-48 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-1 shadow-lg"
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
                <span className="text-[var(--tessera-fg-teal)]">&bull;</span>
              ) : null}
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
  status,
  setStatus,
  typeF,
  setTypeF,
  period,
  setPeriod,
  allLangs,
  langSel,
  setLangSel,
  minCov,
  setMinCov,
  groundedOnly,
  setGroundedOnly,
  advCount,
  canReset,
  onReset,
}: {
  data: Data;
  search: string;
  setSearch: (v: string) => void;
  status: Status;
  setStatus: (v: Status) => void;
  typeF: TypeF;
  setTypeF: (v: TypeF) => void;
  period: string;
  setPeriod: (v: string) => void;
  allLangs: string[];
  langSel: string[];
  setLangSel: (v: string[]) => void;
  minCov: number;
  setMinCov: (v: number) => void;
  groundedOnly: boolean;
  setGroundedOnly: (v: boolean) => void;
  advCount: number;
  canReset: boolean;
  onReset: () => void;
}) {
  const t = useTranslations("agentConnaissances");
  const tCommon = useTranslations("common");
  const f = data.filters;
  if (!f) return null;
  const statusOpts = [
    { value: "all", label: tCommon("all") },
    { value: "good", label: t("statusActive") },
    { value: "off", label: t("statusOff") },
  ];
  const typeOpts = [
    { value: "all", label: tCommon("all") },
    { value: "reg", label: t("typeReg") },
    { value: "prod", label: t("typeProd") },
  ];
  const periodOpts = [
    { value: "30", label: t("period30") },
    { value: "7", label: t("period7") },
    { value: "0", label: t("periodToday") },
    { value: "99999", label: t("periodAll") },
  ];
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5">
      <div className="flex h-9 min-w-[220px] flex-1 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5">
        <Search className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={f.search}
          aria-label={f.search}
          className="min-w-0 flex-1 bg-transparent text-[0.74rem] text-[var(--tessera-text)] placeholder:text-[var(--tessera-text-muted)] focus:outline-none"
        />
      </div>
      <FilterDropdown
        label={t("filterStatut")}
        value={status}
        options={statusOpts}
        onSelect={(v) => setStatus(v as Status)}
      />
      <FilterDropdown
        label={t("filterType")}
        value={typeF}
        options={typeOpts}
        onSelect={(v) => setTypeF(v as TypeF)}
      />
      <FilterDropdown
        label={t("filterPeriode")}
        value={period}
        options={periodOpts}
        onSelect={setPeriod}
      />
      <AdvancedFilters
        label={f.more}
        allLangs={allLangs}
        langSel={langSel}
        setLangSel={setLangSel}
        minCov={minCov}
        setMinCov={setMinCov}
        groundedOnly={groundedOnly}
        setGroundedOnly={setGroundedOnly}
        activeCount={advCount}
        canReset={canReset}
        onReset={onReset}
      />
    </div>
  );
}

const COVERAGE_STEPS = [0, 25, 50, 75] as const;

function AdvancedFilters({
  label,
  allLangs,
  langSel,
  setLangSel,
  minCov,
  setMinCov,
  groundedOnly,
  setGroundedOnly,
  activeCount,
  canReset,
  onReset,
}: {
  label: string;
  allLangs: string[];
  langSel: string[];
  setLangSel: (v: string[]) => void;
  minCov: number;
  setMinCov: (v: number) => void;
  groundedOnly: boolean;
  setGroundedOnly: (v: boolean) => void;
  activeCount: number;
  canReset: boolean;
  onReset: () => void;
}) {
  const t = useTranslations("agentConnaissances");
  const [open, setOpen] = useState(false);
  const ref = useDismiss(
    open,
    useCallback(() => setOpen(false), []),
  );
  const toggleLang = (l: string) =>
    setLangSel(langSel.includes(l) ? langSel.filter((x) => x !== l) : [...langSel, l]);
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "flex h-9 items-center gap-1.5 rounded-md border px-2.5 text-[0.74rem]",
          activeCount > 0
            ? "border-[#5fd0c6]/50 bg-[#5fd0c6]/10 text-[var(--tessera-text)]"
            : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
        )}
      >
        <SlidersHorizontal className="h-3.5 w-3.5" /> {label}
        {activeCount > 0 ? (
          <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-[#5fd0c6] px-1 text-[0.6rem] font-semibold text-[#04201d]">
            {activeCount}
          </span>
        ) : null}
      </button>
      {open ? (
        <div className="absolute right-0 z-20 mt-1 w-64 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3 shadow-lg">
          {allLangs.length > 0 ? (
            <div className="mb-3">
              <p className="mb-1.5 text-[0.64rem] font-medium uppercase tracking-wide text-[var(--tessera-text-muted)]">
                {t("langLabel")}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {allLangs.map((l) => {
                  const on = langSel.includes(l);
                  return (
                    <button
                      key={l}
                      type="button"
                      aria-pressed={on}
                      onClick={() => toggleLang(l)}
                      className={cn(
                        "rounded-md border px-2 py-1 text-[0.66rem] font-medium uppercase",
                        on
                          ? "border-[#5fd0c6]/50 bg-[#5fd0c6]/15 text-[var(--tessera-text)]"
                          : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
                      )}
                    >
                      {l}
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}

          <div className="mb-3">
            <p className="mb-1.5 text-[0.64rem] font-medium uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {t("volumeMin")}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {COVERAGE_STEPS.map((c) => {
                const on = minCov === c;
                return (
                  <button
                    key={c}
                    type="button"
                    aria-pressed={on}
                    onClick={() => setMinCov(c)}
                    className={cn(
                      "rounded-md border px-2 py-1 text-[0.66rem] font-medium tabular-nums",
                      on
                        ? "border-[#5fd0c6]/50 bg-[#5fd0c6]/15 text-[var(--tessera-text)]"
                        : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
                    )}
                  >
                    {c === 0 ? t("coverageAll") : t("coverageGte", { n: c })}
                  </button>
                );
              })}
            </div>
          </div>

          <button
            type="button"
            aria-pressed={groundedOnly}
            onClick={() => setGroundedOnly(!groundedOnly)}
            className="flex w-full items-center justify-between gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2 text-[0.7rem] text-[var(--tessera-text)]"
          >
            <span>{t("grounded")}</span>
            <span
              className={cn(
                "flex h-4 w-8 items-center rounded-full px-0.5 transition-colors",
                groundedOnly ? "justify-end bg-emerald-500" : "justify-start bg-slate-600",
              )}
            >
              <span className="h-3 w-3 rounded-full bg-white" />
            </span>
          </button>

          {canReset ? (
            <button
              type="button"
              onClick={onReset}
              className="mt-3 w-full text-center text-[0.66rem] font-medium text-[var(--tessera-fg-accent)] hover:text-[var(--tessera-text-strong)]"
            >
              {t("reset")}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

// Fixed column widths (Source, Type, Statut, Couverture, Fraicheur, Taux de citation).
const COL_WIDTHS = ["32%", "18%", "12%", "14%", "12%", "12%"] as const;
type SortDir = "asc" | "desc";

// Sort value per column INDEX (locale-proof; labels are localized). Columns:
// 0 Source, 1 Type, 2 Statut, 3 Volume, 4 Fraicheur, 5 Taux de citation.
// null always sorts last regardless of direction.
function sortValue(col: number, r: RowT): number | string | null {
  switch (col) {
    case 3:
      return r.coverage;
    case 4:
      return r.fresh_days ?? null;
    case 5: {
      const n = Number.parseFloat(r.citation);
      return Number.isNaN(n) ? null : n;
    }
    case 1:
      return (r.type_tone ?? r.type).toLowerCase();
    case 2:
      return r.status_tone.toLowerCase();
    default:
      return r.name.toLowerCase();
  }
}

function compareRows(a: RowT, b: RowT, col: number, dir: SortDir): number {
  const av = sortValue(col, a);
  const bv = sortValue(col, b);
  if (av === null && bv === null) return 0;
  if (av === null) return 1; // nulls last
  if (bv === null) return -1;
  const base =
    typeof av === "number" && typeof bv === "number"
      ? av - bv
      : String(av).localeCompare(String(bv));
  return dir === "asc" ? base : -base;
}

function SourcesTable({
  data,
  rows,
  selected,
  onSelect,
}: {
  data: Data;
  rows: RowT[];
  selected: string | null;
  onSelect: (key: string) => void;
}) {
  const t = useTranslations("agentConnaissances");
  const tbl = data.table;
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const [sortCol, setSortCol] = useState<number | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const sortedRows = useMemo(() => {
    if (sortCol === null) return rows;
    return [...rows].sort((a, b) => compareRows(a, b, sortCol, sortDir));
  }, [rows, sortCol, sortDir]);
  const totalRows = sortedRows.length;
  const totalPages = Math.max(1, Math.ceil(totalRows / perPage));
  // Reset to the first page when the filtered set, page size, or sort changes.
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset on filter/sort change, not row identity
  useEffect(() => setPage(1), [totalRows, perPage, sortCol, sortDir]);
  const safePage = Math.min(page, totalPages);
  const startIdx = (safePage - 1) * perPage;
  const pageRows = sortedRows.slice(startIdx, startIdx + perPage);
  const onSort = (col: number) => {
    if (col === sortCol) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(col);
      setSortDir("asc");
    }
  };
  if (!tbl) return null;
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] table-fixed border-collapse text-left">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.64rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {tbl.columns.map((c, i) => (
                <th
                  key={c}
                  style={{ width: COL_WIDTHS[i] }}
                  aria-sort={
                    sortCol === i ? (sortDir === "asc" ? "ascending" : "descending") : "none"
                  }
                  className="px-3 py-2 font-medium"
                >
                  <button
                    type="button"
                    onClick={() => onSort(i)}
                    className={cn(
                      "-mx-1 flex items-center gap-1 rounded px-1 py-0.5 uppercase hover:text-[var(--tessera-text)]",
                      i === 0 ? "" : "whitespace-nowrap",
                      sortCol === i ? "text-[var(--tessera-text)]" : "",
                    )}
                  >
                    {c}
                    {sortCol === i ? (
                      sortDir === "asc" ? (
                        <ArrowUp className="h-3 w-3" />
                      ) : (
                        <ArrowDown className="h-3 w-3" />
                      )
                    ) : (
                      <ChevronsUpDown className="h-3 w-3 opacity-40" />
                    )}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((r) => (
              <tr
                key={r.name}
                // biome-ignore lint/a11y/useSemanticElements: a data row opens the detail drawer and stays keyboard reachable
                role="button"
                tabIndex={0}
                aria-label={r.name}
                onClick={() => r.key && onSelect(r.key)}
                onKeyDown={(e) => {
                  if ((e.key === "Enter" || e.key === " ") && r.key) {
                    e.preventDefault();
                    onSelect(r.key);
                  }
                }}
                className={cn(
                  "cursor-pointer border-b border-[var(--tessera-border)]/60 outline-none last:border-0 focus-visible:bg-[var(--tessera-bg)]/60 focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-[#5fd0c6]",
                  r.key && r.key === selected
                    ? "bg-[var(--tessera-bg)]/70"
                    : "hover:bg-[var(--tessera-bg)]/40",
                )}
              >
                <td className="px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]">
                      <FileGlyph />
                    </span>
                    <span className="min-w-0">
                      <Truncate
                        full={r.name}
                        className="text-[0.76rem] font-medium text-[var(--tessera-text)]"
                      >
                        {r.name}
                      </Truncate>
                      <Truncate
                        full={r.path}
                        className="text-[0.62rem] text-[var(--tessera-text-muted)]"
                      >
                        {r.path}
                      </Truncate>
                    </span>
                  </div>
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 text-[0.72rem] text-[var(--tessera-text-muted)]">
                  {r.type}
                </td>
                <td className="px-3 py-2.5">
                  <span
                    className={cn(
                      "rounded-full border px-2 py-0.5 text-[0.6rem] font-medium",
                      STATUS_TONE[r.status_tone] ?? STATUS_TONE.good,
                    )}
                  >
                    {r.status}
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  {r.coverage === null ? (
                    <span className="text-[0.72rem] text-[var(--tessera-text-muted)]">-</span>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span className="w-9 shrink-0 text-[0.72rem] tabular-nums text-[var(--tessera-text)]">
                        {r.coverage}%
                      </span>
                      <span className="hidden h-[4px] w-16 overflow-hidden rounded-full bg-[var(--tessera-border)] sm:block">
                        <span
                          className="block h-full rounded-full bg-[#5fd0c6]"
                          style={{ width: `${r.coverage}%` }}
                        />
                      </span>
                    </div>
                  )}
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 text-[0.72rem] text-[var(--tessera-text-muted)]">
                  {r.freshness}
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 text-[0.72rem] tabular-nums text-[var(--tessera-text)]">
                  {r.citation}
                </td>
              </tr>
            ))}
            {totalRows === 0 ? (
              <tr>
                <td
                  colSpan={tbl.columns.length}
                  className="px-3 py-6 text-center text-[0.72rem] text-[var(--tessera-text-muted)]"
                >
                  {t("noResults")}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <Pagination
        page={safePage}
        totalPages={totalPages}
        start={totalRows === 0 ? 0 : startIdx + 1}
        end={Math.min(startIdx + perPage, totalRows)}
        total={totalRows}
        perPage={perPage}
        onPage={setPage}
        onPerPage={setPerPage}
      />
    </section>
  );
}

const ROWS_PER_PAGE_OPTS = [10, 20, 50] as const;
const MAX_PAGE_BUTTONS = 5;

function pageWindow(page: number, totalPages: number): number[] {
  // A compact, centered window of page numbers (no ellipsis logic needed at this scale).
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
  const t = useTranslations("agentConnaissances");
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--tessera-border)] px-3 py-2 text-[0.7rem] text-[var(--tessera-text-muted)]">
      <span className="tabular-nums" aria-live="polite">
        {t("paginationSummary", { start, end, total })}
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
        <span>{t("rowsPerPage")}</span>
        <select
          value={perPage}
          onChange={(e) => onPerPage(Number(e.target.value))}
          className="h-7 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 text-[0.72rem] text-[var(--tessera-text)] focus:outline-none"
        >
          {ROWS_PER_PAGE_OPTS.map((n) => (
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
  const t = useTranslations("agentConnaissances");
  const Icon = dir === "prev" ? ChevronLeft : ChevronRight;
  return (
    <button
      type="button"
      disabled={disabled}
      aria-label={dir === "prev" ? t("prevPage") : t("nextPage")}
      onClick={onClick}
      className="flex h-7 w-7 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)] disabled:opacity-40"
    >
      <Icon className="h-3.5 w-3.5" />
    </button>
  );
}

function FileGlyph() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-3.5 w-3.5"
      fill="none"
      stroke="currentColor"
      aria-hidden="true"
    >
      <path
        d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M14 2v6h6" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}

type AnswerT = DetailT["answers"][number];
// Longer grounded answers collapse to a few lines with a Voir plus toggle.
const ANSWER_CLAMP_CHARS = 180;

function AnswerItem({ ans }: { ans: AnswerT }) {
  const t = useTranslations("agentConnaissances");
  const [open, setOpen] = useState(false);
  const answer = ans.answer ?? "";
  const clampable = answer.length > ANSWER_CLAMP_CHARS;
  return (
    <li className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)]/40 p-2.5">
      <div className="flex items-start gap-2">
        <Quote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--tessera-fg-teal)]" />
        <span className="min-w-0 flex-1 text-[0.72rem] font-medium text-[var(--tessera-text)]">
          {ans.text}
        </span>
        {ans.time ? (
          <span className="shrink-0 text-[0.6rem] text-[var(--tessera-text-muted)]">
            {ans.time}
          </span>
        ) : null}
      </div>
      {answer ? (
        <>
          <p
            title={answer}
            className={cn(
              "mt-1 text-[0.68rem] leading-relaxed text-[var(--tessera-text-muted)]",
              clampable && !open && "line-clamp-2",
            )}
          >
            {answer}
          </p>
          {clampable ? (
            <button
              type="button"
              onClick={() => setOpen((o) => !o)}
              className="mt-1 text-[0.64rem] font-medium text-[var(--tessera-fg-teal)] hover:text-[var(--tessera-fg-teal)]"
            >
              {open ? t("showLess") : t("showMore")}
            </button>
          ) : null}
        </>
      ) : null}
    </li>
  );
}

function DetailDrawer({
  detail,
  pending,
  onClose,
  onDetach,
  onToggle,
}: {
  detail: DetailT;
  pending: boolean;
  onClose: () => void;
  onDetach: (key: string) => void;
  onToggle: (key: string, active: boolean) => void;
}) {
  // Anchor the overlay to the <main> content area so it spans its full height
  // (below the header, right of the sidebar) regardless of how tall the page is.
  const [rect, setRect] = useState<{
    top: number;
    left: number;
    width: number;
    height: number;
  } | null>(null);
  useEffect(() => {
    const measure = () => {
      const m = document.querySelector("main");
      if (!m) return;
      const r = m.getBoundingClientRect();
      // Start below the agent tab strip so page-level navigation stays usable.
      const tabs = document.querySelector("[data-agent-tabs]");
      const top = tabs ? tabs.getBoundingClientRect().bottom : r.top;
      setRect({ top, left: r.left, width: r.width, height: r.bottom - top });
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div
      className="fixed z-50 flex justify-end overflow-hidden bg-[#020817]/70 p-2.5 backdrop-blur-[2px]"
      style={rect ?? { inset: 0 }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <DetailPanel
        detail={detail}
        pending={pending}
        onClose={onClose}
        onDetach={onDetach}
        onToggle={onToggle}
      />
    </div>
  );
}

function DetailPanel({
  detail,
  pending,
  onClose,
  onDetach,
  onToggle,
}: {
  detail: DetailT;
  pending: boolean;
  onClose: () => void;
  onDetach: (key: string) => void;
  onToggle: (key: string, active: boolean) => void;
}) {
  const tCommon = useTranslations("common");
  const t = useTranslations("agentConnaissances");
  const [tab, setTab] = useState(detail.tabs[0] ?? "Usage");
  const closeRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  useEffect(() => closeRef.current?.focus(), []);
  // Keep Tab focus inside the drawer (the native <dialog open> is not modal).
  const onTrapKey = (event: React.KeyboardEvent<HTMLDialogElement>) => {
    if (event.key !== "Tab" || !dialogRef.current) return;
    const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
      'button, a[href], select, input, [tabindex]:not([tabindex="-1"])',
    );
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (!first || !last) return;
    const active = document.activeElement;
    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  };
  const d = detail;
  const key = d.key;
  return (
    <dialog
      open
      ref={dialogRef}
      aria-modal="true"
      aria-label={d.name}
      onKeyDown={onTrapKey}
      className="static m-0 flex h-full w-full max-w-[460px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-0 text-[var(--tessera-text)] shadow-[0_12px_48px_rgba(0,0,0,0.5)]"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-[var(--tessera-border)] px-3.5 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]">
            <FileGlyph />
          </span>
          <Truncate
            full={d.name}
            className="text-[0.85rem] font-semibold text-[var(--tessera-text)]"
          >
            {d.name}
          </Truncate>
          <CardInfo ns="agentConnaissances" k="detail" title={d.name} />
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span
            className={cn(
              "rounded-full border px-2 py-0.5 text-[0.6rem] font-medium",
              STATUS_TONE[d.status_tone] ?? STATUS_TONE.good,
            )}
          >
            {d.status}
          </span>
          <button
            type="button"
            ref={closeRef}
            aria-label={tCommon("close")}
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--tessera-text-muted)] outline-none hover:bg-[var(--tessera-bg)] hover:text-[var(--tessera-text)] focus-visible:ring-1 focus-visible:ring-[#5fd0c6]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      <nav className="flex shrink-0 items-center gap-4 border-b border-[var(--tessera-border)] px-3.5">
        {d.tabs.map((tb) => {
          const on = tb === tab;
          return (
            <button
              key={tb}
              type="button"
              onClick={() => setTab(tb)}
              className={cn(
                "-mb-px border-b-2 py-2.5 text-[0.72rem] transition-colors",
                on
                  ? "border-[#5fd0c6] font-medium text-[var(--tessera-text)]"
                  : "border-transparent text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
              )}
            >
              {tb}
            </button>
          );
        })}
      </nav>

      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-3.5">
        {tab === d.tabs[0] ? (
          <>
            <div>
              <h3 className="mb-1 text-[0.72rem] font-semibold text-[var(--tessera-text)]">
                {d.summary_title}
              </h3>
              <p className="text-[0.72rem] leading-relaxed text-[var(--tessera-text-muted)]">
                {d.summary}
              </p>
            </div>
            <div>
              <h3 className="mb-2 text-[0.72rem] font-semibold text-[var(--tessera-text)]">
                {d.usage_title}
              </h3>
              <ul className="flex flex-col gap-1.5 text-[0.72rem]">
                {d.usage.map((u) => (
                  <li key={u.label} className="flex items-center justify-between gap-2">
                    <span className="text-[var(--tessera-text-muted)]">{u.label}</span>
                    <span className="font-medium tabular-nums text-[var(--tessera-text)]">
                      {u.value}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </>
        ) : null}

        {tab === d.tabs[1] ? (
          <div>
            <h3 className="mb-2 text-[0.72rem] font-semibold text-[var(--tessera-text)]">
              {d.answers_title}
            </h3>
            {d.answers.length === 0 ? (
              <p className="text-[0.72rem] text-[var(--tessera-text-muted)]">
                {t("noGroundedAnswers")}
              </p>
            ) : (
              <ul className="flex flex-col gap-2.5">
                {d.answers.map((ans) => (
                  <AnswerItem key={ans.text} ans={ans} />
                ))}
              </ul>
            )}
          </div>
        ) : null}

        {tab === d.tabs[2] ? (
          <div>
            <h3 className="mb-2 text-[0.72rem] font-semibold text-[var(--tessera-text)]">
              {d.params_title ?? t("paramsFallback")}
            </h3>
            <ul className="flex flex-col gap-1.5 text-[0.72rem]">
              {(d.params ?? []).map((p) => (
                <li key={p.label} className="flex items-center justify-between gap-2">
                  <span className="text-[var(--tessera-text-muted)]">{p.label}</span>
                  <span className="font-medium text-[var(--tessera-text)]">{p.value}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {d.attachment ? (
          <div>
            <h3 className="mb-2 text-[0.72rem] font-semibold text-[var(--tessera-text)]">
              {d.attachment.title}
            </h3>
            <ul className="flex flex-col gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2 text-[0.72rem]">
              {d.attachment.rows.map((r) => (
                <li key={r.label} className="flex items-center justify-between gap-2">
                  <span className="text-[var(--tessera-text-muted)]">{r.label}</span>
                  <span className="font-medium text-[var(--tessera-text)]">{r.value}</span>
                </li>
              ))}
            </ul>
            {d.attachment.journal_title ? (
              <div data-testid="source-journal" className="mt-2">
                <h4 className="mb-1 text-[0.68rem] font-semibold text-[var(--tessera-text-muted)]">
                  {d.attachment.journal_title}
                </h4>
                {Array.isArray(d.attachment.journal) ? (
                  d.attachment.journal.length > 0 ? (
                    <ul className="flex flex-col gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2 text-[0.68rem]">
                      {d.attachment.journal.map((ev) => (
                        <li
                          key={`${ev.at}-${ev.action}`}
                          className="flex items-center justify-between gap-2"
                        >
                          <span className="font-medium text-[var(--tessera-text)]">
                            {ev.action}
                          </span>
                          <span className="text-[var(--tessera-text-muted)]">
                            {ev.at} · {ev.by}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-[0.68rem] text-[var(--tessera-text-muted)]">
                      {d.attachment.journal_empty}
                    </p>
                  )
                ) : (
                  <p className="text-[0.68rem] text-[var(--tessera-fg-warning)]">
                    {d.attachment.journal_unavailable}
                  </p>
                )}
              </div>
            ) : null}
          </div>
        ) : null}

        <div>
          <h3 className="mb-2 text-[0.72rem] font-semibold text-[var(--tessera-text)]">
            {d.actions_title}
          </h3>
          <div className="flex items-center justify-between gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2">
            <span className="text-[0.72rem] text-[var(--tessera-text)]">{d.toggle_label}</span>
            <button
              type="button"
              disabled={pending || !key}
              aria-pressed={d.toggle_on}
              onClick={() => key && onToggle(key, !d.toggle_on)}
              className={cn(
                "flex h-4 w-8 items-center rounded-full px-0.5 transition-colors disabled:opacity-60",
                d.toggle_on ? "justify-end bg-emerald-500" : "justify-start bg-slate-600",
              )}
            >
              <span className="h-3 w-3 rounded-full bg-white" />
            </button>
          </div>
          <button
            type="button"
            disabled={pending || !key}
            onClick={() => key && onDetach(key)}
            className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-md border border-red-500/40 bg-red-500/5 px-3 py-2 text-[0.72rem] font-medium text-[var(--tessera-fg-danger)] hover:bg-red-500/10 disabled:opacity-60"
          >
            {d.detach}
          </button>
          <Link
            href={{ pathname: MEMORY_HREF, query: { source: d.key } }}
            className="mt-2.5 flex items-center gap-1 self-start text-[0.68rem] text-[var(--tessera-fg-accent)] hover:text-[var(--tessera-text-strong)]"
          >
            {d.full_sheet}
            <ChevronRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>
    </dialog>
  );
}
