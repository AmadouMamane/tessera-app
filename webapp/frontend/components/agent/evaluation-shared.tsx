"use client";

/**
 * Shared primitives for the AGENT / Évaluations sub-tabs (Jeux d'évaluations,
 * Résultats, Dimensions, Comparaisons, Erreurs, Versions & historique, Exports).
 *
 * Every sub-tab table gets the same mandatory "Connaissances treatment"
 * (functional-page-playbook): a filter bar, sortable column headers with
 * `aria-sort`, a client-side pagination footer, keyboard-reachable rows, and a
 * row-click that opens the right-anchored detail drawer. Rather than copy that
 * machinery into each tab, it lives here once as `DataTable` + `EvalDrawer`.
 */

import { ChevronDown, ChevronLeft, ChevronRight, ChevronsUpDown, Search, X } from "lucide-react";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { cn } from "@/lib/cn";

export function pick(locale: string, fr: string, de: string, en: string): string {
  return locale === "de" ? de : locale === "en" ? en : fr;
}

/** Close a popover on outside-click / Escape while it is open. */
export function useDismiss(open: boolean, onClose: () => void) {
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

// ── Shared tone maps ─────────────────────────────────────────────────────────

export const TYPE_TONE: Record<string, string> = {
  sys: "border-violet-500/30 bg-violet-500/15 text-violet-300",
  tpl: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  agt: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
};

export const SEVERITY_PILL: Record<string, string> = {
  crit: "border-[#e0566f]/50 bg-[#e0566f]/15 text-[#ff9bb0]",
  muted: "border-[var(--tessera-border)] bg-black/15 text-[var(--tessera-text-muted)]",
};

export const PASS_TONE: Record<string, string> = {
  good: "text-emerald-300",
  bad: "text-red-300",
  muted: "text-[var(--tessera-text-muted)]",
};

export const PASS_DOT: Record<string, string> = {
  good: "bg-emerald-400",
  bad: "bg-red-400",
  muted: "bg-slate-500",
};

// ── Filter chrome ────────────────────────────────────────────────────────────

/** The bordered container holding a tab's search + filter controls. */
export function FilterBar({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5">
      {children}
    </div>
  );
}

export function SearchInput({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  return (
    <div className="flex h-9 min-w-[200px] flex-1 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5">
      <Search className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className="h-full min-w-0 flex-1 bg-transparent text-[0.74rem] text-[var(--tessera-text)] outline-none placeholder:text-[var(--tessera-text-muted)]"
      />
    </div>
  );
}

export function FilterDropdown({
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
          className="absolute right-0 z-20 mt-1 max-h-72 w-56 overflow-y-auto rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-1 shadow-lg"
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

export function ResetButton({ onClick }: { onClick: () => void }) {
  const locale = useLocale();
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex h-9 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[0.74rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
    >
      <X className="h-3.5 w-3.5" /> {pick(locale, "Réinitialiser", "Zuruecksetzen", "Reset")}
    </button>
  );
}

/** Small language-code chips (fr/de/en) shared by the set/case/result views. */
export function LangBadges({ langs }: { langs: string[] }) {
  return (
    <div className="flex flex-wrap gap-1">
      {langs.map((l) => (
        <span
          key={l}
          className="rounded border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1 py-0.5 text-[0.54rem] font-medium uppercase tracking-wide text-[var(--tessera-text-muted)]"
        >
          {l}
        </span>
      ))}
    </div>
  );
}

// ── Generic data table (Connaissances treatment) ─────────────────────────────

export type Column<T> = {
  key: string;
  label: string;
  width?: string;
  numeric?: boolean;
  sortable?: boolean;
  sortValue?: (r: T) => string | number;
  render: (r: T) => React.ReactNode;
};

const PER_PAGE_OPTS = [10, 25, 50];
const MAX_PAGE_BUTTONS = 5;

function collator(locale: string): Intl.Collator {
  return new Intl.Collator(locale === "de" ? "de" : locale === "en" ? "en" : "fr", {
    numeric: true,
    sensitivity: "base",
  });
}

/**
 * A sortable, paginated, keyboard-reachable table. The PARENT owns filtering
 * (it knows the fields) and passes already-filtered `rows`; the table owns
 * sorting + pagination and calls `onRowClick` (which the parent turns into a
 * drawer open). `initialSortCol` seeds the default sort column.
 */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  noun,
  emptyLabel,
  selectedKey = null,
  onRowClick,
  initialSortCol = null,
  initialSortDir = "asc",
  minWidth = "760px",
  defaultPerPage = 10,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (r: T) => string;
  noun: string;
  emptyLabel: string;
  selectedKey?: string | null;
  onRowClick?: (r: T) => void;
  initialSortCol?: number | null;
  initialSortDir?: "asc" | "desc";
  minWidth?: string;
  defaultPerPage?: number;
}) {
  const locale = useLocale();
  const [sortCol, setSortCol] = useState<number | null>(initialSortCol);
  const [sortDir, setSortDir] = useState<"asc" | "desc">(initialSortDir);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(defaultPerPage);
  const col = collator(locale);

  const sorted = useMemo(() => {
    if (sortCol === null) return rows;
    const c = columns[sortCol];
    if (!c || c.sortable === false || !c.sortValue) return rows;
    const val = c.sortValue;
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = val(a);
      const bv = val(b);
      const cmp =
        typeof av === "number" && typeof bv === "number"
          ? av - bv
          : col.compare(String(av), String(bv));
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [rows, sortCol, sortDir, columns, col]);

  const total = sorted.length;
  const totalPages = Math.max(1, Math.ceil(total / perPage));
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset to page 1 on sort/size change
  useEffect(() => setPage(1), [total, perPage, sortCol, sortDir]);
  const safePage = Math.min(page, totalPages);
  const startIdx = (safePage - 1) * perPage;
  const pageRows = sorted.slice(startIdx, startIdx + perPage);
  const start = total === 0 ? 0 : startIdx + 1;
  const end = Math.min(startIdx + perPage, total);

  const onSort = (i: number) => {
    const c = columns[i];
    if (!c || c.sortable === false || !c.sortValue) return;
    if (i === sortCol) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortCol(i);
      setSortDir("asc");
    }
  };

  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
      <div className="overflow-x-auto">
        <table className="w-full table-fixed border-collapse text-left" style={{ minWidth }}>
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {columns.map((c, i) => {
                const sortable = c.sortable !== false && Boolean(c.sortValue);
                return (
                  <th
                    key={c.key}
                    aria-sort={
                      sortCol === i ? (sortDir === "asc" ? "ascending" : "descending") : "none"
                    }
                    style={c.width ? { width: c.width } : undefined}
                    className={cn(
                      "px-3 py-2 font-medium",
                      c.numeric ? "text-right" : "text-left",
                      i === 0 ? "" : "whitespace-nowrap",
                    )}
                  >
                    {sortable ? (
                      <button
                        type="button"
                        onClick={() => onSort(i)}
                        className={cn(
                          "inline-flex items-center gap-1 hover:text-[var(--tessera-text)]",
                          c.numeric ? "flex-row-reverse" : "",
                          sortCol === i ? "text-[var(--tessera-text)]" : "",
                        )}
                      >
                        {c.label}
                        {sortCol === i ? (
                          <ChevronDown
                            className={cn("h-3 w-3", sortDir === "asc" && "rotate-180")}
                          />
                        ) : (
                          <ChevronsUpDown className="h-3 w-3 opacity-40" />
                        )}
                      </button>
                    ) : (
                      c.label
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((r) => {
              const k = rowKey(r);
              const on = k === selectedKey;
              const clickable = Boolean(onRowClick);
              return (
                <tr
                  key={k}
                  role={clickable ? "button" : undefined}
                  tabIndex={clickable ? 0 : undefined}
                  onClick={clickable ? () => onRowClick?.(r) : undefined}
                  onKeyDown={
                    clickable
                      ? (e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            onRowClick?.(r);
                          }
                        }
                      : undefined
                  }
                  className={cn(
                    "border-b border-[var(--tessera-border)]/60 last:border-0",
                    clickable
                      ? "cursor-pointer focus:outline-none focus-visible:ring-1 focus-visible:ring-[#8b7cf0]"
                      : "",
                    on ? "bg-[#6d4aed]/10" : clickable ? "hover:bg-[var(--tessera-bg)]/40" : "",
                  )}
                >
                  {columns.map((c) => (
                    <td
                      key={c.key}
                      className={cn(
                        "px-3 py-2.5 text-[0.7rem]",
                        c.numeric ? "whitespace-nowrap text-right tabular-nums" : "",
                      )}
                    >
                      {c.render(r)}
                    </td>
                  ))}
                </tr>
              );
            })}
            {pageRows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-3 py-8 text-center text-[0.72rem] text-[var(--tessera-text-muted)]"
                >
                  {emptyLabel}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <Pagination
        page={safePage}
        totalPages={totalPages}
        start={start}
        end={end}
        total={total}
        perPage={perPage}
        noun={noun}
        onPage={setPage}
        onPerPage={setPerPage}
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
  noun,
  onPage,
  onPerPage,
}: {
  page: number;
  totalPages: number;
  start: number;
  end: number;
  total: number;
  perPage: number;
  noun: string;
  onPage: (p: number) => void;
  onPerPage: (n: number) => void;
}) {
  const locale = useLocale();
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--tessera-border)] px-3 py-2 text-[0.7rem] text-[var(--tessera-text-muted)]">
      <span className="tabular-nums" aria-live="polite">
        {start}-{end} {pick(locale, "sur", "von", "of")} {total} {noun}
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
        <span>{pick(locale, "Lignes par page", "Zeilen pro Seite", "Rows per page")}</span>
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

// ── Detail drawer (right-anchored, content-area height) ──────────────────────

/**
 * The shared row-click drawer: `fixed`, measured to the `<main>` content area
 * and anchored below the agent tab strip, with a non-modal `<dialog>`, Escape /
 * backdrop close and a Tab focus-trap. The tab supplies the header title and the
 * body via `children`.
 */
export function EvalDrawer({
  title,
  subtitle,
  icon,
  onClose,
  children,
}: {
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const locale = useLocale();
  const [rect, setRect] = useState<{
    top: number;
    left: number;
    width: number;
    height: number;
  } | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const measure = () => {
      const m = document.querySelector("main");
      if (!m) return;
      const r = m.getBoundingClientRect();
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
  useEffect(() => closeRef.current?.focus(), []);

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

  return (
    <div
      className="fixed z-50 flex justify-end overflow-hidden bg-[#020817]/70 p-2.5 backdrop-blur-[2px]"
      style={rect ?? { inset: 0 }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <dialog
        open
        ref={dialogRef}
        aria-modal="true"
        aria-label={title}
        onKeyDown={onTrapKey}
        onCancel={(event) => {
          event.preventDefault();
          onClose();
        }}
        className="static m-0 flex h-full w-full max-w-[460px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-0 text-[var(--tessera-text)] shadow-[0_12px_48px_rgba(0,0,0,0.5)]"
      >
        <div className="flex shrink-0 items-center justify-between gap-2 border-b border-[var(--tessera-border)] px-3.5 py-3">
          <div className="flex min-w-0 items-center gap-2">
            {icon ? (
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]">
                {icon}
              </span>
            ) : null}
            <div className="min-w-0">
              <span className="block truncate text-[0.85rem] font-semibold text-[var(--tessera-text)]">
                {title}
              </span>
              {subtitle ? (
                <span className="block truncate text-[0.62rem] text-[var(--tessera-text-muted)]">
                  {subtitle}
                </span>
              ) : null}
            </div>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label={pick(locale, "Fermer", "Schliessen", "Close")}
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3.5">{children}</div>
      </dialog>
    </div>
  );
}

// ── Export helpers (client-side blobs) ───────────────────────────────────────

/** Trigger a client-side file download of `content` as `filename`. */
export function downloadBlob(filename: string, mime: string, content: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function csvCell(v: unknown): string {
  const s = v === null || v === undefined ? "" : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** Serialize a header row + object rows to CSV text (RFC 4180-ish, `;`-free). */
export function toCsv(headers: string[], rows: (string | number | boolean | null)[][]): string {
  const head = headers.map(csvCell).join(",");
  const body = rows.map((r) => r.map(csvCell).join(",")).join("\n");
  return `${head}\n${body}\n`;
}
