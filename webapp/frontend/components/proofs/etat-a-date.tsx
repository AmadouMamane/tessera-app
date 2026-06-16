"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bookmark,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  Download,
  History,
  RotateCcw,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { fetchEtatADate, saveEtatSnapshot } from "@/lib/api/client";
import type { EtatADate as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

type Row = NonNullable<Data["table"]>["rows"][number];
type SortDir = "asc" | "desc";

const TYPE_TONE: Record<string, string> = {
  violet: "border-[#8b7cf0]/30 bg-[#8b7cf0]/15 text-[#c4b5fd]",
  blue: "border-[#4c8bf5]/30 bg-[#4c8bf5]/15 text-[#93c5fd]",
};
const KIND_DOT: Record<string, string> = {
  info: "bg-sky-400",
  ok: "bg-emerald-400",
  warn: "bg-amber-400",
};
const ROWS_PER_PAGE_OPTS = [10, 25, 50];

/** Close a popover on outside-click / Escape; returns the ref for its root. */
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

/** datetime-local value (browser-local) -> ISO instant, or null when empty. */
function toIso(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

/** ISO instant -> datetime-local value in browser-local time (for the input). */
function toLocalInput(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const off = d.getTimezoneOffset() * 60_000;
  return new Date(d.getTime() - off).toISOString().slice(0, 16);
}

export function EtatADate() {
  const t = useTranslations("etatADate");
  const qc = useQueryClient();
  // null = live; a committed ISO instant once the operator reconstructs at T.
  const [draft, setDraft] = useState("");
  const [asOf, setAsOf] = useState<string | null>(null);
  // Table controls (filters live in the parent; sort/page live in the table).
  const [search, setSearch] = useState("");
  const [typeF, setTypeF] = useState("all");
  const [statusF, setStatusF] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);

  const { data } = useQuery({
    queryKey: ["etat-a-date", asOf],
    queryFn: ({ signal }) => fetchEtatADate(asOf, signal),
    staleTime: 30_000,
  });

  const saveSnapshot = useMutation({
    mutationFn: () => saveEtatSnapshot(asOf),
    onSuccess: (fresh) => qc.setQueryData(["etat-a-date", asOf], fresh),
  });

  function reloadAt(snapAsOf: string | null) {
    setAsOf(snapAsOf);
    setDraft(snapAsOf ? toLocalInput(snapAsOf) : "");
  }

  function downloadReport() {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${data.meta?.ref_code ?? "etat-a-date"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const allRows = data?.table?.rows ?? [];
  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return allRows.filter(
      (r) =>
        (typeF === "all" || r.type_key === typeF) &&
        (statusF === "all" || r.status === statusF) &&
        (q === "" || r.source.toLowerCase().includes(q)),
    );
  }, [allRows, search, typeF, statusF]);

  const detail = selected ? (allRows.find((r) => r.key === selected) ?? null) : null;

  return (
    <div className="relative flex flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      <ControlBar
        t={t}
        draft={draft}
        onDraft={setDraft}
        onReconstruct={() => setAsOf(toIso(draft))}
        refCode={data?.meta?.ref_code ?? "-"}
        agent={data?.meta?.agent ?? "-"}
        contextSource={data?.meta?.context_source ?? "-"}
        onDownload={downloadReport}
        canDownload={Boolean(data?.available)}
        onSave={() => saveSnapshot.mutate()}
        saving={saveSnapshot.isPending}
        saved={saveSnapshot.isSuccess}
      />

      {data === undefined ? (
        <EtatSkeleton />
      ) : !data.available ? (
        <div className="flex min-h-[50vh] items-center justify-center text-sm text-[var(--tessera-text-muted)]">
          {t("unavailable")}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-5">
            {(data.kpis ?? []).map((k) => (
              <KpiTile key={k.key} kpi={k} />
            ))}
          </div>

          <div className="grid gap-2.5 xl:grid-cols-12">
            <SourcesTable
              t={t}
              title={data.table?.title ?? ""}
              allRows={allRows}
              rows={rows}
              search={search}
              onSearch={setSearch}
              typeF={typeF}
              onTypeF={setTypeF}
              statusF={statusF}
              onStatusF={setStatusF}
              selected={selected}
              onSelect={setSelected}
              className="xl:col-span-8"
            />
            <div className="flex flex-col gap-2.5 xl:col-span-4">
              <Integrity data={data} />
              <Timeline data={data} />
              <Policies data={data} />
            </div>
          </div>

          <SummaryCards data={data} />
          <Snapshots data={data} onReload={reloadAt} />
        </>
      )}

      {detail ? <SourceDrawer t={t} row={detail} onClose={() => setSelected(null)} /> : null}
    </div>
  );
}

// ── control bar ──────────────────────────────────────────────────────────────

type T = ReturnType<typeof useTranslations<"etatADate">>;

function ControlBar({
  t,
  draft,
  onDraft,
  onReconstruct,
  refCode,
  agent,
  contextSource,
  onDownload,
  canDownload,
  onSave,
  saving,
  saved,
}: {
  t: T;
  draft: string;
  onDraft: (v: string) => void;
  onReconstruct: () => void;
  refCode: string;
  agent: string;
  contextSource: string;
  onDownload: () => void;
  canDownload: boolean;
  onSave: () => void;
  saving: boolean;
  saved: boolean;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={onSave}
          disabled={!canDownload || saving}
          className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)] disabled:opacity-50"
        >
          <Bookmark className="h-4 w-4" />
          {saving ? t("saving") : saved ? t("saved") : t("saveSnapshot")}
        </button>
        <button
          type="button"
          onClick={onDownload}
          disabled={!canDownload}
          className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)] disabled:opacity-50"
        >
          <Download className="h-4 w-4" /> {t("downloadReport")}
        </button>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <Field label={t("agent")}>
          <span className="flex h-9 items-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-sm">
            {agent}
          </span>
        </Field>
        <Field label={t("dateTime")}>
          <input
            type="datetime-local"
            value={draft}
            onChange={(e) => onDraft(e.target.value)}
            aria-label={t("dateTime")}
            className="h-9 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-sm text-[var(--tessera-text)] outline-none focus:border-[#7c5cf5]"
          />
        </Field>
        <Field label={t("contextSource")}>
          <span className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-sm">
            {contextSource}
            <span className="rounded bg-[var(--tessera-surface)] px-1.5 py-0.5 font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
              {refCode}
            </span>
          </span>
        </Field>
        <button
          type="button"
          onClick={onReconstruct}
          className="flex h-9 items-center gap-2 rounded-md border border-[#7c5cf5] bg-[#6d4aed] px-4 text-xs font-medium text-white hover:bg-[#7c5cf5]"
        >
          <History className="h-4 w-4" /> {t("reconstruct")}
        </button>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[0.62rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
        {label}
      </span>
      {children}
    </div>
  );
}

// ── KPI ────────────────────────────────────────────────────────────────────

function KpiTile({ kpi }: { kpi: NonNullable<Data["kpis"]>[number] }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <p className="truncate text-[0.66rem] text-[var(--tessera-text-muted)]">{kpi.label}</p>
      <p className="text-[1.4rem] font-semibold tabular-nums text-[var(--tessera-text)]">
        {kpi.value}
      </p>
      <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{kpi.hint}</p>
    </div>
  );
}

// ── panels ───────────────────────────────────────────────────────────────────

function Panel({
  title,
  children,
  className,
}: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section
      className={cn(
        "flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3",
        className,
      )}
    >
      <h2 className="mb-2 text-[0.78rem] font-semibold text-[var(--tessera-text)]">{title}</h2>
      {children}
    </section>
  );
}

// ── sources table (filters + sort + pagination + row-click drawer) ────────────

const COLS: { key: keyof Row | "source"; labelKey: string; width: string; align?: "right" }[] = [
  { key: "source", labelKey: "source", width: "34%" },
  { key: "type", labelKey: "type", width: "16%" },
  { key: "langs", labelKey: "langs", width: "12%" },
  { key: "chunks", labelKey: "fragments", width: "14%", align: "right" },
  { key: "updated", labelKey: "updated", width: "12%" },
  { key: "status", labelKey: "status", width: "12%" },
];

function sortValue(row: Row, key: keyof Row | "source"): string | number {
  const v = row[key as keyof Row];
  return typeof v === "number" ? v : String(v ?? "").toLowerCase();
}

function SourcesTable({
  t,
  title,
  allRows,
  rows,
  search,
  onSearch,
  typeF,
  onTypeF,
  statusF,
  onStatusF,
  selected,
  onSelect,
  className,
}: {
  t: T;
  title: string;
  allRows: Row[];
  rows: Row[];
  search: string;
  onSearch: (v: string) => void;
  typeF: string;
  onTypeF: (v: string) => void;
  statusF: string;
  onStatusF: (v: string) => void;
  selected: string | null;
  onSelect: (key: string | null) => void;
  className?: string;
}) {
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const [sortCol, setSortCol] = useState<number | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const sorted = useMemo(() => {
    if (sortCol === null) return rows;
    const key = COLS[sortCol]?.key ?? "source";
    return [...rows].sort((a, b) => {
      const va = sortValue(a, key);
      const vb = sortValue(b, key);
      const cmp =
        typeof va === "number" && typeof vb === "number"
          ? va - vb
          : String(va).localeCompare(String(vb));
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [rows, sortCol, sortDir]);

  const total = sorted.length;
  const totalPages = Math.max(1, Math.ceil(total / perPage));
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset on filter/sort/size change
  useEffect(() => setPage(1), [total, perPage, sortCol, sortDir]);
  const safePage = Math.min(page, totalPages);
  const start = (safePage - 1) * perPage;
  const pageRows = sorted.slice(start, start + perPage);

  // Unique filter options derived from the data (stable keys, localized labels).
  const typeOpts = useMemo(() => {
    const m = new Map<string, string>();
    for (const r of allRows) m.set(r.type_key, r.type);
    return [...m.entries()];
  }, [allRows]);
  const statusOpts = useMemo(() => {
    const m = new Map<string, string>();
    for (const r of allRows) m.set(r.status, r.status_label);
    return [...m.entries()];
  }, [allRows]);

  function toggleSort(i: number) {
    if (i === sortCol) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortCol(i);
      setSortDir("asc");
    }
  }

  return (
    <section
      className={cn(
        "flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]",
        className,
      )}
    >
      <div className="flex flex-wrap items-center gap-2 border-b border-[var(--tessera-border)] p-3">
        <h2 className="mr-auto text-[0.78rem] font-semibold text-[var(--tessera-text)]">{title}</h2>
        <div className="relative">
          <Search className="-translate-y-1/2 pointer-events-none absolute top-1/2 left-2.5 h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
          <input
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            placeholder={t("searchPlaceholder")}
            aria-label={t("searchPlaceholder")}
            className="h-8 w-52 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] pl-8 pr-2 text-[0.72rem] text-[var(--tessera-text)] outline-none focus:border-[#7c5cf5]"
          />
        </div>
        <FilterDropdown
          label={t("filterType")}
          value={typeF}
          allLabel={t("all")}
          options={typeOpts}
          onSelect={onTypeF}
        />
        <FilterDropdown
          label={t("filterStatus")}
          value={statusF}
          allLabel={t("all")}
          options={statusOpts}
          onSelect={onStatusF}
        />
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] table-fixed border-collapse text-left">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {COLS.map((c, i) => (
                <th
                  key={c.labelKey}
                  style={{ width: c.width }}
                  aria-sort={
                    sortCol === i ? (sortDir === "asc" ? "ascending" : "descending") : "none"
                  }
                  className={cn("px-3 py-2", c.align === "right" && "text-right")}
                >
                  <button
                    type="button"
                    onClick={() => toggleSort(i)}
                    className={cn(
                      "inline-flex items-center gap-1 hover:text-[var(--tessera-text)]",
                      sortCol === i && "text-[var(--tessera-text)]",
                      c.align === "right" && "flex-row-reverse",
                    )}
                  >
                    {t(c.labelKey)}
                    {sortCol === i ? (
                      <span className="text-[0.7rem]">{sortDir === "asc" ? "▲" : "▼"}</span>
                    ) : (
                      <ChevronsUpDown className="h-3 w-3 opacity-40" />
                    )}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.length === 0 ? (
              <tr>
                <td
                  colSpan={COLS.length}
                  className="px-3 py-6 text-center text-[0.72rem] text-[var(--tessera-text-muted)]"
                >
                  {t("tableEmpty")}
                </td>
              </tr>
            ) : (
              pageRows.map((r) => (
                <tr
                  key={r.key}
                  // biome-ignore lint/a11y/useSemanticElements: a table row cannot be a <button>; it opens the detail drawer
                  role="button"
                  tabIndex={0}
                  aria-label={r.source}
                  onClick={() => onSelect(r.key)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect(r.key);
                    }
                  }}
                  className={cn(
                    "cursor-pointer border-b border-[var(--tessera-border)]/50 text-[0.72rem] outline-none last:border-0 hover:bg-[var(--tessera-bg)]/50 focus-visible:bg-[var(--tessera-bg)]/60 focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-[#5fd0c6]",
                    selected === r.key && "bg-[var(--tessera-bg)]/60",
                  )}
                >
                  <td className="truncate px-3 py-2 font-medium text-[var(--tessera-text)]">
                    {r.source}
                    <span className="block text-[0.58rem] font-normal text-[var(--tessera-text-muted)]">
                      {r.updated}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={cn(
                        "rounded-full border px-2 py-0.5 text-[0.58rem]",
                        TYPE_TONE[r.type_tone] ??
                          "border-slate-500/30 bg-slate-500/15 text-slate-300",
                      )}
                    >
                      {r.type}
                    </span>
                  </td>
                  <td className="px-3 py-2 uppercase tabular-nums text-[var(--tessera-text-muted)]">
                    {r.langs}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-[var(--tessera-text)]">
                    {r.chunks}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-[var(--tessera-text-muted)]">
                    {r.first_seen}
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={cn(
                        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[0.58rem] font-medium",
                        r.status === "accessible"
                          ? "border-emerald-500/30 bg-emerald-500/15 text-emerald-300"
                          : "border-red-500/30 bg-red-500/15 text-red-300",
                      )}
                    >
                      {r.status_label}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <Pagination
        t={t}
        page={safePage}
        totalPages={totalPages}
        start={total === 0 ? 0 : start + 1}
        end={Math.min(start + perPage, total)}
        total={total}
        perPage={perPage}
        onPage={setPage}
        onPerPage={setPerPage}
      />
    </section>
  );
}

function FilterDropdown({
  label,
  value,
  allLabel,
  options,
  onSelect,
}: {
  label: string;
  value: string;
  allLabel: string;
  options: [string, string][];
  onSelect: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useDismiss(open, () => setOpen(false));
  const current =
    value === "all" ? allLabel : (options.find(([k]) => k === value)?.[1] ?? allLabel);
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex h-8 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[0.72rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
      >
        <span className="text-[var(--tessera-text)]">{label}</span>
        <span>{current}</span>
        <ChevronDown className="h-3 w-3" />
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 min-w-[10rem] rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-1 shadow-lg"
        >
          {[["all", allLabel] as [string, string], ...options].map(([k, lbl]) => (
            <button
              key={k}
              type="button"
              role="menuitem"
              onClick={() => {
                onSelect(k);
                setOpen(false);
              }}
              className={cn(
                "flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-[0.72rem] hover:bg-[var(--tessera-bg)]",
                value === k ? "text-[var(--tessera-text)]" : "text-[var(--tessera-text-muted)]",
              )}
            >
              {lbl}
              {value === k ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function pageWindow(page: number, totalPages: number): number[] {
  const span = Math.min(5, totalPages);
  let first = Math.max(1, page - Math.floor(span / 2));
  first = Math.min(first, Math.max(1, totalPages - span + 1));
  return Array.from({ length: span }, (_, i) => first + i);
}

function Pagination({
  t,
  page,
  totalPages,
  start,
  end,
  total,
  perPage,
  onPage,
  onPerPage,
}: {
  t: T;
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
        {t("paginationSummary", { start, end, total })}
      </span>
      <div className="flex items-center gap-1">
        <button
          type="button"
          disabled={page <= 1}
          aria-label={t("prevPage")}
          onClick={() => onPage(Math.max(1, page - 1))}
          className="flex h-7 w-7 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)] disabled:opacity-40"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </button>
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
        <button
          type="button"
          disabled={page >= totalPages}
          aria-label={t("nextPage")}
          onClick={() => onPage(Math.min(totalPages, page + 1))}
          className="flex h-7 w-7 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)] disabled:opacity-40"
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
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

// ── row-click drawer (anchored to <main>, like Connaissances) ─────────────────

function SourceDrawer({ t, row, onClose }: { t: T; row: Row; onClose: () => void }) {
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
      setRect({ top: r.top, left: r.left, width: r.width, height: r.bottom - r.top });
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

  const fields: [string, string][] = [
    [t("type"), row.type],
    [t("status"), row.status_label],
    [t("langs"), row.langs.toUpperCase()],
    [t("accessibleChunks"), `${row.chunks} / ${row.total_chunks}`],
    [t("firstSeen"), row.first_seen],
    [t("lastSeen"), row.updated],
  ];

  return (
    <div
      className="fixed z-50 flex justify-end overflow-hidden bg-[#020817]/70 p-2.5 backdrop-blur-[2px]"
      style={rect ?? { inset: 0 }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <dialog
        open
        aria-modal
        aria-label={row.source}
        className="relative flex h-full w-full max-w-[440px] flex-col rounded-lg border border-[var(--tessera-border)] border-l bg-[var(--tessera-surface)] p-4 text-[var(--tessera-text)] shadow-2xl"
      >
        <button
          type="button"
          onClick={onClose}
          aria-label={t("close")}
          className="absolute top-3 right-3 rounded-md border border-[var(--tessera-border)] p-1 text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          <X className="h-4 w-4" />
        </button>
        <p className="text-[0.62rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
          {t("detailEyebrow")}
        </p>
        <h3 className="mt-1 pr-8 text-[0.95rem] font-semibold">{row.source}</h3>
        <span
          className={cn(
            "mt-2 inline-flex w-fit items-center gap-1 rounded-full border px-2 py-0.5 text-[0.6rem] font-medium",
            row.status === "accessible"
              ? "border-emerald-500/30 bg-emerald-500/15 text-emerald-300"
              : "border-red-500/30 bg-red-500/15 text-red-300",
          )}
        >
          {row.status_label}
        </span>
        <dl className="mt-4 flex flex-col gap-2.5 text-[0.78rem]">
          {fields.map(([label, value]) => (
            <div
              key={label}
              className="flex items-center justify-between gap-2 border-b border-[var(--tessera-border)]/40 pb-2 last:border-0"
            >
              <dt className="text-[var(--tessera-text-muted)]">{label}</dt>
              <dd className="font-medium tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
      </dialog>
    </div>
  );
}

function Integrity({ data }: { data: Data }) {
  const it = data.integrity;
  if (!it) return null;
  return (
    <section className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="flex flex-col">
          <span className="text-[0.62rem] text-[var(--tessera-text-muted)]">
            Couverture de l'index
          </span>
          <span className="text-[1.3rem] font-semibold tabular-nums">{it.coverage}</span>
        </span>
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[0.6rem] font-medium",
            it.verified
              ? "border-emerald-500/30 bg-emerald-500/15 text-emerald-300"
              : "border-red-500/30 bg-red-500/15 text-red-300",
          )}
        >
          {it.verified ? <ShieldCheck className="h-3.5 w-3.5" /> : null}
          {it.verified_label}
        </span>
      </div>
      <dl className="mt-2 flex flex-col gap-1.5 text-[0.72rem]">
        <div className="flex items-center justify-between gap-2">
          <dt className="text-[var(--tessera-text-muted)]">Derniere synchro avant T</dt>
          <dd className="font-medium">{it.last_sync}</dd>
        </div>
        <div className="flex items-center justify-between gap-2">
          <dt className="text-[var(--tessera-text-muted)]">Journalisation</dt>
          <dd className="font-medium">{it.chain_label}</dd>
        </div>
      </dl>
    </section>
  );
}

function Timeline({ data }: { data: Data }) {
  const tl = data.timeline;
  if (!tl) return null;
  return (
    <Panel title={tl.title}>
      {tl.rows.length === 0 ? (
        <p className="py-1 text-[0.72rem] text-[var(--tessera-text-muted)]">Aucun evenement a T.</p>
      ) : (
        <ul className="flex flex-col gap-2.5">
          {tl.rows.map((r, i) => (
            <li key={`${r.time}-${i}`} className="flex gap-2.5 text-[0.72rem]">
              <span
                className={cn(
                  "mt-1 h-1.5 w-1.5 shrink-0 rounded-full",
                  KIND_DOT[r.kind] ?? "bg-slate-400",
                )}
              />
              <span className="min-w-0">
                <span className="block tabular-nums text-[var(--tessera-text-muted)]">
                  {r.time}
                </span>
                <span className="text-[var(--tessera-text)]">{r.label}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function Policies({ data }: { data: Data }) {
  const p = data.policies;
  if (!p) return null;
  return (
    <Panel title={p.title}>
      <dl className="flex flex-col gap-1.5 text-[0.72rem]">
        {p.rows.map((r) => (
          <div key={r.label} className="flex items-center justify-between gap-2">
            <dt className="text-[var(--tessera-text-muted)]">{r.label}</dt>
            <dd className="font-medium tabular-nums text-[var(--tessera-text)]">{r.value}</dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}

function SummaryCards({ data }: { data: Data }) {
  const s = data.summary;
  if (!s) return null;
  return (
    <Panel title={s.title}>
      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-4">
        {s.cards.map((c) => (
          <div
            key={c.label}
            className="flex flex-col gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5"
          >
            <span className="flex items-center gap-1.5 text-[0.62rem] text-[var(--tessera-text-muted)]">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> {c.label}
            </span>
            <span className="text-[1.1rem] font-semibold tabular-nums text-[var(--tessera-text)]">
              {c.value}
            </span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function Snapshots({ data, onReload }: { data: Data; onReload: (asOf: string | null) => void }) {
  const t = useTranslations("etatADate");
  const s = data.snapshots;
  if (!s) return null;
  return (
    <Panel title={s.title}>
      {s.rows.length === 0 ? (
        <p className="py-1 text-[0.72rem] text-[var(--tessera-text-muted)]">{t("noSnapshots")}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {s.rows.map((r) => (
            <li
              key={r.id}
              className="flex items-center justify-between gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2"
            >
              <span className="min-w-0">
                <span className="flex items-center gap-2 text-[0.74rem] font-medium text-[var(--tessera-text)]">
                  {r.as_of_label}
                  <span className="rounded bg-[var(--tessera-surface)] px-1.5 py-0.5 font-mono text-[0.58rem] text-[var(--tessera-text-muted)]">
                    {r.ref_code}
                  </span>
                </span>
                <span className="block truncate text-[0.62rem] text-[var(--tessera-text-muted)]">
                  {r.summary} - {t("savedAt")} {r.saved_label}
                </span>
              </span>
              <button
                type="button"
                onClick={() => onReload(r.as_of)}
                className="flex shrink-0 items-center gap-1 rounded-md border border-[var(--tessera-border)] px-2 py-1 text-[0.62rem] text-[#b9a6ff] hover:text-white"
              >
                <RotateCcw className="h-3 w-3" /> {t("reload")}
              </button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

// ── skeleton ───────────────────────────────────────────────────────────────

const SKELETON_KPIS = ["a", "b", "c", "d", "e"];

function EtatSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-5">
        {SKELETON_KPIS.map((k) => (
          <Skeleton key={k} className="h-[88px] w-full rounded-lg" />
        ))}
      </div>
      <div className="grid gap-2.5 xl:grid-cols-12">
        <Skeleton className="h-80 rounded-lg xl:col-span-8" />
        <Skeleton className="h-80 rounded-lg xl:col-span-4" />
      </div>
    </div>
  );
}
