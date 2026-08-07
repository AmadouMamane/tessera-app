"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, ChevronRight, ChevronsUpDown, Search, SearchX } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { useMemo, useState } from "react";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { QueryErrorState } from "@/components/cockpit/query-error-state";
import { ComponentDrawer } from "@/components/health/component-drawer";
import { observedAt, relativeNow } from "@/components/health/observability-shared";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchComponents } from "@/lib/api/client";
import type { ComponentCheck } from "@/lib/api/schemas";

const POLL_MS = 15_000;

type VerdictFilter = "all" | "ok" | "fail" | "blind";
type SortColumn = "name" | "verdict";
type Sort = { column: SortColumn; direction: 1 | -1 } | null;

/** How a verdict ranks when the column is sorted: the actionable ones first. */
const VERDICT_RANK: Record<string, number> = { fail: 0, blind: 1, skip: 2, ok: 3 };

/**
 * The stack's components, as the preflight witness sees them.
 *
 * This page used to render four KPI cards fed by `/healthz` and `/readyz` — two probes about
 * the agent process — while its own contextual help promised a component list with a last
 * check and its dependencies. On 2026-08-05 `tessera.preflight` reported ClickHouse FAIL and
 * this page showed everything operational, because nothing on it could go red for a dependency.
 *
 * Three verdicts, not two. `blind` — the probe could not look at all — is rendered as its own
 * state and never as "ok": a witness that cannot see may not report ok (ADR 0026). A reader who
 * cannot tell "the database is down" from "nobody asked the database" has no information.
 *
 * Since the mould pass this is a full table of the playbook's kind: filterable (by verdict and
 * by text), sortable within each half, and every row opens the component's drawer — the raw
 * answer, the capabilities that depend on it, its edges in the chain with their citations, and
 * its own slice of the history. No pagination, deliberately: the table is bounded at twenty by
 * construction (the registry is declared), and splitting the two halves across pages would
 * hide exactly the half-to-half comparison the group headers exist for.
 */
export function ComponentsPanel() {
  const t = useTranslations("health.components");
  const format = useFormatter();
  const [filter, setFilter] = useState<VerdictFilter>("all");
  const [needle, setNeedle] = useState("");
  const [sort, setSort] = useState<Sort>(null);
  const [selected, setSelected] = useState<ComponentCheck | null>(null);

  const query = useQuery({
    queryKey: ["components"],
    queryFn: ({ signal }) => fetchComponents(signal),
    refetchInterval: POLL_MS,
  });

  const tone = (verdict: string) =>
    verdict === "ok" ? "success" : verdict === "fail" ? "danger" : "warning";

  const rows = query.data?.components ?? [];
  const counts = useMemo(
    () => ({
      all: rows.length,
      ok: rows.filter((c) => c.verdict === "ok").length,
      fail: rows.filter((c) => c.verdict === "fail").length,
      blind: rows.filter((c) => c.verdict === "blind").length,
    }),
    [rows],
  );

  const visible = useMemo(() => {
    const lowered = needle.trim().toLowerCase();
    const matches = (component: ComponentCheck) => {
      if (filter !== "all" && component.verdict !== filter) return false;
      if (!lowered) return true;
      return [component.name, component.role, component.asked, component.detail].some((field) =>
        field.toLowerCase().includes(lowered),
      );
    };
    const filtered = rows.filter(matches);
    if (sort === null) return filtered;
    const compare = (a: ComponentCheck, b: ComponentCheck) => {
      const delta =
        sort.column === "name"
          ? a.name.localeCompare(b.name)
          : (VERDICT_RANK[a.verdict] ?? 9) - (VERDICT_RANK[b.verdict] ?? 9);
      return delta * sort.direction;
    };
    return [...filtered].sort(compare);
  }, [rows, filter, needle, sort]);

  function toggleSort(column: SortColumn) {
    setSort((current) => {
      if (current === null || current.column !== column) return { column, direction: 1 };
      if (current.direction === 1) return { column, direction: -1 };
      return null;
    });
  }

  const filters: VerdictFilter[] = ["all", "ok", "fail", "blind"];

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex min-w-0 items-center gap-1.5 text-sm">
          <span className="min-w-0 truncate">{t("title")}</span>
          <MetricInfo title={t("title")} what={t("what")} how={t("how")} source={t("source")} />
        </CardTitle>
        {query.data ? (
          <div className="flex items-center gap-2">
            {/* The observation instant, published because it is NOT the render instant: the
                probe is cached, and a component list that does not say when it last looked
                invites the reader to assume "now". */}
            <span className="text-[0.66rem] text-[var(--muted-foreground)]">
              {t("checked", {
                when: format.relativeTime(observedAt(query.data.observed_at), relativeNow()),
              })}
            </span>
            <Badge tone={tone(query.data.verdict === "clear" ? "ok" : query.data.verdict)}>
              {t(`verdict.${query.data.verdict}`, {
                ok: query.data.counts.stack_ok,
                total: query.data.counts.stack_total,
              })}
            </Badge>
          </div>
        ) : null}
      </CardHeader>
      <CardContent className="pt-1">
        {query.isPending ? (
          <Skeleton className="h-24 w-full" />
        ) : query.error || !query.data ? (
          // A failed READ is not an empty result: say the read failed, never "0 components".
          <QueryErrorState
            compact
            onRetry={() => void query.refetch()}
            retrying={query.isRefetching}
          />
        ) : rows.length > 0 ? (
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2">
              {/* Label and count used to sit side by side in the same size and nearly the same
                  colour, so four chips read as one run-on string — « Tous 20 OK 20 Pannes 0 ».
                  The count now wears its own chip: separated, tabular, and tied to the
                  selection state, which is also what finally makes the ACTIVE filter visible. */}
              <div className="flex items-center gap-1 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-muted)]/30 p-1">
                {filters.map((option) => {
                  const active = option === filter;
                  return (
                    <button
                      key={option}
                      type="button"
                      onClick={() => setFilter(option)}
                      aria-pressed={active}
                      className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[0.68rem] transition-colors ${
                        active
                          ? "bg-[var(--tessera-surface)] font-medium text-[var(--foreground)] shadow-sm ring-1 ring-inset ring-[var(--tessera-border)]"
                          : "text-[var(--muted-foreground)] hover:bg-[var(--tessera-muted)]/40 hover:text-[var(--foreground)]"
                      }`}
                    >
                      {t(`filter.${option}`)}
                      <span
                        className={`min-w-[1.15rem] rounded px-1 py-px text-center text-[0.62rem] tabular-nums ${
                          active
                            ? "bg-[var(--tessera-muted)] text-[var(--foreground)]"
                            : "bg-[var(--tessera-muted)]/50 text-[var(--muted-foreground)]"
                        }`}
                      >
                        {counts[option]}
                      </span>
                    </button>
                  );
                })}
              </div>
              {/* `shrink-0` is the fix, not the width: a flex item shrinks below its declared
                  `w-*` by default, so the chips group squeezed this one until the placeholder
                  read « Rechercher un composa ». The row already wraps — wrapping to its own
                  line is the right degradation, being cut in half is not. Sized for the
                  longest of the three locales (French, 24 characters). */}
              <label className="relative ml-auto flex shrink-0 items-center">
                <Search className="pointer-events-none absolute left-2 h-3 w-3 text-[var(--muted-foreground)]" />
                <input
                  type="search"
                  value={needle}
                  onChange={(event) => setNeedle(event.target.value)}
                  placeholder={t("searchPlaceholder")}
                  className="h-6.5 w-56 rounded-md border border-[var(--tessera-border)] bg-transparent pl-6.5 pr-2 text-[0.7rem] text-[var(--foreground)] outline-none transition-colors placeholder:text-[var(--muted-foreground)] focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
                />
              </label>
            </div>
            {visible.length === 0 ? (
              <p className="py-2 text-xs text-[var(--muted-foreground)]">{t("noMatch")}</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full table-fixed border-collapse text-left text-[0.72rem]">
                  <thead>
                    <tr className="border-b border-[var(--tessera-border)] text-[0.6rem] uppercase tracking-wide text-[var(--muted-foreground)]">
                      <SortableHeader
                        className="w-[11rem] 2xl:w-[14rem]"
                        label={t("col.name")}
                        column="name"
                        sort={sort}
                        onToggle={toggleSort}
                      />
                      <SortableHeader
                        className="w-[6.5rem]"
                        label={t("col.verdict")}
                        column="verdict"
                        sort={sort}
                        onToggle={toggleSort}
                      />
                      <th className="px-1.5 py-1 font-medium">{t("col.asked")}</th>
                      <th className="w-[36%] px-1.5 py-1 pr-2 text-right font-medium">
                        {t("col.answered")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {(["stack", "precondition"] as const).flatMap((group) => {
                      const groupRows = visible.filter((c) => c.group === group);
                      if (groupRows.length === 0) return [];
                      return [
                        <tr key={`h-${group}`}>
                          <th
                            colSpan={4}
                            className="px-1.5 pb-1 pt-3 text-left text-[0.6rem] font-medium uppercase tracking-wide text-[var(--muted-foreground)]"
                          >
                            <span className="flex items-baseline gap-2">
                              {t(`group.${group}`, { n: groupRows.length })}
                              {/* The two halves answer DIFFERENT questions and were rendered
                                  identically: Grafana being down is not the agent being broken.
                                  A reader who cannot tell the groups apart looks in the wrong
                                  place, which is the failure this whole page is about. */}
                              <span className="font-normal normal-case tracking-normal text-[var(--muted-foreground)]/70">
                                {t(`groupAsks.${group}`)}
                              </span>
                            </span>
                          </th>
                        </tr>,
                        ...groupRows.map((component) => (
                          <ComponentRow
                            key={`${group}-${component.name}`}
                            component={component}
                            onOpen={() => setSelected(component)}
                          />
                        )),
                      ];
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : (
          <p className="text-xs text-[var(--muted-foreground)]">{t("empty")}</p>
        )}
      </CardContent>
      {selected && query.data ? (
        <ComponentDrawer component={selected} data={query.data} onClose={() => setSelected(null)} />
      ) : null}
    </Card>
  );
}

function SortableHeader({
  label,
  column,
  sort,
  onToggle,
  className = "",
}: {
  label: string;
  column: SortColumn;
  sort: Sort;
  onToggle: (column: SortColumn) => void;
  className?: string;
}) {
  const active = sort?.column === column;
  const direction = active ? sort.direction : undefined;
  return (
    <th
      className={`px-1.5 py-1 font-medium ${className}`}
      aria-sort={active ? (direction === 1 ? "ascending" : "descending") : "none"}
    >
      <button
        type="button"
        onClick={() => onToggle(column)}
        className="flex items-center gap-0.5 uppercase tracking-wide transition-colors hover:text-[var(--foreground)]"
      >
        {label}
        {active ? (
          direction === 1 ? (
            <ArrowUp className="h-2.5 w-2.5" />
          ) : (
            <ArrowDown className="h-2.5 w-2.5" />
          )
        ) : (
          <ChevronsUpDown className="h-2.5 w-2.5 opacity-50" />
        )}
      </button>
    </th>
  );
}

/** Normalise for the echo test: whitespace and case must not make two identical cells differ. */
const flatten = (value: string) => value.trim().toLowerCase().replace(/\s+/g, " ");

function ComponentRow({
  component,
  onOpen,
}: {
  component: ComponentCheck;
  onOpen: () => void;
}) {
  const t = useTranslations("health.components");
  const tone =
    component.verdict === "ok" ? "success" : component.verdict === "fail" ? "danger" : "warning";

  // Translated where a translation exists, served English otherwise. A missing key must degrade
  // to the technical string — which is at least true — never to a blank cell or to next-intl's
  // rendering of the key path.
  const role = t.has(`role.${component.name}`) ? t(`role.${component.name}`) : component.role;

  // Looked up per GROUP, never by name alone. `postgres`, `clickhouse` and `prometheus` appear
  // in BOTH halves — the port and the adapter are two different questions with two different
  // answers, which is the whole reason the table has two groups. A name-only lookup gave the
  // stack rows the PRECONDITION's sentence: "postgres · la connexion propre au registre" next to
  // an answer about a DNS name not resolving. The stack's question is derived from the probe
  // and needs no map at all; only the preconditions carry declared prose.
  const asked =
    component.group === "precondition" && t.has(`asks.${component.name}`)
      ? t(`asks.${component.name}`)
      : askedLabel(component.asked, t);

  // `eval-package` answers `import eval, import eval.runner` — its own question, restated. The
  // badge already carries the outcome, so an echoing cell adds nothing and costs the reader a
  // double-take.
  const echoes = flatten(component.detail) === flatten(component.asked);

  // What the probe found, said in the reader's language, with the MACHINE's own words appended
  // and untouched. A stack probe carries an outcome code for exactly this; a precondition does
  // not, and falls back to preflight's own line — which is read identically in a terminal, and
  // which this page has no business paraphrasing.
  const found =
    component.outcome && t.has(`outcome.${component.outcome}`)
      ? [
          `${component.address} — ${t(`outcome.${component.outcome}`)}`,
          component.raw && !component.raw.startsWith("HTTP") ? component.raw : "",
          component.outcome === "http_ok" || component.outcome === "http_error"
            ? component.raw
            : "",
        ]
          .filter(Boolean)
          .join(" · ")
      : component.detail;

  return (
    <tr
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen();
        }
      }}
      tabIndex={0}
      aria-label={t("openRow", { name: component.name })}
      className="group cursor-pointer border-b border-[var(--tessera-border)]/60 align-top outline-none transition-colors last:border-0 hover:bg-[var(--tessera-muted)]/30 focus-visible:bg-[var(--tessera-muted)]/30"
    >
      <td className="px-1.5 py-1">
        <span className="flex items-center gap-1">
          <span className="block min-w-0 truncate font-medium text-[var(--foreground)]">
            {component.name}
          </span>
          <ChevronRight className="h-3 w-3 shrink-0 text-[var(--muted-foreground)] opacity-0 transition-opacity group-hover:opacity-70 group-focus-visible:opacity-70" />
        </span>
        {role ? (
          <span className="block truncate text-[0.62rem] text-[var(--muted-foreground)]">
            {role}
          </span>
        ) : null}
      </td>
      <td className="px-1.5 py-1">
        <Badge tone={tone}>{t(`state.${component.verdict}`)}</Badge>
        {/* The component's SECOND witness, surfaced only when the two disagree.
            « pourquoi langfuse-web est le problème alors qu'il est OK dans la liste ? » —
            because the socket answered and the adapter's read did not, and until now only the
            consequences block knew. Shown on divergence alone: a read that agrees adds a badge
            to nineteen calm rows and hides the one that matters. */}
        {component.read && component.read.verdict !== component.verdict ? (
          <span
            className={`mt-0.5 flex items-center gap-0.5 text-[0.6rem] ${
              component.read.verdict === "ok"
                ? "text-[var(--muted-foreground)]"
                : "text-[var(--tessera-fg-warning)]"
            }`}
            title={component.read.detail}
          >
            <SearchX className="h-3 w-3 shrink-0" />
            {t(`readSplit.${component.read.verdict}`)}
          </span>
        ) : null}
      </td>
      <td className="truncate px-1.5 py-1 text-[var(--muted-foreground)]" title={component.asked}>
        {asked || "—"}
      </td>
      <td
        className="truncate px-1.5 py-1 pr-2 text-right font-mono text-[0.66rem] text-[var(--muted-foreground)]"
        title={component.detail}
      >
        {echoes ? <span className="font-sans italic">{t("answeredByVerdict")}</span> : found}
      </td>
    </tr>
  );
}

/**
 * The derived stack question, rendered in the reader's language.
 *
 * The backend sends `TCP connect` / `HTTP GET /ping` — derived from the probe rather than
 * written out per component, so there is no second list to keep in step. Only the shape needs
 * translating, and the path stays verbatim because it is an address, not prose.
 */
function askedLabel(asked: string, t: (key: string, values?: Record<string, string>) => string) {
  if (asked === "TCP connect") return t("asks.tcp");
  const path = asked.match(/^HTTP GET (.+)$/)?.[1];
  return path ? t("asks.http", { path }) : asked;
}
