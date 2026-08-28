"use client";

import { ChevronLeft, ChevronRight, ChevronsUpDown, SortAsc, SortDesc } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { type ReactNode, useEffect, useMemo, useState } from "react";

import { cn } from "@/lib/cn";

export type PremiumColumn<T> = {
  key: string;
  label: string;
  width?: string;
  numeric?: boolean;
  sortable?: boolean;
  sortValue?: (row: T) => string | number;
  render: (row: T) => ReactNode;
};

const PER_PAGE = [5, 10, 25, 50] as const;

function pageWindow(page: number, totalPages: number): number[] {
  const span = Math.min(5, totalPages);
  let first = Math.max(1, page - Math.floor(span / 2));
  first = Math.min(first, Math.max(1, totalPages - span + 1));
  return Array.from({ length: span }, (_, index) => first + index);
}

/** Canonical sortable, paginated and drawer-ready cockpit entity table. */
export function PremiumDataTable<T>({
  columns,
  rows,
  rowKey,
  emptyLabel,
  selectedKey = null,
  onRowOpen,
  rowLabel,
  initialSortCol = null,
  initialSortDir = "asc",
  minWidth = "760px",
  defaultPerPage = 10,
  testId,
  className,
}: {
  columns: PremiumColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  emptyLabel: string;
  selectedKey?: string | null;
  onRowOpen?: (row: T) => void;
  rowLabel?: (row: T) => string;
  initialSortCol?: number | null;
  initialSortDir?: "asc" | "desc";
  minWidth?: string;
  defaultPerPage?: number;
  testId?: string;
  className?: string;
}) {
  const locale = useLocale();
  const t = useTranslations("table");
  const [sortCol, setSortCol] = useState<number | null>(initialSortCol);
  const [sortDir, setSortDir] = useState<"asc" | "desc">(initialSortDir);
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(defaultPerPage);
  useEffect(() => {
    if (defaultPerPage > 5 && window.matchMedia("(max-width: 639px)").matches) {
      setPerPage(5);
    }
  }, [defaultPerPage]);
  const collator = useMemo(
    () => new Intl.Collator(locale, { numeric: true, sensitivity: "base" }),
    [locale],
  );
  const sorted = useMemo(() => {
    if (sortCol === null) return rows;
    const column = columns[sortCol];
    if (!column?.sortValue || column.sortable === false) return rows;
    return [...rows].sort((left, right) => {
      const a = column.sortValue?.(left);
      const b = column.sortValue?.(right);
      const compared =
        typeof a === "number" && typeof b === "number"
          ? a - b
          : collator.compare(String(a), String(b));
      return sortDir === "asc" ? compared : -compared;
    });
  }, [rows, columns, sortCol, sortDir, collator]);

  const total = sorted.length;
  const totalPages = Math.max(1, Math.ceil(total / perPage));
  // biome-ignore lint/correctness/useExhaustiveDependencies: table-model changes intentionally reset pagination.
  useEffect(() => setPage(1), [total, perPage, sortCol, sortDir]);
  const safePage = Math.min(page, totalPages);
  const startIndex = (safePage - 1) * perPage;
  const visibleRows = sorted.slice(startIndex, startIndex + perPage);
  const start = total === 0 ? 0 : startIndex + 1;
  const end = Math.min(startIndex + perPage, total);
  const clickable = Boolean(onRowOpen);

  function toggleSort(index: number) {
    const column = columns[index];
    if (!column?.sortValue || column.sortable === false) return;
    if (sortCol === index) setSortDir((value) => (value === "asc" ? "desc" : "asc"));
    else {
      setSortCol(index);
      setSortDir("asc");
    }
  }

  return (
    <section
      data-premium-table="true"
      data-testid={testId}
      className={cn(
        "flex min-w-0 flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] shadow-[inset_0_1px_0_rgba(255,255,255,0.025)]",
        className,
      )}
    >
      <div className="hidden overflow-x-auto overscroll-x-contain [scrollbar-gutter:stable] sm:block">
        <table className="w-full table-fixed border-collapse text-left" style={{ minWidth }}>
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-xs uppercase tracking-[0.06em] text-[var(--tessera-text-muted)]">
              {columns.map((column, index) => {
                const sortable = column.sortable !== false && Boolean(column.sortValue);
                return (
                  <th
                    key={column.key}
                    aria-sort={
                      sortable && sortCol === index
                        ? sortDir === "asc"
                          ? "ascending"
                          : "descending"
                        : undefined
                    }
                    style={column.width ? { width: column.width } : undefined}
                    className={cn(
                      "bg-[var(--tessera-surface)] px-3 py-2 font-medium",
                      index === 0 && "sticky left-0 z-[2] shadow-[1px_0_0_var(--tessera-border)]",
                      column.numeric ? "text-right" : "text-left",
                      index > 0 && "whitespace-nowrap",
                    )}
                  >
                    {sortable ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(index)}
                        className={cn(
                          "inline-flex items-center gap-1 rounded-sm outline-none transition-colors motion-reduce:transition-none hover:text-[var(--tessera-text)] focus-visible:ring-2 focus-visible:ring-[var(--tessera-fg-info)]/45",
                          column.numeric && "flex-row-reverse",
                        )}
                      >
                        {column.label}
                        {sortCol === index ? (
                          sortDir === "asc" ? (
                            <SortAsc className="h-3 w-3 text-[var(--tessera-fg-info)]" />
                          ) : (
                            <SortDesc className="h-3 w-3 text-[var(--tessera-fg-info)]" />
                          )
                        ) : (
                          <ChevronsUpDown className="h-3 w-3 opacity-40" />
                        )}
                      </button>
                    ) : (
                      column.label
                    )}
                  </th>
                );
              })}
              {clickable ? <th className="w-28 px-3 py-2" aria-hidden="true" /> : null}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => {
              const key = rowKey(row);
              const selected = key === selectedKey;
              return (
                <tr
                  key={key}
                  role={clickable ? "button" : undefined}
                  aria-haspopup={clickable ? "dialog" : undefined}
                  aria-label={clickable ? rowLabel?.(row) : undefined}
                  tabIndex={clickable ? 0 : undefined}
                  onClick={clickable ? () => onRowOpen?.(row) : undefined}
                  onKeyDown={
                    clickable
                      ? (event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            onRowOpen?.(row);
                          }
                        }
                      : undefined
                  }
                  className={cn(
                    "group border-b border-[var(--tessera-border)]/60 outline-none transition-colors last:border-0 motion-reduce:transition-none",
                    clickable &&
                      "cursor-pointer hover:bg-[color-mix(in_oklch,var(--tessera-fg-info)_7%,transparent)] focus-visible:bg-[color-mix(in_oklch,var(--tessera-fg-info)_9%,transparent)]",
                    selected &&
                      "bg-[color-mix(in_oklch,var(--tessera-fg-info)_11%,transparent)] shadow-[inset_3px_0_0_var(--tessera-fg-info)]",
                  )}
                >
                  {columns.map((column, index) => (
                    <td
                      key={column.key}
                      className={cn(
                        "px-3 py-2.5 text-xs leading-5 text-[var(--tessera-text)]",
                        index === 0 &&
                          "sticky left-0 z-[1] bg-[var(--tessera-surface)] shadow-[1px_0_0_var(--tessera-border)] group-hover:bg-[color-mix(in_oklch,var(--tessera-fg-info)_7%,var(--tessera-surface))] group-focus-visible:bg-[color-mix(in_oklch,var(--tessera-fg-info)_9%,var(--tessera-surface))]",
                        selected &&
                          index === 0 &&
                          "bg-[color-mix(in_oklch,var(--tessera-fg-info)_11%,var(--tessera-surface))]",
                        column.numeric && "whitespace-nowrap text-right tabular-nums",
                      )}
                    >
                      {column.render(row)}
                    </td>
                  ))}
                  {clickable ? (
                    <td className="px-3 py-2.5">
                      <span className="flex items-center justify-end gap-1 whitespace-nowrap text-xs text-[var(--tessera-fg-info)]">
                        <span className="opacity-0 transition-opacity motion-reduce:transition-none group-hover:opacity-100 group-focus-visible:opacity-100">
                          {t("rowOpen")}
                        </span>
                        <ChevronRight className="h-3.5 w-3.5 opacity-55 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100 motion-reduce:transition-none" />
                      </span>
                    </td>
                  ) : null}
                </tr>
              );
            })}
            {visibleRows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length + (clickable ? 1 : 0)}
                  className="px-4 py-10 text-center text-xs text-[var(--tessera-text-muted)]"
                >
                  {emptyLabel}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <div className="divide-y divide-[var(--tessera-border)] sm:hidden">
        {visibleRows.map((row) => {
          const key = rowKey(row);
          const selected = key === selectedKey;
          const identity = columns[0];
          return (
            <article
              key={key}
              role={clickable ? "button" : undefined}
              aria-haspopup={clickable ? "dialog" : undefined}
              aria-label={clickable ? rowLabel?.(row) : undefined}
              aria-pressed={clickable ? selected : undefined}
              tabIndex={clickable ? 0 : undefined}
              onClick={clickable ? () => onRowOpen?.(row) : undefined}
              onKeyDown={
                clickable
                  ? (event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        onRowOpen?.(row);
                      }
                    }
                  : undefined
              }
              className={cn(
                "px-3 py-3 outline-none transition-colors motion-reduce:transition-none",
                clickable &&
                  "cursor-pointer hover:bg-[var(--tessera-bg-soft)] focus-visible:bg-[var(--tessera-bg-soft)] focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--tessera-fg-info)]/45",
                selected &&
                  "bg-[color-mix(in_oklch,var(--tessera-fg-info)_11%,transparent)] shadow-[inset_3px_0_0_var(--tessera-fg-info)]",
              )}
            >
              {identity ? (
                <div className="mb-3 flex min-h-11 items-center justify-between gap-3">
                  <div className="min-w-0 text-sm font-semibold text-[var(--tessera-text-strong)]">
                    {identity.render(row)}
                  </div>
                  {clickable ? (
                    <span className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-[var(--tessera-fg-info)]">
                      {t("rowOpen")}
                      <ChevronRight className="h-4 w-4" aria-hidden />
                    </span>
                  ) : null}
                </div>
              ) : null}
              <dl className="grid gap-2">
                {columns.slice(1).map((column) => (
                  <div
                    key={column.key}
                    className="grid min-w-0 grid-cols-[minmax(6.5rem,38%)_minmax(0,1fr)] items-start gap-3"
                  >
                    <dt className="text-xs font-medium text-[var(--tessera-text-muted)]">
                      {column.label}
                    </dt>
                    <dd
                      className={cn(
                        "min-w-0 break-words text-xs leading-5 text-[var(--tessera-text)]",
                        column.numeric && "text-right tabular-nums",
                      )}
                    >
                      {column.render(row)}
                    </dd>
                  </div>
                ))}
              </dl>
            </article>
          );
        })}
        {visibleRows.length === 0 ? (
          <p className="px-4 py-10 text-center text-sm text-[var(--tessera-text-muted)]">
            {emptyLabel}
          </p>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--tessera-border)] px-3 py-2 text-xs text-[var(--tessera-text-muted)]">
        <span className="tabular-nums" aria-live="polite">
          {t("summary", { start, end, total })}
        </span>
        <div className="flex items-center gap-1">
          <PageButton
            label={t("prev")}
            disabled={safePage <= 1}
            onClick={() => setPage(Math.max(1, safePage - 1))}
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </PageButton>
          {pageWindow(safePage, totalPages).map((number) => (
            <PageButton
              key={number}
              label={String(number)}
              current={number === safePage}
              onClick={() => setPage(number)}
            >
              {number}
            </PageButton>
          ))}
          <PageButton
            label={t("next")}
            disabled={safePage >= totalPages}
            onClick={() => setPage(Math.min(totalPages, safePage + 1))}
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </PageButton>
        </div>
        <label className="flex items-center gap-2">
          <span>{t("perPage")}</span>
          <select
            value={perPage}
            onChange={(event) => setPerPage(Number(event.target.value))}
            className="h-11 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 text-xs text-[var(--tessera-text)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--tessera-fg-info)]/45 sm:h-8"
          >
            {PER_PAGE.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
      </div>
    </section>
  );
}

function PageButton({
  label,
  disabled,
  current,
  onClick,
  children,
}: {
  label: string;
  disabled?: boolean;
  current?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-current={current ? "page" : undefined}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "flex h-11 min-w-11 items-center justify-center rounded-md border px-2 text-xs tabular-nums outline-none transition-colors motion-reduce:transition-none focus-visible:ring-2 focus-visible:ring-[var(--tessera-fg-info)]/45 disabled:opacity-40 sm:h-8 sm:min-w-8",
        current
          ? "border-[var(--tessera-fg-info)]/55 bg-[var(--tessera-fg-info)]/12 font-medium text-[var(--tessera-text-strong)]"
          : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
      )}
    >
      {children}
    </button>
  );
}
