"use client";

/**
 * The AGENT / Évaluations sub-tab views that are net-new beyond the overview:
 * Jeux d'évaluations (curated eval sets), Résultats + Erreurs (per-case run
 * outcomes), Comparaisons (run vs run), Versions & historique (the run timeline)
 * and Exports (client-side downloads). Each draws only on real payload data and
 * degrades to an honest empty state; every table gets the shared Connaissances
 * treatment via `DataTable`, every row-click opens `EvalDrawer`.
 */

import {
  AlertTriangle,
  ArrowRight,
  Beaker,
  Boxes,
  Download,
  FileJson,
  FileText,
  GitCompare,
  History,
  ListChecks,
  ShieldAlert,
  Table2,
  Wrench,
} from "lucide-react";
import type { Route } from "next";
import { useLocale } from "next-intl";
import { useMemo, useState } from "react";

import { Link } from "@/i18n/navigation";
import { agentPath } from "@/lib/agent-context";
import type { AgentEvaluations as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import { useAgentId } from "@/lib/use-agent-id";
import {
  type Column,
  DataTable,
  EvalDrawer,
  FilterBar,
  FilterDropdown,
  LangBadges,
  PASS_DOT,
  PASS_TONE,
  ResetButton,
  SEVERITY_PILL,
  SearchInput,
  TYPE_TONE,
  downloadBlob,
  pick,
  toCsv,
} from "./evaluation-shared";

type SetRow = NonNullable<Data["sets"]>["rows"][number];
type CaseRow = NonNullable<Data["sets"]>["cases"][number];
type ResultRow = NonNullable<Data["results"]>["rows"][number];
type RunItem = NonNullable<Data["runs"]>["items"][number];

function EmptyState({ label }: { label: string }) {
  return (
    <div className="rounded-lg border border-dashed border-[var(--tessera-border)] px-4 py-10 text-center text-[0.8rem] text-[var(--tessera-text-muted)]">
      {label}
    </div>
  );
}

function TabHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <h2 className="text-[0.95rem] font-semibold text-[var(--tessera-text)]">{title}</h2>
      {subtitle ? (
        <p className="text-[0.72rem] text-[var(--tessera-text-muted)]">{subtitle}</p>
      ) : null}
    </div>
  );
}

/** A compact labelled stat used across the tab summary strips. */
function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex min-w-[92px] flex-col gap-0.5 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2">
      <span className="text-[0.56rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
        {label}
      </span>
      <span
        className={cn(
          "text-[1.05rem] font-semibold tabular-nums",
          tone ?? "text-[var(--tessera-text)]",
        )}
      >
        {value}
      </span>
    </div>
  );
}

function DrawerField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 text-[0.72rem]">
      <span className="text-[var(--tessera-text-muted)]">{label}</span>
      <span className="min-w-0 truncate text-right font-medium text-[var(--tessera-text)]">
        {children}
      </span>
    </div>
  );
}

function DrawerBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5">
      <h3 className="mb-1.5 text-[0.62rem] font-semibold uppercase tracking-wide text-[var(--tessera-text-muted)]">
        {title}
      </h3>
      {children}
    </div>
  );
}

// ── Jeux d'évaluations ───────────────────────────────────────────────────────

export function SetsTab({ data }: { data: Data }) {
  const locale = useLocale();
  const sets = data.sets;
  const [search, setSearch] = useState("");
  const [scope, setScope] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);

  const rows = sets?.rows ?? [];
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((r) => {
      if (scope === "bound" && !r.bound) return false;
      if (scope === "shared" && r.bound) return false;
      if (q && !`${r.name} ${r.slug} ${r.description}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [rows, search, scope]);

  if (!sets)
    return (
      <EmptyState label={pick(locale, "Aucun jeu d'évaluations.", "Keine Sets.", "No sets.")} />
    );

  const selectedRow = rows.find((r) => r.slug === selected) ?? null;
  const cases = sets.cases;
  const columns: Column<SetRow>[] = [
    {
      key: "name",
      label: sets.columns[0] ?? "Jeu",
      width: "34%",
      sortValue: (r) => r.name,
      render: (r) => (
        <div className="flex min-w-0 items-center gap-2">
          <Boxes className="h-4 w-4 shrink-0 text-[#8b7cf0]" />
          <span className="truncate font-medium text-[var(--tessera-text)]">{r.name}</span>
          {r.active ? (
            <span className="shrink-0 rounded-full border border-emerald-500/40 bg-emerald-500/15 px-1.5 py-0.5 text-[0.5rem] font-medium uppercase text-emerald-300">
              {pick(locale, "Actif", "Aktiv", "Active")}
            </span>
          ) : null}
        </div>
      ),
    },
    {
      key: "scope",
      label: sets.columns[1] ?? "Portée",
      width: "18%",
      sortValue: (r) => (r.bound ? `1${r.agent_id}` : "0"),
      render: (r) =>
        r.bound ? (
          <span className="text-[0.68rem] text-[var(--tessera-text)]">
            {sets.bound_label}
            <span className="ml-1 font-mono text-[0.6rem] text-[var(--tessera-text-muted)]">
              {r.agent_id}
            </span>
          </span>
        ) : (
          <span className="text-[0.68rem] text-[var(--tessera-text-muted)]">
            {sets.shared_label}
          </span>
        ),
    },
    {
      key: "cases",
      label: sets.columns[2] ?? "Cas",
      width: "14%",
      numeric: true,
      sortValue: (r) => r.case_count,
      render: (r) => (
        <span title={r.floor_count > 0 ? `+${r.floor_count} ${sets.floor_note}` : undefined}>
          {r.case_count}
          {r.floor_count > 0 ? (
            <span className="ml-1 text-[0.58rem] text-[var(--tessera-text-muted)]">
              (+{r.floor_count})
            </span>
          ) : null}
        </span>
      ),
    },
    {
      key: "critical",
      label: sets.columns[3] ?? "Critiques",
      width: "12%",
      numeric: true,
      sortValue: (r) => r.critical_count,
      render: (r) => <span className="text-[#ff9bb0]">{r.critical_count}</span>,
    },
    {
      key: "categories",
      label: sets.columns[4] ?? "Catégories",
      width: "10%",
      numeric: true,
      sortValue: (r) => r.category_count,
      render: (r) => r.category_count,
    },
    {
      key: "languages",
      label: sets.columns[5] ?? "Langues",
      width: "12%",
      sortable: false,
      render: (r) => <LangBadges langs={r.languages} />,
    },
  ];

  return (
    <div className="flex flex-col gap-2.5">
      <TabHeader title={sets.title} subtitle={sets.subtitle} />
      <div className="flex flex-wrap gap-2">
        <Stat label={pick(locale, "Jeux", "Sets", "Sets")} value={String(sets.total)} />
        <Stat
          label={pick(locale, "Cas au catalogue", "Faelle im Katalog", "Catalogue cases")}
          value={String(cases.length)}
        />
        <Stat
          label={pick(locale, "Cas critiques", "Kritische Faelle", "Critical cases")}
          value={String(cases.filter((c) => c.severity === "critical").length)}
          tone="text-[#ff9bb0]"
        />
      </div>
      <FilterBar>
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder={pick(locale, "Rechercher un jeu…", "Set suchen…", "Search a set…")}
        />
        <FilterDropdown
          label={pick(locale, "Portée", "Geltung", "Scope")}
          value={scope}
          onSelect={setScope}
          options={[
            { value: "all", label: pick(locale, "Tous", "Alle", "All") },
            { value: "bound", label: sets.bound_label },
            { value: "shared", label: sets.shared_label },
          ]}
        />
        {(search || scope !== "all") && (
          <ResetButton
            onClick={() => {
              setSearch("");
              setScope("all");
            }}
          />
        )}
      </FilterBar>
      <DataTable
        columns={columns}
        rows={filtered}
        rowKey={(r) => r.slug}
        noun={pick(locale, "jeux", "Sets", "sets")}
        emptyLabel={sets.empty_label}
        selectedKey={selectedRow?.slug ?? null}
        onRowClick={(r) => setSelected(r.slug)}
        initialSortCol={2}
        initialSortDir="desc"
        minWidth="820px"
      />
      {selectedRow ? (
        <SetDrawer
          row={selectedRow}
          cases={cases}
          labels={sets}
          onClose={() => setSelected(null)}
        />
      ) : null}
    </div>
  );
}

function SetDrawer({
  row,
  cases,
  labels,
  onClose,
}: {
  row: SetRow;
  cases: CaseRow[];
  labels: NonNullable<Data["sets"]>;
  onClose: () => void;
}) {
  const locale = useLocale();
  const byId = useMemo(() => new Map(cases.map((c) => [c.id, c])), [cases]);
  const setCases = row.case_ids.map((id) => byId.get(id)).filter((c): c is CaseRow => Boolean(c));
  return (
    <EvalDrawer
      title={row.name}
      subtitle={row.bound ? `${labels.bound_label} · ${row.agent_id}` : labels.shared_label}
      icon={<Boxes className="h-4 w-4 text-[#8b7cf0]" />}
      onClose={onClose}
    >
      {row.active ? (
        <div className="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1.5 text-[0.68rem] text-emerald-300">
          {labels.active_label}
        </div>
      ) : null}
      {row.description ? (
        <p className="text-[0.72rem] leading-relaxed text-[var(--tessera-text-muted)]">
          {row.description}
        </p>
      ) : null}
      <DrawerBlock title={pick(locale, "Composition", "Zusammensetzung", "Composition")}>
        <div className="flex flex-col gap-1.5">
          <DrawerField label={labels.columns[2] ?? "Cas"}>
            {row.case_count}
            {row.floor_count > 0 ? ` (+${row.floor_count} ${labels.floor_note})` : ""}
          </DrawerField>
          <DrawerField label={labels.columns[3] ?? "Critiques"}>{row.critical_count}</DrawerField>
          <DrawerField label={labels.columns[4] ?? "Catégories"}>{row.category_count}</DrawerField>
          <DrawerField label={labels.columns[5] ?? "Langues"}>
            {row.languages.join(", ")}
          </DrawerField>
        </div>
      </DrawerBlock>
      {row.gate_rationale ? (
        <DrawerBlock title={labels.rationale_label}>
          <p className="text-[0.68rem] leading-relaxed text-[var(--tessera-text-muted)]">
            {row.gate_rationale}
          </p>
        </DrawerBlock>
      ) : null}
      <DrawerBlock title={`${labels.cases_label} (${setCases.length})`}>
        <ul className="flex flex-col gap-1">
          {setCases.map((c) => (
            <li key={c.id} className="flex items-center gap-2 text-[0.68rem]">
              <span
                className={cn(
                  "shrink-0 rounded border px-1 py-0.5 text-[0.5rem] font-medium uppercase",
                  SEVERITY_PILL[c.severity_tone] ?? SEVERITY_PILL.muted,
                )}
              >
                {c.severity_label}
              </span>
              <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]" title={c.title}>
                {c.title}
              </span>
              <span className="shrink-0 text-[0.58rem] text-[var(--tessera-text-muted)]">
                {c.category_label}
              </span>
            </li>
          ))}
        </ul>
      </DrawerBlock>
    </EvalDrawer>
  );
}

// ── Résultats / Erreurs ──────────────────────────────────────────────────────

export function ResultsTab({ data, mode }: { data: Data; mode: "all" | "failed" }) {
  const locale = useLocale();
  const agentId = useAgentId();
  const results = data.results;
  const [search, setSearch] = useState("");
  const [typeKey, setTypeKey] = useState("all");
  const [statusKey, setStatusKey] = useState("all");
  const [langKey, setLangKey] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);

  const base = useMemo(
    () => (results?.rows ?? []).filter((r) => (mode === "failed" ? !r.passed : true)),
    [results, mode],
  );
  const typeOptions = useMemo(() => {
    const seen = new Map<string, string>();
    for (const r of base) if (!seen.has(r.category)) seen.set(r.category, r.category_label);
    return [...seen.entries()].map(([value, label]) => ({ value, label }));
  }, [base]);
  const langOptions = useMemo(() => {
    const seen = new Set(base.map((r) => r.language));
    return [...seen].sort().map((l) => ({ value: l, label: l.toUpperCase() }));
  }, [base]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return base.filter((r) => {
      if (typeKey !== "all" && r.category !== typeKey) return false;
      if (langKey !== "all" && r.language !== langKey) return false;
      if (statusKey === "passed" && !r.passed) return false;
      if (statusKey === "failed" && r.passed) return false;
      if (q && !`${r.title} ${r.case_id}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [base, search, typeKey, langKey, statusKey]);

  if (!results) {
    return (
      <EmptyState label={pick(locale, "Aucun résultat.", "Keine Ergebnisse.", "No results.")} />
    );
  }
  if (mode === "failed" && results.failed === 0) {
    return (
      <div className="flex flex-col gap-2.5">
        <TabHeader title={results.errors_title} subtitle={results.errors_subtitle} />
        <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/5 px-4 py-8 text-center text-[0.8rem] text-emerald-300">
          {results.empty_errors}
        </div>
      </div>
    );
  }

  const rowKey = (r: ResultRow) => `${r.case_id}:${r.language}`;
  const selectedRow = base.find((r) => rowKey(r) === selected) ?? null;

  const columns: Column<ResultRow>[] = [
    {
      key: "case",
      label: results.columns[0] ?? "Cas",
      width: "36%",
      sortValue: (r) => r.title,
      render: (r) => (
        <div className="flex min-w-0 flex-col">
          <span className="truncate font-medium text-[var(--tessera-text)]" title={r.title}>
            {r.title}
          </span>
          <span className="truncate font-mono text-[0.58rem] text-[var(--tessera-text-muted)]">
            {r.case_id}
          </span>
        </div>
      ),
    },
    {
      key: "type",
      label: results.columns[1] ?? "Type",
      width: "16%",
      sortValue: (r) => r.category_label,
      render: (r) => (
        <span
          className={cn(
            "rounded-full border px-2 py-0.5 text-[0.54rem] font-medium",
            TYPE_TONE[r.category_tone] ?? TYPE_TONE.tpl,
          )}
        >
          {r.category_label}
        </span>
      ),
    },
    {
      key: "lang",
      label: results.columns[2] ?? "Langue",
      width: "10%",
      sortValue: (r) => r.language,
      render: (r) => <span className="uppercase">{r.language}</span>,
    },
    {
      key: "status",
      label: results.columns[3] ?? "Statut",
      width: "14%",
      sortValue: (r) => (r.passed ? 1 : 0),
      render: (r) => (
        <span
          className={cn(
            "inline-flex items-center gap-1.5 text-[0.66rem]",
            PASS_TONE[r.status_tone],
          )}
        >
          <span className={cn("h-1.5 w-1.5 rounded-full", PASS_DOT[r.status_tone])} />
          {r.status_label}
        </span>
      ),
    },
    {
      key: "latency",
      label: results.columns[4] ?? "Latence",
      width: "12%",
      numeric: true,
      sortValue: (r) => r.duration_ms,
      render: (r) => <span className="text-[var(--tessera-text-muted)]">{r.duration_label}</span>,
    },
    {
      key: "tools",
      label: results.columns[5] ?? "Outils",
      width: "10%",
      numeric: true,
      sortValue: (r) => r.tool_count,
      render: (r) => (
        <span className={r.tool_count > 0 ? "text-sky-300" : "text-[var(--tessera-text-muted)]"}>
          {r.tool_count}
        </span>
      ),
    },
  ];

  const title = mode === "failed" ? results.errors_title : results.title;
  const subtitle = mode === "failed" ? results.errors_subtitle : results.subtitle;

  return (
    <div className="flex flex-col gap-2.5">
      <TabHeader title={title} subtitle={subtitle} />
      <div className="flex flex-wrap gap-2">
        <Stat label={pick(locale, "Total", "Gesamt", "Total")} value={String(results.total)} />
        <Stat
          label={pick(locale, "Réussis", "Bestanden", "Passed")}
          value={String(results.passed)}
          tone="text-emerald-300"
        />
        <Stat
          label={pick(locale, "Échoués", "Fehlgeschlagen", "Failed")}
          value={String(results.failed)}
          tone={results.failed > 0 ? "text-[#ff9bb0]" : undefined}
        />
        <Stat
          label={pick(locale, "Escalades", "Eskalationen", "Escalations")}
          value={String(results.escalated)}
        />
      </div>
      {mode === "failed" ? (
        <Link
          href={agentPath(agentId, "evaluations") as Route}
          className="flex items-center gap-1.5 self-start text-[0.68rem] text-[#b9a6ff] hover:text-white"
        >
          <ShieldAlert className="h-3.5 w-3.5" />
          {pick(
            locale,
            "Voir le verdict du gate et les cas critiques bloquants",
            "Gate-Urteil und blockierende kritische Faelle ansehen",
            "See the gate verdict and blocking critical cases",
          )}
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      ) : null}
      <FilterBar>
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder={pick(locale, "Rechercher un cas…", "Fall suchen…", "Search a case…")}
        />
        <FilterDropdown
          label={pick(locale, "Type", "Typ", "Type")}
          value={typeKey}
          onSelect={setTypeKey}
          options={[{ value: "all", label: pick(locale, "Tous", "Alle", "All") }, ...typeOptions]}
        />
        {mode === "all" ? (
          <FilterDropdown
            label={pick(locale, "Statut", "Status", "Status")}
            value={statusKey}
            onSelect={setStatusKey}
            options={[
              { value: "all", label: pick(locale, "Tous", "Alle", "All") },
              { value: "passed", label: pick(locale, "Réussi", "Bestanden", "Passed") },
              { value: "failed", label: pick(locale, "Échoué", "Fehlgeschlagen", "Failed") },
            ]}
          />
        ) : null}
        <FilterDropdown
          label={pick(locale, "Langue", "Sprache", "Language")}
          value={langKey}
          onSelect={setLangKey}
          options={[{ value: "all", label: pick(locale, "Toutes", "Alle", "All") }, ...langOptions]}
        />
        {(search || typeKey !== "all" || statusKey !== "all" || langKey !== "all") && (
          <ResetButton
            onClick={() => {
              setSearch("");
              setTypeKey("all");
              setStatusKey("all");
              setLangKey("all");
            }}
          />
        )}
      </FilterBar>
      <DataTable
        columns={columns}
        rows={filtered}
        rowKey={rowKey}
        noun={pick(locale, "cas", "Faelle", "cases")}
        emptyLabel={mode === "failed" ? results.empty_errors : results.empty_results}
        selectedKey={selectedRow ? rowKey(selectedRow) : null}
        onRowClick={(r) => setSelected(rowKey(r))}
        initialSortCol={3}
        initialSortDir="asc"
        minWidth="880px"
      />
      {selectedRow ? (
        <ResultDrawer row={selectedRow} labels={results.labels} onClose={() => setSelected(null)} />
      ) : null}
    </div>
  );
}

function ResultDrawer({
  row,
  labels,
  onClose,
}: {
  row: ResultRow;
  labels: NonNullable<Data["results"]>["labels"];
  onClose: () => void;
}) {
  const locale = useLocale();
  return (
    <EvalDrawer
      title={row.title}
      subtitle={`${row.case_id} · ${row.language.toUpperCase()}`}
      icon={<Beaker className="h-4 w-4 text-[#8b7cf0]" />}
      onClose={onClose}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[0.62rem] font-medium",
            row.passed
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
              : "border-[#e0566f]/50 bg-[#e0566f]/10 text-[#ff9bb0]",
          )}
        >
          <span className={cn("h-1.5 w-1.5 rounded-full", PASS_DOT[row.status_tone])} />
          {row.status_label}
        </span>
        <span
          className={cn(
            "rounded-full border px-2 py-0.5 text-[0.56rem] font-medium",
            TYPE_TONE[row.category_tone] ?? TYPE_TONE.tpl,
          )}
        >
          {row.category_label}
        </span>
        {row.escalated ? (
          <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[0.56rem] font-medium text-amber-300">
            <AlertTriangle className="h-3 w-3" /> {labels.escalated}
          </span>
        ) : null}
      </div>
      <DrawerBlock title={labels.question}>
        <p className="whitespace-pre-wrap text-[0.72rem] leading-relaxed text-[var(--tessera-text)]">
          {row.question || (
            <span className="italic text-[var(--tessera-text-muted)]">{labels.no_question}</span>
          )}
        </p>
      </DrawerBlock>
      <DrawerBlock title={labels.response}>
        <p className="whitespace-pre-wrap text-[0.72rem] leading-relaxed text-[var(--tessera-text-muted)]">
          {row.response || "-"}
        </p>
      </DrawerBlock>
      {row.reasons.length > 0 ? (
        <DrawerBlock title={labels.diagnostic}>
          <ul className="flex flex-col gap-1 text-[0.7rem]">
            {row.reasons.map((reason) => (
              <li key={reason} className="flex items-start gap-1.5">
                <span
                  className={cn(
                    "mt-[5px] h-1.5 w-1.5 shrink-0 rounded-full",
                    row.passed ? "bg-emerald-400" : "bg-[#ff9bb0]",
                  )}
                />
                <span className="text-[var(--tessera-text)]">{reason}</span>
              </li>
            ))}
          </ul>
        </DrawerBlock>
      ) : null}
      <DrawerBlock title={labels.tools}>
        {row.tools.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {row.tools.map((tool) => (
              <span
                key={tool}
                className="inline-flex items-center gap-1 rounded border border-sky-500/30 bg-sky-500/10 px-1.5 py-0.5 text-[0.6rem] font-mono text-sky-300"
              >
                <Wrench className="h-2.5 w-2.5" /> {tool}
              </span>
            ))}
          </div>
        ) : (
          <p className="text-[0.68rem] text-[var(--tessera-text-muted)]">{labels.no_tools}</p>
        )}
      </DrawerBlock>
      <div className="flex flex-col gap-1.5">
        <DrawerField label={labels.tokens}>
          {row.input_tokens} / {row.output_tokens}
        </DrawerField>
        {row.started_at ? (
          <DrawerField label={labels.started}>
            {new Date(row.started_at).toLocaleString(
              locale === "de" ? "de-DE" : locale === "en" ? "en-GB" : "fr-FR",
            )}
          </DrawerField>
        ) : null}
      </div>
    </EvalDrawer>
  );
}

// ── Comparaisons (run vs run) ────────────────────────────────────────────────

function verdict(gatePassed: boolean | null, locale: string): { label: string; tone: string } {
  if (gatePassed === null)
    return {
      label: pick(locale, "non enregistré", "nicht aufgezeichnet", "not recorded"),
      tone: "text-[var(--tessera-text-muted)]",
    };
  return gatePassed
    ? { label: pick(locale, "PASSE", "BESTANDEN", "PASS"), tone: "text-emerald-300" }
    : { label: pick(locale, "BLOQUÉ", "BLOCKIERT", "BLOCKED"), tone: "text-red-300" };
}

function RunSelect({
  value,
  items,
  onChange,
  label,
}: {
  value: number;
  items: RunItem[];
  onChange: (i: number) => void;
  label: string;
}) {
  return (
    <label className="flex flex-1 flex-col gap-1">
      <span className="text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-9 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[0.74rem] text-[var(--tessera-text)] focus:border-[#8b7cf0] focus:outline-none"
      >
        {items.map((r, i) => (
          <option key={r.run_at} value={i}>
            {r.label} · {r.eval_set || "-"} · {r.passed}/{r.total}
          </option>
        ))}
      </select>
    </label>
  );
}

export function ComparaisonsTab({ data }: { data: Data }) {
  const locale = useLocale();
  const runs = data.runs;
  const items = runs?.items ?? [];
  const [aIdx, setAIdx] = useState(0);
  const [bIdx, setBIdx] = useState(1);

  const title = pick(locale, "Comparaisons", "Vergleiche", "Comparisons");
  const subtitle = pick(
    locale,
    "Comparez deux runs d'évaluation - métriques et écarts.",
    "Zwei Evaluierungslaeufe vergleichen - Metriken und Abweichungen.",
    "Compare two evaluation runs - metrics and deltas.",
  );

  if (items.length < 2) {
    return (
      <div className="flex flex-col gap-2.5">
        <TabHeader title={title} subtitle={subtitle} />
        <EmptyState
          label={pick(
            locale,
            "Un seul run (ou aucun) - la comparaison apparaît au deuxième run.",
            "Nur ein Lauf (oder keiner) - der Vergleich erscheint mit dem zweiten Lauf.",
            "A single run (or none) - the comparison appears with the second run.",
          )}
        />
      </div>
    );
  }

  const a = items[Math.min(aIdx, items.length - 1)];
  const b = items[Math.min(bIdx, items.length - 1)];
  if (!a || !b) return null;
  const sameCatalogue = a.catalogue_version === b.catalogue_version;
  const nf = new Intl.NumberFormat(
    locale === "de" ? "de-DE" : locale === "en" ? "en-GB" : "fr-FR",
    {
      maximumFractionDigits: 1,
    },
  );
  const deltaPts = (a.pass_rate - b.pass_rate) * 100;
  const va = verdict(a.gate_passed, locale);
  const vb = verdict(b.gate_passed, locale);

  const metricRows: {
    label: string;
    a: React.ReactNode;
    b: React.ReactNode;
    delta?: React.ReactNode;
  }[] = [
    {
      label: pick(locale, "Taux de réussite", "Erfolgsrate", "Pass rate"),
      a: `${nf.format(a.pass_rate * 100)}%`,
      b: `${nf.format(b.pass_rate * 100)}%`,
      delta: (
        <span
          className={cn(
            "tabular-nums",
            deltaPts > 0
              ? "text-emerald-300"
              : deltaPts < 0
                ? "text-red-300"
                : "text-[var(--tessera-text-muted)]",
          )}
        >
          {deltaPts > 0 ? "+" : ""}
          {nf.format(deltaPts)} pt
        </span>
      ),
    },
    {
      label: pick(locale, "Cas réussis", "Bestandene Faelle", "Passed cases"),
      a: `${a.passed}/${a.total}`,
      b: `${b.passed}/${b.total}`,
    },
    {
      label: pick(locale, "Verdict gate", "Gate-Urteil", "Gate verdict"),
      a: <span className={va.tone}>{va.label}</span>,
      b: <span className={vb.tone}>{vb.label}</span>,
    },
    {
      label: pick(locale, "Version catalogue", "Katalogversion", "Catalogue version"),
      a: a.catalogue_version || "-",
      b: b.catalogue_version || "-",
    },
    {
      label: pick(locale, "Modèle", "Modell", "Model"),
      a: a.model,
      b: b.model,
    },
    {
      label: pick(locale, "Jeu", "Set", "Set"),
      a: a.eval_set || "-",
      b: b.eval_set || "-",
    },
  ];

  return (
    <div className="flex flex-col gap-2.5">
      <TabHeader title={title} subtitle={subtitle} />
      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5">
        <RunSelect
          value={aIdx}
          items={items}
          onChange={setAIdx}
          label={pick(locale, "Run A", "Lauf A", "Run A")}
        />
        <GitCompare className="mb-1.5 h-4 w-4 shrink-0 text-[var(--tessera-text-muted)]" />
        <RunSelect
          value={bIdx}
          items={items}
          onChange={setBIdx}
          label={pick(locale, "Run B", "Lauf B", "Run B")}
        />
      </div>
      {!sameCatalogue ? (
        <p className="rounded-md border border-amber-500/40 bg-amber-500/5 px-2.5 py-1.5 text-[0.68rem] text-amber-300">
          {pick(
            locale,
            "Versions de catalogue différentes - l'écart de taux compare deux examens distincts.",
            "Unterschiedliche Katalogversionen - die Ratendifferenz vergleicht zwei verschiedene Pruefungen.",
            "Different catalogue versions - the rate delta compares two distinct exams.",
          )}
        </p>
      ) : null}
      <section className="overflow-x-auto rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
        <table className="w-full min-w-[560px] border-collapse text-left text-[0.72rem]">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.56rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              <th className="px-3 py-2 font-medium">
                {pick(locale, "Métrique", "Metrik", "Metric")}
              </th>
              <th className="px-3 py-2 font-medium">A · {a.label}</th>
              <th className="px-3 py-2 font-medium">B · {b.label}</th>
              <th className="px-3 py-2 text-right font-medium">Δ</th>
            </tr>
          </thead>
          <tbody>
            {metricRows.map((m) => (
              <tr
                key={m.label}
                className="border-b border-[var(--tessera-border)]/60 last:border-0"
              >
                <td className="px-3 py-2 text-[var(--tessera-text-muted)]">{m.label}</td>
                <td className="px-3 py-2 font-medium text-[var(--tessera-text)]">{m.a}</td>
                <td className="px-3 py-2 font-medium text-[var(--tessera-text)]">{m.b}</td>
                <td className="px-3 py-2 text-right">
                  {m.delta ?? <span className="text-[var(--tessera-text-muted)]">-</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

// ── Versions & historique ────────────────────────────────────────────────────

export function VersionsTab({ data }: { data: Data }) {
  const locale = useLocale();
  const runs = data.runs;
  const items = runs?.items ?? [];
  const [selected, setSelected] = useState<string | null>(null);

  const title = pick(locale, "Versions & historique", "Versionen & Verlauf", "Versions & history");
  if (!runs || items.length === 0) {
    return (
      <div className="flex flex-col gap-2.5">
        <TabHeader title={title} subtitle={runs?.subtitle} />
        <EmptyState
          label={runs?.empty_label ?? pick(locale, "Aucun run.", "Keine Laeufe.", "No runs.")}
        />
      </div>
    );
  }

  const selectedRow = items.find((r) => r.run_at === selected) ?? null;
  const nf = new Intl.NumberFormat(
    locale === "de" ? "de-DE" : locale === "en" ? "en-GB" : "fr-FR",
    {
      maximumFractionDigits: 1,
    },
  );
  const columns: Column<RunItem>[] = [
    {
      key: "date",
      label: pick(locale, "Date", "Datum", "Date"),
      width: "16%",
      sortValue: (r) => r.run_at,
      render: (r) => (
        <div className="flex items-center gap-2">
          <History className="h-3.5 w-3.5 shrink-0 text-[#8b7cf0]" />
          <span className="font-medium text-[var(--tessera-text)]">{r.label}</span>
        </div>
      ),
    },
    {
      key: "set",
      label: pick(locale, "Jeu", "Set", "Set"),
      width: "16%",
      sortValue: (r) => r.eval_set,
      render: (r) => <span className="text-[var(--tessera-text-muted)]">{r.eval_set || "-"}</span>,
    },
    {
      key: "catalogue",
      label: pick(locale, "Catalogue", "Katalog", "Catalogue"),
      width: "16%",
      sortValue: (r) => r.catalogue_version,
      render: (r) => (
        <span className="font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
          {r.catalogue_version || "-"}
        </span>
      ),
    },
    {
      key: "model",
      label: pick(locale, "Modèle", "Modell", "Model"),
      width: "16%",
      sortValue: (r) => r.model,
      render: (r) => <span className="text-[var(--tessera-text-muted)]">{r.model}</span>,
    },
    {
      key: "rate",
      label: pick(locale, "Réussite", "Erfolg", "Pass rate"),
      width: "14%",
      numeric: true,
      sortValue: (r) => r.pass_rate,
      render: (r) => (
        <span className="text-[var(--tessera-text)]">
          {r.total > 0 ? `${r.passed}/${r.total} (${nf.format(r.pass_rate * 100)}%)` : "-"}
        </span>
      ),
    },
    {
      key: "verdict",
      label: pick(locale, "Verdict", "Urteil", "Verdict"),
      width: "12%",
      sortValue: (r) => String(r.gate_passed),
      render: (r) => {
        const v = verdict(r.gate_passed, locale);
        return <span className={cn("font-semibold", v.tone)}>{v.label}</span>;
      },
    },
    {
      key: "delta",
      label: "Δ",
      width: "10%",
      numeric: true,
      sortValue: (r) => r.delta_pass_rate ?? -999,
      render: (r) =>
        r.delta_pass_rate === null ? (
          <span className="text-[var(--tessera-text-muted)]">-</span>
        ) : (
          <span
            className={cn(
              r.delta_pass_rate > 0
                ? "text-emerald-300"
                : r.delta_pass_rate < 0
                  ? "text-red-300"
                  : "text-[var(--tessera-text-muted)]",
            )}
          >
            {r.delta_pass_rate > 0 ? "+" : ""}
            {nf.format(r.delta_pass_rate * 100)}
          </span>
        ),
    },
  ];

  return (
    <div className="flex flex-col gap-2.5">
      <TabHeader title={title} subtitle={runs.subtitle} />
      <DataTable
        columns={columns}
        rows={items}
        rowKey={(r) => r.run_at}
        noun={pick(locale, "runs", "Laeufe", "runs")}
        emptyLabel={runs.empty_label}
        selectedKey={selectedRow?.run_at ?? null}
        onRowClick={(r) => setSelected(r.run_at)}
        initialSortCol={0}
        initialSortDir="desc"
        minWidth="860px"
      />
      {selectedRow ? <VersionDrawer row={selectedRow} onClose={() => setSelected(null)} /> : null}
    </div>
  );
}

function VersionDrawer({ row, onClose }: { row: RunItem; onClose: () => void }) {
  const locale = useLocale();
  const agentId = useAgentId();
  const v = verdict(row.gate_passed, locale);
  const nf = new Intl.NumberFormat(
    locale === "de" ? "de-DE" : locale === "en" ? "en-GB" : "fr-FR",
    {
      maximumFractionDigits: 1,
    },
  );
  return (
    <EvalDrawer
      title={`${pick(locale, "Run du", "Lauf vom", "Run of")} ${row.label}`}
      subtitle={row.eval_set || undefined}
      icon={<History className="h-4 w-4 text-[#8b7cf0]" />}
      onClose={onClose}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={cn("rounded-full border px-2 py-0.5 text-[0.62rem] font-semibold", v.tone)}
        >
          {pick(locale, "Gate :", "Gate:", "Gate:")} {v.label}
        </span>
      </div>
      <DrawerBlock title={pick(locale, "Résultat", "Ergebnis", "Result")}>
        <div className="flex flex-col gap-1.5">
          <DrawerField label={pick(locale, "Cas réussis", "Bestandene Faelle", "Passed cases")}>
            {row.total > 0
              ? `${row.passed}/${row.total} (${nf.format(row.pass_rate * 100)}%)`
              : "-"}
          </DrawerField>
          <DrawerField label={pick(locale, "Score", "Score", "Score")}>
            {row.score} / 10
          </DrawerField>
          {row.delta_pass_rate !== null ? (
            <DrawerField
              label={pick(locale, "Δ vs run précédent", "Δ ggue. Vorlauf", "Δ vs previous run")}
            >
              {row.delta_pass_rate > 0 ? "+" : ""}
              {nf.format(row.delta_pass_rate * 100)} pt
            </DrawerField>
          ) : null}
        </div>
      </DrawerBlock>
      <DrawerBlock title={pick(locale, "Provenance", "Herkunft", "Provenance")}>
        <div className="flex flex-col gap-1.5">
          <DrawerField label={pick(locale, "Jeu", "Set", "Set")}>{row.eval_set || "-"}</DrawerField>
          <DrawerField
            label={pick(locale, "Version catalogue", "Katalogversion", "Catalogue version")}
          >
            {row.catalogue_version || "-"}
          </DrawerField>
          <DrawerField label={pick(locale, "Modèle", "Modell", "Model")}>{row.model}</DrawerField>
          <DrawerField label={pick(locale, "Horodatage", "Zeitstempel", "Timestamp")}>
            {row.run_at}
          </DrawerField>
        </div>
      </DrawerBlock>
      <Link
        href={`${agentPath(agentId, "evaluations")}?run=${encodeURIComponent(row.run_at)}` as Route}
        className="flex items-center gap-1.5 self-start text-[0.7rem] text-[#b9a6ff] hover:text-white"
      >
        {pick(
          locale,
          "Ouvrir ce run dans la vue d'ensemble",
          "Diesen Lauf in der Uebersicht oeffnen",
          "Open this run in the overview",
        )}
        <ArrowRight className="h-3.5 w-3.5" />
      </Link>
    </EvalDrawer>
  );
}

// ── Exports ──────────────────────────────────────────────────────────────────

export function ExportsTab({ data }: { data: Data }) {
  const locale = useLocale();
  const agentId = useAgentId();
  const stamp = data.gate?.candidate || data.meta?.model || "run";
  const base = `tessera-${agentId}-${stamp}`;

  const cards: {
    key: string;
    icon: React.ReactNode;
    title: string;
    desc: string;
    format: string;
    available: boolean;
    onExport: () => void;
  }[] = [
    {
      key: "results",
      icon: <ListChecks className="h-5 w-5 text-emerald-300" />,
      title: pick(locale, "Résultats du run", "Ergebnisse des Laufs", "Run results"),
      desc: pick(
        locale,
        "Chaque cas exécuté : statut, latence, outils, jetons.",
        "Jeder ausgefuehrte Fall: Status, Latenz, Tools, Tokens.",
        "Every executed case: status, latency, tools, tokens.",
      ),
      format: "CSV",
      available: Boolean(data.results?.rows.length),
      onExport: () => {
        const rows = (data.results?.rows ?? []).map((r) => [
          r.case_id,
          r.language,
          r.category,
          r.passed,
          r.duration_ms,
          r.tool_count,
          r.input_tokens,
          r.output_tokens,
        ]);
        downloadBlob(
          `${base}-resultats.csv`,
          "text/csv",
          toCsv(
            [
              "case_id",
              "language",
              "category",
              "passed",
              "duration_ms",
              "tools",
              "in_tokens",
              "out_tokens",
            ],
            rows,
          ),
        );
      },
    },
    {
      key: "dimensions",
      icon: <Table2 className="h-5 w-5 text-sky-300" />,
      title: pick(locale, "Dimensions", "Dimensionen", "Dimensions"),
      desc: pick(
        locale,
        "Taux de réussite par catégorie du catalogue.",
        "Erfolgsrate je Katalogkategorie.",
        "Pass rate per catalogue category.",
      ),
      format: "CSV",
      available: Boolean(data.table?.rows.length),
      onExport: () => {
        const rows = (data.table?.rows ?? []).map((r) => [
          r.category_key,
          r.name,
          r.passed,
          r.total,
          r.failed,
          Math.round(r.pass_rate * 100),
        ]);
        downloadBlob(
          `${base}-dimensions.csv`,
          "text/csv",
          toCsv(["category", "label", "passed", "total", "failed", "pass_rate_pct"], rows),
        );
      },
    },
    {
      key: "runs",
      icon: <History className="h-5 w-5 text-violet-300" />,
      title: pick(locale, "Historique des runs", "Lauf-Verlauf", "Run history"),
      desc: pick(
        locale,
        "Chaque run : date, verdict, taux, version de catalogue.",
        "Jeder Lauf: Datum, Urteil, Rate, Katalogversion.",
        "Each run: date, verdict, rate, catalogue version.",
      ),
      format: "CSV",
      available: Boolean(data.runs?.items.length),
      onExport: () => {
        const rows = (data.runs?.items ?? []).map((r) => [
          r.run_at,
          r.eval_set,
          r.catalogue_version,
          r.model,
          r.passed,
          r.total,
          Math.round(r.pass_rate * 100),
          r.gate_passed === null ? "" : r.gate_passed,
        ]);
        downloadBlob(
          `${base}-runs.csv`,
          "text/csv",
          toCsv(
            [
              "run_at",
              "eval_set",
              "catalogue_version",
              "model",
              "passed",
              "total",
              "pass_rate_pct",
              "gate_passed",
            ],
            rows,
          ),
        );
      },
    },
    {
      key: "sets",
      icon: <Boxes className="h-5 w-5 text-amber-300" />,
      title: pick(locale, "Jeux d'évaluations", "Evaluierungssets", "Evaluation sets"),
      desc: pick(
        locale,
        "Les jeux curés et leur composition.",
        "Die kuratierten Sets und ihre Zusammensetzung.",
        "The curated sets and their composition.",
      ),
      format: "JSON",
      available: Boolean(data.sets?.rows.length),
      onExport: () => {
        downloadBlob(
          `${base}-jeux.json`,
          "application/json",
          JSON.stringify(data.sets?.rows ?? [], null, 2),
        );
      },
    },
    {
      key: "gate",
      icon: <FileJson className="h-5 w-5 text-[#ff9bb0]" />,
      title: pick(locale, "Rapport de gate", "Gate-Bericht", "Gate report"),
      desc: pick(
        locale,
        "Le verdict de release et les cas critiques.",
        "Das Release-Urteil und die kritischen Faelle.",
        "The release verdict and the critical cases.",
      ),
      format: "JSON",
      available: Boolean(data.gate),
      onExport: () => {
        downloadBlob(
          `${base}-gate.json`,
          "application/json",
          JSON.stringify(data.gate ?? {}, null, 2),
        );
      },
    },
  ];

  const active = cards.filter((c) => c.available);

  return (
    <div className="flex flex-col gap-2.5">
      <TabHeader
        title={pick(locale, "Exports", "Exporte", "Exports")}
        subtitle={pick(
          locale,
          "Téléchargez les données de ce run - fichiers générés côté navigateur.",
          "Laden Sie die Daten dieses Laufs herunter - im Browser erzeugte Dateien.",
          "Download this run's data - files generated in the browser.",
        )}
      />
      {active.length === 0 ? (
        <EmptyState
          label={pick(
            locale,
            "Rien à exporter - éval non exécutée.",
            "Nichts zu exportieren - Evaluierung nicht ausgefuehrt.",
            "Nothing to export - eval not executed.",
          )}
        />
      ) : (
        <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
          {active.map((c) => (
            <div
              key={c.key}
              className="flex flex-col gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3.5"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="flex h-9 w-9 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)]">
                  {c.icon}
                </span>
                <span className="rounded border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 py-0.5 text-[0.54rem] font-medium uppercase tracking-wide text-[var(--tessera-text-muted)]">
                  {c.format}
                </span>
              </div>
              <div className="flex min-h-[54px] flex-col gap-0.5">
                <h3 className="text-[0.82rem] font-semibold text-[var(--tessera-text)]">
                  {c.title}
                </h3>
                <p className="text-[0.68rem] leading-snug text-[var(--tessera-text-muted)]">
                  {c.desc}
                </p>
              </div>
              <button
                type="button"
                onClick={c.onExport}
                className="flex items-center justify-center gap-1.5 rounded-md border border-[#7c5cf5] bg-[#6d4aed] px-3 py-1.5 text-[0.72rem] font-medium text-white hover:bg-[#7c5cf5]"
              >
                <Download className="h-3.5 w-3.5" />{" "}
                {pick(locale, "Télécharger", "Herunterladen", "Download")}
              </button>
            </div>
          ))}
        </div>
      )}
      <p className="flex items-center gap-1.5 text-[0.66rem] text-[var(--tessera-text-muted)]">
        <FileText className="h-3.5 w-3.5" />
        {pick(
          locale,
          "Les exports reflètent le run actif ; aucune donnée ne quitte le navigateur.",
          "Die Exporte spiegeln den aktiven Lauf wider; keine Daten verlassen den Browser.",
          "Exports reflect the active run; no data leaves the browser.",
        )}
      </p>
    </div>
  );
}
