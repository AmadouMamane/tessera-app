"use client";

/**
 * The AGENT / Historique sub-tab views beyond Vue d'ensemble and Sessions:
 * Messages (per-session exchanges + the real transcript conversations),
 * Evaluations (per-session eval outcomes), Traces & outils (real tool-call
 * counts — per-call traces are honestly declared not captured), Utilisateurs
 * (the real single eval operator, no fabricated end-users), Contenu & sources
 * (honest empty state — no source data rides on this payload), Erreurs (failed
 * sessions) and Exports (browser-generated files). Every number comes from the
 * payload the page already receives; nothing is invented client-side.
 */

import {
  AlertTriangle,
  ArrowRight,
  BadgeCheck,
  Download,
  FileJson,
  FileText,
  FolderSearch,
  MessagesSquare,
  Table2,
  UserRound,
  Wrench,
} from "lucide-react";
import type { Route } from "next";
import { useLocale } from "next-intl";
import { useMemo, useState } from "react";

import { Truncate } from "@/components/ui/truncate";
import { Link } from "@/i18n/navigation";
import { agentPath } from "@/lib/agent-context";
import type { AgentHistorique as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import { useAgentId } from "@/lib/use-agent-id";
import {
  type Column,
  DataTable,
  EvalDrawer,
  FilterBar,
  FilterDropdown,
  ResetButton,
  SearchInput,
  downloadBlob,
  pick,
  toCsv,
} from "./agent-subtab-shared";

type Row = NonNullable<Data["table"]>["rows"][number];

const STATUS_PILL: Record<string, string> = {
  good: "border-emerald-500/30 bg-emerald-500/15 text-[var(--tessera-fg-success)]",
  info: "border-sky-500/30 bg-sky-500/15 text-[var(--tessera-fg-info)]",
  warn: "border-amber-500/30 bg-amber-500/15 text-[var(--tessera-fg-warning)]",
  bad: "border-red-500/30 bg-red-500/15 text-[var(--tessera-fg-danger)]",
  crit: "border-red-500/30 bg-red-500/15 text-[var(--tessera-fg-danger)]",
};
const SCORE_TEXT: Record<string, string> = {
  good: "text-[var(--tessera-fg-success)]",
  warn: "text-[var(--tessera-fg-warning)]",
  crit: "text-[var(--tessera-fg-danger)]",
};

function EmptyState({ label }: { label: string }) {
  return (
    <div className="rounded-lg border border-dashed border-[var(--tessera-border)] px-4 py-10 text-center text-[0.8rem] text-[var(--tessera-text-muted)]">
      {label}
    </div>
  );
}

function TabHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <h2 className="text-[0.95rem] font-semibold text-[var(--tessera-text)]">{title}</h2>
      <p className="text-[0.72rem] text-[var(--tessera-text-muted)]">{subtitle}</p>
    </div>
  );
}

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

function HonestNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 py-2 text-[0.68rem] leading-relaxed text-[var(--tessera-text-muted)]">
      {children}
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

function DrawerText({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5">
      <h3 className="mb-1.5 text-[0.62rem] font-semibold uppercase tracking-wide text-[var(--tessera-text-muted)]">
        {title}
      </h3>
      <p className="whitespace-pre-wrap text-[0.7rem] leading-relaxed text-[var(--tessera-text)]">
        {text}
      </p>
    </div>
  );
}

/** The columns every session-flavored table shares (session id, case, category). */
function identityColumns(locale: string): Column<Row>[] {
  return [
    {
      key: "sid",
      label: "Session",
      width: "14%",
      sortValue: (r) => r.sid,
      render: (r) => (
        <span className="font-mono text-[0.64rem] text-[var(--tessera-text)]">{r.sid}</span>
      ),
    },
    {
      key: "case",
      label: pick(locale, "Cas", "Fall", "Case"),
      width: "20%",
      sortValue: (r) => r.case_id,
      render: (r) => (
        <Truncate
          full={r.case_id}
          className="font-mono text-[0.62rem] text-[var(--tessera-text-muted)]"
        >
          {r.case_id}
        </Truncate>
      ),
    },
    {
      key: "category",
      label: pick(locale, "Catégorie", "Kategorie", "Category"),
      width: "16%",
      sortValue: (r) => r.category_label,
      render: (r) => (
        <Truncate full={r.category_label} className="text-[0.68rem] text-[var(--tessera-text)]">
          {r.category_label}
        </Truncate>
      ),
    },
  ];
}

function statusColumn(locale: string): Column<Row> {
  return {
    key: "status",
    label: pick(locale, "Statut", "Status", "Status"),
    width: "12%",
    sortValue: (r) => r.status,
    render: (r) => (
      <span
        className={cn(
          "rounded-full border px-2 py-0.5 text-[0.58rem] font-medium",
          STATUS_PILL[r.status_tone] ?? STATUS_PILL.info,
        )}
      >
        {r.status}
      </span>
    ),
  };
}

// ── Messages ─────────────────────────────────────────────────────────────────

export function MessagesTab({ data }: { data: Data }) {
  const locale = useLocale();
  const [search, setSearch] = useState("");
  const [langKey, setLangKey] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);
  const rows = data.table?.rows ?? [];
  const labels = data.detail_labels;

  const langOptions = data.filters?.options.lang ?? [];
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((r) => {
      if (langKey !== "all" && r.lang !== langKey) return false;
      if (q && !`${r.sid} ${r.case_id} ${r.question} ${r.response}`.toLowerCase().includes(q))
        return false;
      return true;
    });
  }, [rows, search, langKey]);

  const title = pick(locale, "Messages", "Nachrichten", "Messages");
  const subtitle = pick(
    locale,
    "Chaque échange évalué — la requête du client et la réponse du modèle, tels qu'exécutés.",
    "Jeder evaluierte Austausch — Kundenanfrage und Modellantwort, wie ausgeführt.",
    "Each evaluated exchange — the customer request and the model response, as executed.",
  );

  if (rows.length === 0) {
    return (
      <div className="flex flex-col gap-2.5">
        <TabHeader title={title} subtitle={subtitle} />
        <EmptyState label={pick(locale, "Aucun échange.", "Keine Austausche.", "No exchanges.")} />
      </div>
    );
  }

  const selectedRow = rows.find((r) => r.sid === selected) ?? null;
  const questionLabel = labels?.question_label ?? pick(locale, "Question", "Frage", "Question");
  const responseLabel = labels?.response_label ?? pick(locale, "Réponse", "Antwort", "Response");
  const columns: Column<Row>[] = [
    ...identityColumns(locale),
    {
      key: "lang",
      label: pick(locale, "Langue", "Sprache", "Language"),
      width: "8%",
      sortValue: (r) => r.lang,
      render: (r) => (
        <span className="font-mono text-[0.62rem] uppercase text-[var(--tessera-text-muted)]">
          {r.lang}
        </span>
      ),
    },
    {
      key: "question",
      label: questionLabel,
      width: "28%",
      sortable: false,
      render: (r) => (
        <Truncate full={r.question} className="text-[0.68rem] text-[var(--tessera-text-muted)]">
          {r.question}
        </Truncate>
      ),
    },
    {
      key: "start",
      label: pick(locale, "Date", "Datum", "Date"),
      width: "14%",
      sortValue: (r) => r.start_ts,
      render: (r) => (
        <span className="whitespace-nowrap text-[0.66rem] tabular-nums text-[var(--tessera-text-muted)]">
          {r.start}
        </span>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-2.5">
      <TabHeader title={title} subtitle={subtitle} />
      <FilterBar>
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder={pick(
            locale,
            "Rechercher un échange…",
            "Austausch suchen…",
            "Search an exchange…",
          )}
        />
        <FilterDropdown
          label={pick(locale, "Langue", "Sprache", "Language")}
          value={langKey}
          options={langOptions.map((o) => ({ value: o.key, label: o.label }))}
          onSelect={setLangKey}
        />
        {search || langKey !== "all" ? (
          <ResetButton
            onClick={() => {
              setSearch("");
              setLangKey("all");
            }}
          />
        ) : null}
      </FilterBar>
      <DataTable
        columns={columns}
        rows={filtered}
        rowKey={(r) => r.sid}
        noun={pick(locale, "échanges", "Austausche", "exchanges")}
        emptyLabel={pick(locale, "Aucun échange.", "Keine Austausche.", "No exchanges.")}
        selectedKey={selectedRow?.sid ?? null}
        onRowClick={(r) => setSelected(r.sid)}
        initialSortCol={5}
        initialSortDir="desc"
        minWidth="760px"
      />
      {selectedRow ? (
        <EvalDrawer
          title={selectedRow.case_id}
          subtitle={`${selectedRow.sid} · ${selectedRow.start}`}
          icon={<MessagesSquare className="h-4 w-4 text-[var(--tessera-fg-info)]" />}
          onClose={() => setSelected(null)}
        >
          <DrawerText title={questionLabel} text={selectedRow.question} />
          <DrawerText title={responseLabel} text={selectedRow.response} />
          <div className="flex flex-col gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5">
            <DrawerField label={pick(locale, "Statut", "Status", "Status")}>
              {selectedRow.status}
            </DrawerField>
            <DrawerField label={pick(locale, "Langue", "Sprache", "Language")}>
              {selectedRow.lang.toUpperCase()}
            </DrawerField>
            <DrawerField label={pick(locale, "Latence", "Latenz", "Latency")}>
              {selectedRow.latency}
            </DrawerField>
          </div>
        </EvalDrawer>
      ) : null}
    </div>
  );
}

// ── Evaluations ──────────────────────────────────────────────────────────────

export function EvaluationsTab({ data }: { data: Data }) {
  const locale = useLocale();
  const agentId = useAgentId();
  const [statusKey, setStatusKey] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);
  const rows = data.table?.rows ?? [];

  const filtered = useMemo(
    () => rows.filter((r) => statusKey === "all" || r.status_tone === statusKey),
    [rows, statusKey],
  );
  const passed = rows.filter((r) => r.passed).length;
  const escalations = rows.filter((r) => r.escalation).length;

  const title = pick(locale, "Evaluations", "Evaluierungen", "Evaluations");
  const subtitle = pick(
    locale,
    "Le verdict d'évaluation de chaque session — score, statut, escalade, outils, jetons.",
    "Das Evaluierungsurteil jeder Session — Score, Status, Eskalation, Tools, Tokens.",
    "Each session's evaluation verdict — score, status, escalation, tools, tokens.",
  );

  if (rows.length === 0) {
    return (
      <div className="flex flex-col gap-2.5">
        <TabHeader title={title} subtitle={subtitle} />
        <EmptyState
          label={pick(locale, "Aucune évaluation.", "Keine Evaluierungen.", "No evaluations.")}
        />
      </div>
    );
  }

  const statusOptions = data.filters?.options.status ?? [];
  const selectedRow = rows.find((r) => r.sid === selected) ?? null;
  const columns: Column<Row>[] = [
    ...identityColumns(locale),
    {
      key: "score",
      label: "Score",
      width: "9%",
      numeric: true,
      sortValue: (r) => r.score_num,
      render: (r) => (
        <span className={cn("tabular-nums", SCORE_TEXT[r.score_tone] ?? "")}>{r.score}</span>
      ),
    },
    statusColumn(locale),
    {
      key: "escalation",
      label: pick(locale, "Escalade", "Eskalation", "Escalation"),
      width: "10%",
      sortValue: (r) => (r.escalation ? 1 : 0),
      render: (r) =>
        r.escalation ? (
          <span className="text-[0.66rem] text-[var(--tessera-fg-warning)]">
            {pick(locale, "oui", "ja", "yes")}
          </span>
        ) : (
          <span className="text-[0.66rem] text-[var(--tessera-text-muted)]">
            {pick(locale, "non", "nein", "no")}
          </span>
        ),
    },
    {
      key: "tools",
      label: pick(locale, "Outils", "Tools", "Tools"),
      width: "8%",
      numeric: true,
      sortValue: (r) => r.tools_count,
      render: (r) => r.tools_count,
    },
    {
      key: "tokens",
      label: "Tokens",
      width: "11%",
      numeric: true,
      sortValue: (r) => r.tokens_num,
      render: (r) => <span className="tabular-nums">{r.tokens}</span>,
    },
  ];

  return (
    <div className="flex flex-col gap-2.5">
      <TabHeader title={title} subtitle={subtitle} />
      <div className="flex flex-wrap gap-2">
        <Stat
          label={pick(locale, "Réussies", "Bestanden", "Passed")}
          value={`${passed}/${rows.length}`}
          tone="text-[var(--tessera-fg-success)]"
        />
        <Stat
          label={pick(locale, "Échouées", "Fehlgeschlagen", "Failed")}
          value={String(rows.length - passed)}
          tone={rows.length - passed > 0 ? "text-[var(--tessera-fg-danger)]" : undefined}
        />
        <Stat
          label={pick(locale, "Escalades", "Eskalationen", "Escalations")}
          value={String(escalations)}
          tone={escalations > 0 ? "text-[var(--tessera-fg-warning)]" : undefined}
        />
      </div>
      <FilterBar>
        <FilterDropdown
          label={pick(locale, "Statut", "Status", "Status")}
          value={statusKey}
          options={statusOptions.map((o) => ({ value: o.key, label: o.label }))}
          onSelect={setStatusKey}
        />
        {statusKey !== "all" ? <ResetButton onClick={() => setStatusKey("all")} /> : null}
      </FilterBar>
      <DataTable
        columns={columns}
        rows={filtered}
        rowKey={(r) => r.sid}
        noun={pick(locale, "évaluations", "Evaluierungen", "evaluations")}
        emptyLabel={pick(locale, "Aucune évaluation.", "Keine Evaluierungen.", "No evaluations.")}
        selectedKey={selectedRow?.sid ?? null}
        onRowClick={(r) => setSelected(r.sid)}
        initialSortCol={3}
        initialSortDir="asc"
        minWidth="820px"
      />
      <Link
        href={agentPath(agentId, "evaluations") as Route}
        className="flex items-center gap-1.5 self-start text-[0.7rem] text-[var(--tessera-fg-accent)] hover:text-[var(--tessera-text-strong)]"
      >
        {pick(
          locale,
          "Ouvrir la page Évaluations de l'agent",
          "Die Evaluierungsseite des Agenten öffnen",
          "Open the agent's Evaluations page",
        )}
        <ArrowRight className="h-3.5 w-3.5" />
      </Link>
      {selectedRow ? (
        <EvalDrawer
          title={selectedRow.case_id}
          subtitle={`${selectedRow.sid} · ${selectedRow.start}`}
          icon={<BadgeCheck className="h-4 w-4 text-[var(--tessera-fg-info)]" />}
          onClose={() => setSelected(null)}
        >
          <div className="flex flex-col gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5">
            <DrawerField label="Score">{selectedRow.score}</DrawerField>
            <DrawerField label={pick(locale, "Statut", "Status", "Status")}>
              {selectedRow.status}
            </DrawerField>
            <DrawerField label={pick(locale, "Escalade", "Eskalation", "Escalation")}>
              {selectedRow.escalation
                ? pick(locale, "oui", "ja", "yes")
                : pick(locale, "non", "nein", "no")}
            </DrawerField>
            <DrawerField
              label={pick(locale, "Outils invoqués", "Aufgerufene Tools", "Tools invoked")}
            >
              {selectedRow.tools_count}
            </DrawerField>
            <DrawerField label={pick(locale, "Latence", "Latenz", "Latency")}>
              {selectedRow.latency}
            </DrawerField>
            <DrawerField
              label={pick(
                locale,
                "Jetons (entrée / sortie)",
                "Tokens (Ein-/Ausgabe)",
                "Tokens (in / out)",
              )}
            >
              {`${selectedRow.input_tokens} / ${selectedRow.output_tokens}`}
            </DrawerField>
          </div>
          <DrawerText
            title={
              data.detail_labels?.question_label ?? pick(locale, "Question", "Frage", "Question")
            }
            text={selectedRow.question}
          />
        </EvalDrawer>
      ) : null}
    </div>
  );
}

// ── Traces & outils ──────────────────────────────────────────────────────────

export function TracesTab({ data }: { data: Data }) {
  const locale = useLocale();
  const rows = data.table?.rows ?? [];
  const withTools = rows.filter((r) => r.tools_count > 0);
  const totalCalls = rows.reduce((acc, r) => acc + r.tools_count, 0);

  const title = pick(locale, "Traces & outils", "Traces & Tools", "Traces & tools");
  const subtitle = pick(
    locale,
    "L'usage des outils par session, tel que mesuré par le harnais d'évaluation.",
    "Die Tool-Nutzung je Session, wie vom Evaluierungs-Harness gemessen.",
    "Tool usage per session, as measured by the evaluation harness.",
  );

  const columns: Column<Row>[] = [
    ...identityColumns(locale),
    {
      key: "tools",
      label: pick(locale, "Outils invoqués", "Aufgerufene Tools", "Tools invoked"),
      width: "12%",
      numeric: true,
      sortValue: (r) => r.tools_count,
      render: (r) =>
        r.tools_count > 0 ? (
          <span className="inline-flex items-center gap-1.5 tabular-nums text-[var(--tessera-text)]">
            <Wrench className="h-3 w-3 text-[var(--tessera-fg-info)]" />
            {r.tools_count}
          </span>
        ) : (
          <span className="tabular-nums text-[var(--tessera-text-muted)]">0</span>
        ),
    },
    {
      key: "latency",
      label: pick(locale, "Latence", "Latenz", "Latency"),
      width: "11%",
      numeric: true,
      sortValue: (r) => r.latency_ms,
      render: (r) => <span className="tabular-nums">{r.latency}</span>,
    },
    {
      key: "tokens_in",
      label: pick(locale, "Jetons entrée", "Tokens Eingabe", "Tokens in"),
      width: "11%",
      numeric: true,
      sortValue: (r) => r.input_tokens,
      render: (r) => <span className="tabular-nums">{r.input_tokens}</span>,
    },
    {
      key: "tokens_out",
      label: pick(locale, "Jetons sortie", "Tokens Ausgabe", "Tokens out"),
      width: "11%",
      numeric: true,
      sortValue: (r) => r.output_tokens,
      render: (r) => <span className="tabular-nums">{r.output_tokens}</span>,
    },
  ];

  return (
    <div className="flex flex-col gap-2.5">
      <TabHeader title={title} subtitle={subtitle} />
      <HonestNote>
        {pick(
          locale,
          "Les traces pas-à-pas des appels d'outils ne sont pas capturées pour les runs d'évaluation — seul le nombre d'appels par session l'est. Ce tableau montre exactement ce qui est mesuré, rien de plus.",
          "Schritt-für-Schritt-Traces der Tool-Aufrufe werden für Evaluierungsläufe nicht erfasst — nur die Anzahl der Aufrufe je Session. Diese Tabelle zeigt genau das Gemessene, nicht mehr.",
          "Step-by-step tool-call traces are not captured for evaluation runs — only the number of calls per session is. This table shows exactly what is measured, nothing more.",
        )}
      </HonestNote>
      {rows.length === 0 ? (
        <EmptyState label={pick(locale, "Aucune session.", "Keine Sessions.", "No sessions.")} />
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            <Stat
              label={pick(
                locale,
                "Sessions avec outils",
                "Sessions mit Tools",
                "Sessions with tools",
              )}
              value={`${withTools.length}/${rows.length}`}
            />
            <Stat
              label={pick(locale, "Appels d'outils", "Tool-Aufrufe", "Tool calls")}
              value={String(totalCalls)}
            />
          </div>
          <DataTable
            columns={columns}
            rows={rows}
            rowKey={(r) => r.sid}
            noun={pick(locale, "sessions", "Sessions", "sessions")}
            emptyLabel={pick(locale, "Aucune session.", "Keine Sessions.", "No sessions.")}
            initialSortCol={3}
            initialSortDir="desc"
            minWidth="820px"
          />
        </>
      )}
    </div>
  );
}

// ── Utilisateurs ─────────────────────────────────────────────────────────────

export function UsersTab({ data }: { data: Data }) {
  const locale = useLocale();
  const rows = data.table?.rows ?? [];
  const convos = data.live_conversations ?? [];

  // Real aggregation: every eval session names its operator (`user`). Today that
  // is the harness operator for every row — the table says so instead of
  // inventing end-user identities that the payload does not carry.
  const operators = useMemo(() => {
    const agg = new Map<string, Row[]>();
    for (const r of rows) {
      const list = agg.get(r.user) ?? [];
      list.push(r);
      agg.set(r.user, list);
    }
    return [...agg.entries()].map(([user, sessions]) => ({
      user,
      count: sessions.length,
      passed: sessions.filter((s) => s.passed).length,
      first: sessions.reduce(
        (a, s) => (s.start_ts < a ? s.start_ts : a),
        sessions[0]?.start_ts ?? "",
      ),
      last: sessions.reduce(
        (a, s) => (s.start_ts > a ? s.start_ts : a),
        sessions[0]?.start_ts ?? "",
      ),
    }));
  }, [rows]);

  type OpRow = (typeof operators)[number];
  const columns: Column<OpRow>[] = [
    {
      key: "user",
      label: pick(locale, "Opérateur", "Operator", "Operator"),
      width: "30%",
      sortValue: (r) => r.user,
      render: (r) => (
        <div className="flex min-w-0 items-center gap-2">
          <UserRound className="h-4 w-4 shrink-0 text-[var(--tessera-fg-info)]" />
          <Truncate full={r.user} className="font-medium text-[var(--tessera-text)]">
            {r.user}
          </Truncate>
        </div>
      ),
    },
    {
      key: "sessions",
      label: "Sessions",
      width: "16%",
      numeric: true,
      sortValue: (r) => r.count,
      render: (r) => r.count,
    },
    {
      key: "passed",
      label: pick(locale, "Réussies", "Bestanden", "Passed"),
      width: "16%",
      numeric: true,
      sortValue: (r) => r.passed,
      render: (r) => (
        <span className="tabular-nums">
          {r.passed}/{r.count}
        </span>
      ),
    },
    {
      key: "first",
      label: pick(locale, "Première session", "Erste Session", "First session"),
      width: "19%",
      sortValue: (r) => r.first,
      render: (r) => (
        <span className="text-[0.66rem] tabular-nums text-[var(--tessera-text-muted)]">
          {r.first.slice(0, 10)}
        </span>
      ),
    },
    {
      key: "last",
      label: pick(locale, "Dernière session", "Letzte Session", "Last session"),
      width: "19%",
      sortValue: (r) => r.last,
      render: (r) => (
        <span className="text-[0.66rem] tabular-nums text-[var(--tessera-text-muted)]">
          {r.last.slice(0, 10)}
        </span>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-2.5">
      <TabHeader
        title={pick(locale, "Utilisateurs", "Benutzer", "Users")}
        subtitle={pick(
          locale,
          "Qui a produit les sessions de cette page — sans identité inventée.",
          "Wer die Sessions dieser Seite erzeugt hat — ohne erfundene Identität.",
          "Who produced this page's sessions — no invented identity.",
        )}
      />
      <HonestNote>
        {pick(
          locale,
          "Les sessions évaluées sont exécutées par le harnais d'évaluation, pas par des clients finaux : aucune identité d'utilisateur final n'est enregistrée dans ce payload. Les conversations réelles de l'onglet Messages sont menées par l'opérateur de la démo.",
          "Die evaluierten Sessions werden vom Evaluierungs-Harness ausgeführt, nicht von Endkunden: keine Endbenutzer-Identität wird in diesem Payload erfasst. Die realen Konversationen im Tab Nachrichten führt der Demo-Operator.",
          "Evaluated sessions are executed by the evaluation harness, not by end customers: no end-user identity is recorded in this payload. The real conversations under the Messages tab are led by the demo operator.",
        )}
      </HonestNote>
      {operators.length === 0 ? (
        <EmptyState label={pick(locale, "Aucune session.", "Keine Sessions.", "No sessions.")} />
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            <Stat
              label={pick(
                locale,
                "Opérateurs distincts",
                "Verschiedene Operatoren",
                "Distinct operators",
              )}
              value={String(operators.length)}
            />
            <Stat
              label={pick(locale, "Sessions évaluées", "Evaluierte Sessions", "Evaluated sessions")}
              value={String(rows.length)}
            />
            <Stat
              label={pick(
                locale,
                "Conversations réelles",
                "Reale Konversationen",
                "Real conversations",
              )}
              value={String(convos.length)}
            />
          </div>
          <DataTable
            columns={columns}
            rows={operators}
            rowKey={(r) => r.user}
            noun={pick(locale, "opérateurs", "Operatoren", "operators")}
            emptyLabel={pick(locale, "Aucun opérateur.", "Keine Operatoren.", "No operators.")}
            initialSortCol={1}
            initialSortDir="desc"
            minWidth="720px"
          />
        </>
      )}
    </div>
  );
}

// ── Contenu & sources ────────────────────────────────────────────────────────

export function ContentTab() {
  const locale = useLocale();
  const agentId = useAgentId();
  return (
    <div className="flex flex-col gap-2.5">
      <TabHeader
        title={pick(locale, "Contenu & sources", "Inhalt & Quellen", "Content & sources")}
        subtitle={pick(
          locale,
          "Les documents et sources cités par les réponses de l'agent.",
          "Die von den Antworten des Agenten zitierten Dokumente und Quellen.",
          "The documents and sources the agent's answers cite.",
        )}
      />
      <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-[var(--tessera-border)] px-4 py-12 text-center">
        <FolderSearch className="h-8 w-8 text-[var(--tessera-text-muted)]" />
        <p className="max-w-[520px] text-[0.78rem] leading-relaxed text-[var(--tessera-text-muted)]">
          {pick(
            locale,
            "Aucune donnée de sources n'accompagne les sessions de ce payload : les citations et documents consultés ne sont pas capturés par le harnais d'évaluation. Plutôt qu'un tableau fabriqué, cet onglet le dit. Le corpus que l'agent consulte se gère dans Connaissances.",
            "Keine Quellendaten begleiten die Sessions dieses Payloads: zitierte Dokumente werden vom Evaluierungs-Harness nicht erfasst. Statt einer erfundenen Tabelle sagt dieser Tab das. Das Korpus des Agenten wird unter Wissen verwaltet.",
            "No source data rides with this payload's sessions: citations and consulted documents are not captured by the evaluation harness. Rather than a fabricated table, this tab says so. The corpus the agent consults is managed under Connaissances.",
          )}
        </p>
        <Link
          href={agentPath(agentId, "connaissances") as Route}
          className="flex items-center gap-1.5 text-[0.72rem] text-[var(--tessera-fg-accent)] hover:text-[var(--tessera-text-strong)]"
        >
          {pick(
            locale,
            "Ouvrir la page Connaissances",
            "Die Wissensseite öffnen",
            "Open the Connaissances page",
          )}
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>
    </div>
  );
}

// ── Erreurs ──────────────────────────────────────────────────────────────────

export function ErrorsTab({ data }: { data: Data }) {
  const locale = useLocale();
  const [selected, setSelected] = useState<string | null>(null);
  const rows = data.table?.rows ?? [];
  const failed = useMemo(() => rows.filter((r) => !r.passed), [rows]);
  const escalations = failed.filter((r) => r.escalation).length;
  const categories = new Set(failed.map((r) => r.category_key)).size;
  const labels = data.detail_labels;

  const title = pick(locale, "Erreurs", "Fehler", "Errors");
  const subtitle = pick(
    locale,
    "Les sessions dont l'évaluation a échoué — avec l'échange complet pour comprendre pourquoi.",
    "Die Sessions mit fehlgeschlagener Evaluierung — mit dem vollständigen Austausch.",
    "The sessions whose evaluation failed — with the full exchange to understand why.",
  );

  if (rows.length > 0 && failed.length === 0) {
    return (
      <div className="flex flex-col gap-2.5">
        <TabHeader title={title} subtitle={subtitle} />
        <div className="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1.5 text-[0.68rem] text-[var(--tessera-fg-success)]">
          {pick(
            locale,
            "Aucune session en échec sur ce run.",
            "Keine fehlgeschlagene Session in diesem Lauf.",
            "No failed session on this run.",
          )}
        </div>
      </div>
    );
  }

  const selectedRow = failed.find((r) => r.sid === selected) ?? null;
  const columns: Column<Row>[] = [
    ...identityColumns(locale),
    {
      key: "lang",
      label: pick(locale, "Langue", "Sprache", "Language"),
      width: "8%",
      sortValue: (r) => r.lang,
      render: (r) => (
        <span className="font-mono text-[0.62rem] uppercase text-[var(--tessera-text-muted)]">
          {r.lang}
        </span>
      ),
    },
    statusColumn(locale),
    {
      key: "escalation",
      label: pick(locale, "Escalade", "Eskalation", "Escalation"),
      width: "10%",
      sortValue: (r) => (r.escalation ? 1 : 0),
      render: (r) =>
        r.escalation ? (
          <span className="text-[0.66rem] text-[var(--tessera-fg-warning)]">
            {pick(locale, "oui", "ja", "yes")}
          </span>
        ) : (
          <span className="text-[0.66rem] text-[var(--tessera-text-muted)]">
            {pick(locale, "non", "nein", "no")}
          </span>
        ),
    },
    {
      key: "start",
      label: pick(locale, "Date", "Datum", "Date"),
      width: "14%",
      sortValue: (r) => r.start_ts,
      render: (r) => (
        <span className="whitespace-nowrap text-[0.66rem] tabular-nums text-[var(--tessera-text-muted)]">
          {r.start}
        </span>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-2.5">
      <TabHeader title={title} subtitle={subtitle} />
      {rows.length === 0 ? (
        <EmptyState label={pick(locale, "Aucune session.", "Keine Sessions.", "No sessions.")} />
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            <Stat
              label={pick(locale, "Échecs", "Fehlschläge", "Failures")}
              value={`${failed.length}/${rows.length}`}
              tone="text-[var(--tessera-fg-danger)]"
            />
            <Stat
              label={pick(locale, "Escalades", "Eskalationen", "Escalations")}
              value={String(escalations)}
              tone={escalations > 0 ? "text-[var(--tessera-fg-warning)]" : undefined}
            />
            <Stat
              label={pick(
                locale,
                "Catégories touchées",
                "Betroffene Kategorien",
                "Affected categories",
              )}
              value={String(categories)}
            />
          </div>
          <DataTable
            columns={columns}
            rows={failed}
            rowKey={(r) => r.sid}
            noun={pick(locale, "échecs", "Fehlschläge", "failures")}
            emptyLabel={pick(locale, "Aucun échec.", "Keine Fehlschläge.", "No failures.")}
            selectedKey={selectedRow?.sid ?? null}
            onRowClick={(r) => setSelected(r.sid)}
            initialSortCol={6}
            initialSortDir="desc"
            minWidth="820px"
          />
        </>
      )}
      {selectedRow ? (
        <EvalDrawer
          title={selectedRow.case_id}
          subtitle={`${selectedRow.sid} · ${selectedRow.start}`}
          icon={<AlertTriangle className="h-4 w-4 text-[var(--tessera-fg-danger)]" />}
          onClose={() => setSelected(null)}
        >
          <div className="flex flex-col gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5">
            <DrawerField label={pick(locale, "Statut", "Status", "Status")}>
              {selectedRow.status}
            </DrawerField>
            <DrawerField label="Score">{selectedRow.score}</DrawerField>
            <DrawerField label={pick(locale, "Escalade", "Eskalation", "Escalation")}>
              {selectedRow.escalation
                ? pick(locale, "oui", "ja", "yes")
                : pick(locale, "non", "nein", "no")}
            </DrawerField>
          </div>
          <DrawerText
            title={labels?.question_label ?? pick(locale, "Question", "Frage", "Question")}
            text={selectedRow.question}
          />
          <DrawerText
            title={labels?.response_label ?? pick(locale, "Réponse", "Antwort", "Response")}
            text={selectedRow.response}
          />
        </EvalDrawer>
      ) : null}
    </div>
  );
}

// ── Exports ──────────────────────────────────────────────────────────────────

export function HistoriqueExportsTab({ data }: { data: Data }) {
  const locale = useLocale();
  const agentId = useAgentId();
  const rows = data.table?.rows ?? [];
  const convos = data.live_conversations ?? [];
  const base = `tessera-${agentId}-historique`;

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
      key: "sessions-csv",
      icon: <Table2 className="h-5 w-5 text-[var(--tessera-fg-success)]" />,
      title: pick(locale, "Sessions (CSV)", "Sessions (CSV)", "Sessions (CSV)"),
      desc: pick(
        locale,
        "Chaque session évaluée : cas, catégorie, statut, score, latence, jetons.",
        "Jede evaluierte Session: Fall, Kategorie, Status, Score, Latenz, Tokens.",
        "Every evaluated session: case, category, status, score, latency, tokens.",
      ),
      format: "CSV",
      available: rows.length > 0,
      onExport: () =>
        downloadBlob(
          `${base}-sessions.csv`,
          "text/csv",
          toCsv(
            [
              "sid",
              "case_id",
              "category",
              "lang",
              "status",
              "score",
              "passed",
              "escalation",
              "tools",
              "latency_ms",
              "in_tokens",
              "out_tokens",
              "started_at",
            ],
            rows.map((r) => [
              r.sid,
              r.case_id,
              r.category_key,
              r.lang,
              r.status,
              r.score_num,
              r.passed,
              r.escalation,
              r.tools_count,
              r.latency_ms,
              r.input_tokens,
              r.output_tokens,
              r.start_ts,
            ]),
          ),
        ),
    },
    {
      key: "sessions-json",
      icon: <FileJson className="h-5 w-5 text-[var(--tessera-fg-info)]" />,
      title: pick(locale, "Sessions (JSON)", "Sessions (JSON)", "Sessions (JSON)"),
      desc: pick(
        locale,
        "Les lignes complètes du tableau, telles que servies par l'API.",
        "Die vollständigen Tabellenzeilen, wie von der API geliefert.",
        "The full table rows, as served by the API.",
      ),
      format: "JSON",
      available: rows.length > 0,
      onExport: () =>
        downloadBlob(`${base}-sessions.json`, "application/json", JSON.stringify(rows, null, 2)),
    },
    {
      key: "exchanges-json",
      icon: <FileText className="h-5 w-5 text-[var(--tessera-fg-accent)]" />,
      title: pick(locale, "Échanges Q/R (JSON)", "Q/A-Austausche (JSON)", "Q/A exchanges (JSON)"),
      desc: pick(
        locale,
        "Question et réponse de chaque session, avec cas et verdict.",
        "Frage und Antwort jeder Session, mit Fall und Urteil.",
        "Each session's question and response, with case and verdict.",
      ),
      format: "JSON",
      available: rows.length > 0,
      onExport: () =>
        downloadBlob(
          `${base}-echanges.json`,
          "application/json",
          JSON.stringify(
            rows.map((r) => ({
              sid: r.sid,
              case_id: r.case_id,
              lang: r.lang,
              passed: r.passed,
              question: r.question,
              response: r.response,
            })),
            null,
            2,
          ),
        ),
    },
    {
      key: "conversations-csv",
      icon: <MessagesSquare className="h-5 w-5 text-[var(--tessera-fg-warning)]" />,
      title: pick(
        locale,
        "Conversations réelles (CSV)",
        "Reale Konversationen (CSV)",
        "Real conversations (CSV)",
      ),
      desc: pick(
        locale,
        "Les conversations du transcript : titre, horodatages, volumes.",
        "Die Konversationen des Transkripts: Titel, Zeitstempel, Volumen.",
        "The transcript conversations: title, timestamps, volumes.",
      ),
      format: "CSV",
      available: convos.length > 0,
      onExport: () =>
        downloadBlob(
          `${base}-conversations.csv`,
          "text/csv",
          toCsv(
            ["conversation_id", "title", "started_at", "last_at", "messages", "turns"],
            convos.map((c) => [
              c.conversation_id,
              c.title,
              c.started_at,
              c.last_at,
              c.message_count,
              c.turn_count,
            ]),
          ),
        ),
    },
  ];

  const active = cards.filter((c) => c.available);

  return (
    <div className="flex flex-col gap-2.5">
      <TabHeader
        title={pick(locale, "Exports", "Exporte", "Exports")}
        subtitle={pick(
          locale,
          "Téléchargez les données de cette page — fichiers générés côté navigateur.",
          "Laden Sie die Daten dieser Seite herunter — im Browser erzeugte Dateien.",
          "Download this page's data — files generated in the browser.",
        )}
      />
      {active.length === 0 ? (
        <EmptyState
          label={pick(locale, "Rien à exporter.", "Nichts zu exportieren.", "Nothing to export.")}
        />
      ) : (
        <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-4">
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
    </div>
  );
}
