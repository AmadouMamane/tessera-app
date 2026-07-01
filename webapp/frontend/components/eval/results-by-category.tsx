"use client";

import { Check, X } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ScorecardResult } from "@/lib/api/schemas";

const CATEGORY_LABELS: Record<string, string> = {
  prompt_injection: "Prompt Injection",
  pii_leak: "PII Leak",
  hallucination: "Hallucination",
  overconfidence: "Overconfidence",
  citation_fabrication: "Citation Fabrication",
  tool_misuse: "Tool Misuse",
  policy_violation: "Policy Violation",
  regulatory_misstatement: "Regulatory Misstatement",
  language_mixing: "Language Mixing",
  escalation_failure: "Escalation Failure",
};

const CATEGORY_TONE: Record<string, string> = {
  prompt_injection: "danger",
  pii_leak: "danger",
  hallucination: "warning",
  overconfidence: "warning",
  citation_fabrication: "warning",
  tool_misuse: "danger",
  policy_violation: "navy",
  regulatory_misstatement: "navy",
  language_mixing: "info",
  escalation_failure: "danger",
};

type Filter = "all" | "failed" | "passed";

interface CategoryColumns {
  case: string;
  language: string;
  result: string;
  expected: string;
  failureReason: string;
}

interface FilterLabels {
  all: string;
  failed: string;
  passed: string;
  empty: string;
}

/**
 * Per-case results, grouped into one card per category. A client-side filter
 * (`All · Failures · Passes`) narrows the visible rows — better than sorting the
 * binary Result column (rows are already failures-first), and it keeps the
 * category-card layout intact: categories with no matching row are hidden, and
 * the per-category header counts/bar always reflect the *full* run, not the
 * filtered subset (the pass rate is a fact, not a view).
 */
export function ResultsByCategory({
  results,
  columns,
  passLabel,
  failLabel,
  filterLabels,
}: {
  results: ScorecardResult[];
  columns: CategoryColumns;
  passLabel: string;
  failLabel: string;
  filterLabels: FilterLabels;
}) {
  const [filter, setFilter] = useState<Filter>("all");

  const failedCount = useMemo(() => results.filter((r) => !r.passed).length, [results]);
  const passedCount = results.length - failedCount;

  const byCategory = useMemo(() => groupBy(results, (r) => r.category || "other"), [results]);
  const visible = Object.entries(byCategory)
    .map(([category, group]) => {
      // Failures first (❌ before ✅), then by case id — two contiguous blocks.
      const items = [...group].sort(
        (a, b) => Number(a.passed) - Number(b.passed) || a.case_id.localeCompare(b.case_id),
      );
      const shown = items.filter(
        (r) => filter === "all" || (filter === "failed" ? !r.passed : r.passed),
      );
      const passed = items.filter((r) => r.passed).length;
      return { category, shown, passed, total: items.length };
    })
    .filter((g) => g.shown.length > 0);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-1.5">
        <FilterChip active={filter === "all"} onClick={() => setFilter("all")}>
          {filterLabels.all} <Count>{results.length}</Count>
        </FilterChip>
        <FilterChip active={filter === "failed"} onClick={() => setFilter("failed")}>
          {filterLabels.failed} <Count>{failedCount}</Count>
        </FilterChip>
        <FilterChip active={filter === "passed"} onClick={() => setFilter("passed")}>
          {filterLabels.passed} <Count>{passedCount}</Count>
        </FilterChip>
      </div>

      {visible.length === 0 ? (
        <Card>
          <CardContent className="py-6 text-center text-sm text-[var(--muted-foreground)]">
            {filterLabels.empty}
          </CardContent>
        </Card>
      ) : (
        visible.map(({ category, shown, passed, total }) => {
          const rate = total ? passed / total : 0;
          return (
            <Card key={category} className="overflow-hidden">
              <CardContent className="p-0">
                {/* Category header */}
                <div className="flex items-center justify-between border-b border-[var(--border)] bg-gradient-to-b from-[var(--muted)]/40 to-transparent px-5 py-3.5">
                  <div className="flex items-center gap-3">
                    <Badge
                      tone={
                        (CATEGORY_TONE[category] as "danger" | "warning" | "navy" | "info") ??
                        "neutral"
                      }
                    >
                      {CATEGORY_LABELS[category] ?? category}
                    </Badge>
                    <span className="text-sm text-[var(--muted-foreground)]">
                      {passed}/{total}
                    </span>
                  </div>
                  <PassRateBar rate={rate} />
                </div>
                {/* Cases */}
                <Table className="table-fixed">
                  <colgroup>
                    <col className="w-[22%]" />
                    <col className="w-[7%]" />
                    <col className="w-[8%]" />
                    <col className="w-[35%]" />
                    <col className="w-[28%]" />
                  </colgroup>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{columns.case}</TableHead>
                      <TableHead className="text-center">{columns.language}</TableHead>
                      <TableHead className="text-center">{columns.result}</TableHead>
                      <TableHead>{columns.expected}</TableHead>
                      <TableHead>{columns.failureReason}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {shown.map((result) => (
                      <TableRow key={`${result.case_id}-${result.language}`}>
                        <TableCell className="max-w-0 overflow-hidden align-top">
                          <div className="w-full font-mono text-xs leading-[18px]">
                            {result.case_id.replace(/_/g, "_​")}
                          </div>
                          {result.title && (
                            <div className="mt-0.5 w-full break-words text-xs leading-[18px] text-[var(--muted-foreground)]">
                              {result.title}
                            </div>
                          )}
                        </TableCell>
                        <TableCell className="align-top text-center">
                          <Badge
                            tone={
                              result.language === "fr"
                                ? "navy"
                                : result.language === "de"
                                  ? "gold"
                                  : "info"
                            }
                          >
                            {result.language.toUpperCase()}
                          </Badge>
                        </TableCell>
                        <TableCell className="align-top text-center">
                          {result.passed ? (
                            <Badge tone="success" className="gap-1">
                              <Check className="h-3 w-3" /> {passLabel}
                            </Badge>
                          ) : (
                            <Badge tone="danger" className="gap-1">
                              <X className="h-3 w-3" /> {failLabel}
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell className="max-w-0 overflow-hidden align-top text-xs text-[var(--muted-foreground)]">
                          <div className="w-full break-words leading-[18px] text-justify">
                            {result.expected_behavior ?? "—"}
                          </div>
                        </TableCell>
                        <TableCell className="max-w-0 overflow-hidden align-top">
                          {result.reasons.length > 0 ? (
                            <ul className="w-full space-y-1">
                              {result.reasons.map((r, i) => (
                                <li
                                  // biome-ignore lint/suspicious/noArrayIndexKey: failure reasons are render-once and never reorder
                                  key={i}
                                  className="break-words text-justify text-xs text-red-600 leading-[18px] dark:text-red-400"
                                >
                                  {r}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <span className="text-xs text-[var(--muted-foreground)]">—</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          );
        })
      )}
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
        active
          ? "border-gold-500/60 bg-gold-500/10 text-[var(--foreground)]"
          : "border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--muted)]/40"
      }`}
    >
      {children}
    </button>
  );
}

function Count({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded bg-[var(--muted)]/70 px-1.5 py-0.5 text-[0.65rem] tabular-nums">
      {children}
    </span>
  );
}

function PassRateBar({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100);
  const gradient =
    pct >= 80
      ? "bg-gradient-to-r from-green-600 to-green-400"
      : pct >= 50
        ? "bg-gradient-to-r from-amber-600 to-amber-400"
        : "bg-gradient-to-r from-red-600 to-red-400";
  const text =
    pct >= 80
      ? "text-green-700 dark:text-green-400"
      : pct >= 50
        ? "text-amber-700 dark:text-amber-400"
        : "text-red-700 dark:text-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="h-[4px] w-24 overflow-hidden rounded-full bg-[var(--tessera-border)]">
        <div
          className={`h-full ${gradient} transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`w-8 text-right font-semibold text-xs tabular-nums ${text}`}>{pct}%</span>
    </div>
  );
}

function groupBy<T>(arr: T[], key: (item: T) => string): Record<string, T[]> {
  return arr.reduce<Record<string, T[]>>((acc, item) => {
    const k = key(item);
    const bucket = acc[k] ?? [];
    bucket.push(item);
    acc[k] = bucket;
    return acc;
  }, {});
}
