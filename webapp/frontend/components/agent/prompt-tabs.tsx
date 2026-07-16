"use client";

/**
 * The AGENT / Prompts sub-tab views beyond the overview: Variables (which
 * template `{var}` each prompt declares, aggregated across the catalogue) and
 * Couverture i18n (each prompt's languages + per-language length balance — the
 * real translation-drift signal, since every prompt is present in all three
 * languages). Both are built entirely from the existing payload's per-language
 * prompt text (`details[].content`); no backend change, no contract chain.
 */

import { Braces, FileCode2, Languages } from "lucide-react";
import { useLocale } from "next-intl";
import { useMemo, useState } from "react";

import type { AgentPrompts as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import {
  type Column,
  DataTable,
  EvalDrawer,
  FilterBar,
  LangBadges,
  ResetButton,
  SearchInput,
  pick,
} from "./agent-subtab-shared";

type Detail = NonNullable<Data["details"]>[number];

const LANGS = ["fr", "de", "en"] as const;
const VAR_RE = /\{(\w+)\}/g;
const BALANCE_WARN = 1.6; // max/min length ratio above which we flag drift

/** Template variables a prompt declares, from its content across all languages. */
function varsOf(detail: Detail): string[] {
  const set = new Set<string>();
  for (const c of detail.content) {
    for (const m of c.text.matchAll(VAR_RE)) {
      const name = m[1];
      if (name) set.add(name);
    }
  }
  return [...set].sort();
}

/** Per-language text length, keyed lowercase (the payload codes langs "FR"/"DE"/"EN"). */
function lenByLang(detail: Detail): Record<string, number> {
  const out: Record<string, number> = {};
  for (const c of detail.content) out[c.lang.toLowerCase()] = c.text.length;
  return out;
}

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

// ── Variables ────────────────────────────────────────────────────────────────

type VarRow = { name: string; count: number; prompts: Detail[] };

export function VariablesTab({ data }: { data: Data }) {
  const locale = useLocale();
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const details = data.details ?? [];

  const rows = useMemo<VarRow[]>(() => {
    const agg = new Map<string, Detail[]>();
    for (const d of details) {
      for (const v of varsOf(d)) {
        const list = agg.get(v) ?? [];
        list.push(d);
        agg.set(v, list);
      }
    }
    return [...agg.entries()].map(([name, prompts]) => ({ name, count: prompts.length, prompts }));
  }, [details]);

  const withVars = useMemo(() => details.filter((d) => varsOf(d).length > 0).length, [details]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return q ? rows.filter((r) => r.name.toLowerCase().includes(q)) : rows;
  }, [rows, search]);

  const title = pick(locale, "Variables", "Variablen", "Variables");
  const subtitle = pick(
    locale,
    "Les variables de gabarit {var} déclarées par les prompts, agrégées sur le catalogue.",
    "Die {var}-Vorlagenvariablen der Prompts, über den Katalog aggregiert.",
    "The {var} template variables the prompts declare, aggregated across the catalogue.",
  );

  if (rows.length === 0) {
    return (
      <div className="flex flex-col gap-2.5">
        <TabHeader title={title} subtitle={subtitle} />
        <EmptyState
          label={pick(
            locale,
            "Aucune variable de gabarit dans les prompts.",
            "Keine Vorlagenvariablen in den Prompts.",
            "No template variables in the prompts.",
          )}
        />
      </div>
    );
  }

  const selectedRow = rows.find((r) => r.name === selected) ?? null;
  const columns: Column<VarRow>[] = [
    {
      key: "name",
      label: pick(locale, "Variable", "Variable", "Variable"),
      width: "50%",
      sortValue: (r) => r.name,
      render: (r) => (
        <div className="flex min-w-0 items-center gap-2">
          <Braces className="h-4 w-4 shrink-0 text-[#8b7cf0]" />
          <span className="truncate font-mono font-medium text-[var(--tessera-text)]">{`{${r.name}}`}</span>
        </div>
      ),
    },
    {
      key: "count",
      label: pick(locale, "Prompts", "Prompts", "Prompts"),
      width: "25%",
      numeric: true,
      sortValue: (r) => r.count,
      render: (r) => r.count,
    },
    {
      key: "used",
      label: pick(locale, "Utilisée dans", "Verwendet in", "Used in"),
      width: "25%",
      sortable: false,
      render: (r) => (
        <span className="truncate text-[0.66rem] text-[var(--tessera-text-muted)]">
          {r.prompts.map((p) => p.name).join(", ")}
        </span>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-2.5">
      <TabHeader title={title} subtitle={subtitle} />
      <div className="flex flex-wrap gap-2">
        <Stat
          label={pick(locale, "Variables uniques", "Eindeutige Variablen", "Unique variables")}
          value={String(rows.length)}
        />
        <Stat
          label={pick(
            locale,
            "Prompts avec variables",
            "Prompts mit Variablen",
            "Prompts with variables",
          )}
          value={String(withVars)}
        />
        <Stat
          label={pick(locale, "Sans variable", "Ohne Variable", "Without variable")}
          value={String(details.length - withVars)}
        />
      </div>
      <FilterBar>
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder={pick(
            locale,
            "Rechercher une variable…",
            "Variable suchen…",
            "Search a variable…",
          )}
        />
        {search ? <ResetButton onClick={() => setSearch("")} /> : null}
      </FilterBar>
      <DataTable
        columns={columns}
        rows={filtered}
        rowKey={(r) => r.name}
        noun={pick(locale, "variables", "Variablen", "variables")}
        emptyLabel={pick(locale, "Aucune variable.", "Keine Variablen.", "No variables.")}
        selectedKey={selectedRow?.name ?? null}
        onRowClick={(r) => setSelected(r.name)}
        initialSortCol={1}
        initialSortDir="desc"
        minWidth="620px"
      />
      {selectedRow ? (
        <EvalDrawer
          title={`{${selectedRow.name}}`}
          subtitle={pick(
            locale,
            `${selectedRow.count} prompt(s)`,
            `${selectedRow.count} Prompt(s)`,
            `${selectedRow.count} prompt(s)`,
          )}
          icon={<Braces className="h-4 w-4 text-[#8b7cf0]" />}
          onClose={() => setSelected(null)}
        >
          <ul className="flex flex-col gap-1.5">
            {selectedRow.prompts.map((p) => (
              <li
                key={p.key}
                className="flex items-center justify-between gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1.5 text-[0.72rem]"
              >
                <span className="min-w-0 truncate font-medium text-[var(--tessera-text)]">
                  {p.name}
                </span>
                <span className="shrink-0 font-mono text-[0.6rem] text-[var(--tessera-text-muted)]">
                  {p.id}
                </span>
              </li>
            ))}
          </ul>
        </EvalDrawer>
      ) : null}
    </div>
  );
}

// ── Couverture i18n ──────────────────────────────────────────────────────────

type I18nRow = {
  key: string;
  name: string;
  langs: string[];
  len: Record<string, number>;
  missing: string[];
  balance: number; // max/min ratio across present langs (1 = perfectly balanced)
  detail: Detail;
};

export function I18nTab({ data }: { data: Data }) {
  const locale = useLocale();
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const details = data.details ?? [];

  const rows = useMemo<I18nRow[]>(() => {
    return details.map((d) => {
      const len = lenByLang(d);
      const langs = d.content.map((c) => c.lang.toLowerCase());
      const missing = LANGS.filter((l) => !langs.includes(l));
      const present = Object.values(len).filter((n) => n > 0);
      const balance = present.length > 0 ? Math.max(...present) / Math.min(...present) : 1;
      return { key: d.key, name: d.name, langs, len, missing, balance, detail: d };
    });
  }, [details]);

  const complete = rows.filter((r) => r.missing.length === 0).length;
  const drifted = rows.filter((r) => r.balance >= BALANCE_WARN).length;

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return q ? rows.filter((r) => r.name.toLowerCase().includes(q)) : rows;
  }, [rows, search]);

  const title = pick(locale, "Couverture i18n", "i18n-Abdeckung", "i18n coverage");
  const subtitle = pick(
    locale,
    "Chaque prompt par langue — présence et équilibre des longueurs (dérive de traduction).",
    "Jeder Prompt je Sprache — Präsenz und Längenbalance (Übersetzungsdrift).",
    "Each prompt by language — presence and length balance (translation drift).",
  );
  const lenCol = (lang: string) => ({
    key: `len_${lang}`,
    label: lang.toUpperCase(),
    width: "12%",
    numeric: true,
    sortValue: (r: I18nRow) => r.len[lang] ?? -1,
    render: (r: I18nRow) =>
      r.len[lang] ? (
        <span className="text-[var(--tessera-text-muted)]">
          {r.len[lang].toLocaleString(locale)}
        </span>
      ) : (
        <span className="text-[#ff9bb0]">-</span>
      ),
  });

  const selectedRow = rows.find((r) => r.key === selected) ?? null;
  const columns: Column<I18nRow>[] = [
    {
      key: "name",
      label: pick(locale, "Prompt", "Prompt", "Prompt"),
      width: "30%",
      sortValue: (r) => r.name,
      render: (r) => (
        <div className="flex min-w-0 items-center gap-2">
          <FileCode2 className="h-4 w-4 shrink-0 text-[#8b7cf0]" />
          <span className="truncate font-medium text-[var(--tessera-text)]">{r.name}</span>
        </div>
      ),
    },
    {
      key: "langs",
      label: pick(locale, "Langues", "Sprachen", "Languages"),
      width: "16%",
      sortValue: (r) => r.langs.length,
      render: (r) =>
        r.missing.length === 0 ? (
          <LangBadges langs={r.langs} />
        ) : (
          <span className="text-[0.62rem] text-[#ff9bb0]">
            {pick(locale, "manque", "fehlt", "missing")} {r.missing.join(", ").toUpperCase()}
          </span>
        ),
    },
    lenCol("fr"),
    lenCol("de"),
    lenCol("en"),
    {
      key: "balance",
      label: pick(locale, "Écart", "Abweichung", "Spread"),
      width: "18%",
      numeric: true,
      sortValue: (r) => r.balance,
      render: (r) => (
        <span
          className={cn(
            r.missing.length > 0
              ? "text-[#ff9bb0]"
              : r.balance >= BALANCE_WARN
                ? "text-amber-300"
                : "text-emerald-300",
          )}
        >
          {`${r.balance.toFixed(1)}x`}
        </span>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-2.5">
      <TabHeader title={title} subtitle={subtitle} />
      <div className="flex flex-wrap gap-2">
        <Stat label={pick(locale, "Prompts", "Prompts", "Prompts")} value={String(rows.length)} />
        <Stat
          label={pick(locale, "Trilingues", "Dreisprachig", "Trilingual")}
          value={`${complete}/${rows.length}`}
          tone={complete === rows.length ? "text-emerald-300" : "text-[#ff9bb0]"}
        />
        <Stat
          label={pick(locale, "Écart de longueur", "Längendrift", "Length drift")}
          value={String(drifted)}
          tone={drifted > 0 ? "text-amber-300" : undefined}
        />
      </div>
      <FilterBar>
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder={pick(locale, "Rechercher un prompt…", "Prompt suchen…", "Search a prompt…")}
        />
        {search ? <ResetButton onClick={() => setSearch("")} /> : null}
      </FilterBar>
      <DataTable
        columns={columns}
        rows={filtered}
        rowKey={(r) => r.key}
        noun={pick(locale, "prompts", "Prompts", "prompts")}
        emptyLabel={pick(locale, "Aucun prompt.", "Keine Prompts.", "No prompts.")}
        selectedKey={selectedRow?.key ?? null}
        onRowClick={(r) => setSelected(r.key)}
        initialSortCol={5}
        initialSortDir="desc"
        minWidth="720px"
      />
      {selectedRow ? (
        <EvalDrawer
          title={selectedRow.name}
          subtitle={pick(
            locale,
            `${selectedRow.langs.length}/3 langues · écart ${selectedRow.balance.toFixed(1)}x`,
            `${selectedRow.langs.length}/3 Sprachen · Abweichung ${selectedRow.balance.toFixed(1)}x`,
            `${selectedRow.langs.length}/3 languages · spread ${selectedRow.balance.toFixed(1)}x`,
          )}
          icon={<Languages className="h-4 w-4 text-[#8b7cf0]" />}
          onClose={() => setSelected(null)}
        >
          {selectedRow.detail.content.map((c) => (
            <div
              key={c.lang}
              className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5"
            >
              <div className="mb-1 flex items-center justify-between">
                <span className="rounded border border-[var(--tessera-border)] px-1.5 py-0.5 text-[0.56rem] font-medium uppercase text-[var(--tessera-text-muted)]">
                  {c.lang}
                </span>
                <span className="text-[0.6rem] tabular-nums text-[var(--tessera-text-muted)]">
                  {c.text.length.toLocaleString(locale)} {pick(locale, "car.", "Z.", "chars")}
                </span>
              </div>
              <p className="line-clamp-4 whitespace-pre-wrap text-[0.68rem] leading-relaxed text-[var(--tessera-text-muted)]">
                {c.text}
              </p>
            </div>
          ))}
        </EvalDrawer>
      ) : null}
    </div>
  );
}
