"use client";

import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { FailedCasesReport } from "@/lib/api/schemas";

const KNOWN_CATEGORIES = [
  "prompt_injection",
  "pii_leak",
  "hallucination",
  "overconfidence",
  "regulatory_misstatement",
  "citation_fabrication",
  "tool_misuse",
  "policy_violation",
  "language_mixing",
  "escalation_failure",
];

const SEVERITIES = ["critical", "high", "medium", "low"];
const SEV_TONE: Record<string, "danger" | "warning" | "neutral"> = {
  critical: "danger",
  high: "warning",
  medium: "neutral",
  low: "neutral",
};
const SEV_RANK: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

const DONUT_COLORS = [
  "#ef4444",
  "#f59e0b",
  "#3b82f6",
  "#8b5cf6",
  "#10b981",
  "#ec4899",
  "#14b8a6",
  "#f97316",
  "#64748b",
  "#a3a3a3",
];

function useCatLabel() {
  const tq = useTranslations("quality");
  return (c: string) =>
    KNOWN_CATEGORIES.includes(c) ? tq(`failed.cat.${c}`) : c.replace(/_/g, " ");
}

/** Filterable failed-case catalogue (Cas échoués tab, reference image 03). */
export function FailedCasesTable({
  report,
  loading,
}: {
  report: FailedCasesReport | undefined;
  loading: boolean;
}) {
  const tq = useTranslations("quality");
  const catLabel = useCatLabel();
  const [sev, setSev] = useState<string | "all">("all");
  const [cat, setCat] = useState<string | "all">("all");

  const cases = report?.cases ?? [];
  const categories = useMemo(() => Object.keys(report?.by_category ?? {}), [report]);

  const shown = useMemo(
    () =>
      cases
        .filter(
          (c) => (sev === "all" || c.severity === sev) && (cat === "all" || c.category === cat),
        )
        .sort(
          (a, b) =>
            (SEV_RANK[a.severity] ?? 9) - (SEV_RANK[b.severity] ?? 9) ||
            a.case_id.localeCompare(b.case_id),
        ),
    [cases, sev, cat],
  );

  if (loading && !report) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{tq("failed.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-40 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="text-sm">{tq("failed.title")}</CardTitle>
          <span className="text-xs text-[var(--muted-foreground)]">
            {tq("failed.count", { shown: shown.length, total: report?.n ?? 0 })}
          </span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Chip active={sev === "all"} onClick={() => setSev("all")}>
            {tq("failed.all")}
          </Chip>
          {SEVERITIES.map((s) => (
            <Chip key={s} active={sev === s} onClick={() => setSev(s)} tone={SEV_TONE[s]}>
              {tq(`failed.sev.${s}`)} · {report?.by_severity?.[s] ?? 0}
            </Chip>
          ))}
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Chip active={cat === "all"} onClick={() => setCat("all")}>
            {tq("failed.all")}
          </Chip>
          {categories.map((c) => (
            <Chip key={c} active={cat === c} onClick={() => setCat(c)}>
              {catLabel(c)} · {report?.by_category?.[c] ?? 0}
            </Chip>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        {shown.length === 0 ? (
          <p className="py-8 text-center text-sm text-[var(--muted-foreground)]">
            {tq("failed.empty")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted-foreground)]">
                  <th className="py-2 pr-4 font-medium">{tq("failed.cols.id")}</th>
                  <th className="py-2 pr-4 font-medium">{tq("failed.cols.category")}</th>
                  <th className="py-2 pr-4 font-medium">{tq("failed.cols.severity")}</th>
                  <th className="py-2 pr-4 font-medium">{tq("failed.cols.lang")}</th>
                  <th className="py-2 font-medium">{tq("failed.cols.example")}</th>
                </tr>
              </thead>
              <tbody>
                {shown.map((c) => (
                  <tr key={c.case_id} className="border-b border-[var(--border)]/50 align-top">
                    <td className="py-2 pr-4 font-mono text-xs text-[var(--muted-foreground)]">
                      {c.case_id}
                    </td>
                    <td className="py-2 pr-4 whitespace-nowrap">{catLabel(c.category)}</td>
                    <td className="py-2 pr-4">
                      <Badge tone={SEV_TONE[c.severity] ?? "neutral"}>
                        {tq(`failed.sev.${c.severity}`)}
                      </Badge>
                    </td>
                    <td className="py-2 pr-4 uppercase text-[var(--muted-foreground)]">
                      {c.language}
                    </td>
                    <td className="py-2 text-[var(--muted-foreground)]">
                      <span className="line-clamp-2 max-w-md">{c.example}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/** "Répartition des échecs" donut over the failure categories (image 00/03). */
export function FailureDistribution({
  report,
  loading,
}: {
  report: FailedCasesReport | undefined;
  loading: boolean;
}) {
  const tq = useTranslations("quality");
  const catLabel = useCatLabel();
  const entries = Object.entries(report?.by_category ?? {}).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((s, [, n]) => s + n, 0) || 1;
  const r = 54;
  const circ = 2 * Math.PI * r;
  let acc = 0;

  if (loading && !report) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{tq("failed.distribution")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-40 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{tq("failed.distribution")}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap items-center gap-5">
          <div className="relative h-[150px] w-[150px] shrink-0">
            <svg viewBox="0 0 150 150" className="h-full w-full -rotate-90" aria-hidden="true">
              <circle
                cx="75"
                cy="75"
                r={r}
                fill="none"
                stroke="var(--tessera-border)"
                strokeWidth="14"
              />
              {entries.map(([key, n], i) => {
                const len = (n / total) * circ;
                const seg = (
                  <circle
                    key={key}
                    cx="75"
                    cy="75"
                    r={r}
                    fill="none"
                    stroke={DONUT_COLORS[i % DONUT_COLORS.length]}
                    strokeWidth="14"
                    strokeDasharray={`${len} ${circ - len}`}
                    strokeDashoffset={-acc}
                  />
                );
                acc += len;
                return seg;
              })}
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="font-serif text-2xl font-semibold tabular-nums">{total}</span>
              <span className="text-[0.65rem] text-[var(--muted-foreground)]">
                {tq("failed.casesLabel")}
              </span>
            </div>
          </div>
          <ul className="flex min-w-0 flex-1 flex-col gap-1 text-xs">
            {entries.map(([key, n], i) => (
              <li key={key} className="flex items-center justify-between gap-2">
                <span className="flex min-w-0 items-center gap-1.5">
                  <span
                    className="h-2 w-2 shrink-0 rounded-full"
                    style={{ background: DONUT_COLORS[i % DONUT_COLORS.length] }}
                  />
                  <span className="truncate">{catLabel(key)}</span>
                </span>
                <span className="shrink-0 tabular-nums text-[var(--muted-foreground)]">
                  {Math.round((n / total) * 100)}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}

function Chip({
  active,
  onClick,
  tone,
  children,
}: {
  active: boolean;
  onClick: () => void;
  tone?: "danger" | "warning" | "neutral";
  children: React.ReactNode;
}) {
  const dot =
    tone === "danger"
      ? "bg-red-500"
      : tone === "warning"
        ? "bg-amber-500"
        : tone === "neutral"
          ? "bg-[var(--muted-foreground)]"
          : "";
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition-colors ${
        active
          ? "border-gold-500/50 bg-gold-500/10 text-gold-200"
          : "border-[var(--border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
      }`}
    >
      {dot ? <span className={`h-1.5 w-1.5 rounded-full ${dot}`} /> : null}
      {children}
    </button>
  );
}
