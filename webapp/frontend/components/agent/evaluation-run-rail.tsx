"use client";

import type { Route } from "next";
import { useLocale } from "next-intl";
import { useSearchParams } from "next/navigation";

import { Link } from "@/i18n/navigation";
import { agentPath } from "@/lib/agent-context";
import type { AgentEvaluations as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import { useAgentId } from "@/lib/use-agent-id";

// Evaluation Run Rail (registre des rails temporels §4, substrat S3 / composant C2):
// the AGENT/Évaluations run journal — it walks RUNS, one point per evaluation run,
// each carrying its OWN stored provenance (date + catalogue version + model,
// eval-gate-policy § provenance) and the gate verdict recorded at run time. It is
// distinct from the SR-01 signal scrubber (S4/C4): no signals, no scrub, no replay.
//
// Contract (§5 of the registre): the selected run derives from the URL
// (`?run=<run_at>`, deep-linkable — never component state), and the active mode is
// always visible (Live = latest run · Historique = an older run). The rail code
// stays internal: it is never displayed.

const RUN_PARAM = "run";

type RunsBlock = NonNullable<Data["runs"]>;
type RunItem = RunsBlock["items"][number];

function pick(locale: string, fr: string, de: string, en: string): string {
  return locale === "de" ? de : locale === "en" ? en : fr;
}

function nf(locale: string): Intl.NumberFormat {
  return new Intl.NumberFormat(locale === "de" ? "de-DE" : locale === "en" ? "en-GB" : "fr-FR", {
    maximumFractionDigits: 1,
  });
}

/** The gate verdict recorded at run time — `null` = not recorded, said as such. */
function verdictLabel(gatePassed: boolean | null, locale: string): string {
  if (gatePassed === null)
    return pick(locale, "non enregistré", "nicht aufgezeichnet", "not recorded");
  return gatePassed
    ? pick(locale, "PASSE", "BESTANDEN", "PASS")
    : pick(locale, "BLOQUÉ", "BLOCKIERT", "BLOCKED");
}

const VERDICT_TEXT: Record<string, string> = {
  true: "text-emerald-300",
  false: "text-red-300",
  null: "text-[var(--tessera-text-muted)]",
};

const VERDICT_BAR: Record<string, string> = {
  true: "bg-[#3fb37f]",
  false: "bg-[#e0566f]",
  null: "bg-slate-500",
};

/** One run's provenance, the shape the policy demands: set · date · catalogue. */
function provenance(run: RunItem, locale: string): string {
  const cat = run.catalogue_version
    ? `cat ${run.catalogue_version}`
    : pick(locale, "cat non enregistrée", "Katalog nicht aufgezeichnet", "cat not recorded");
  return `${run.eval_set || "—"} · ${run.date_label} · ${cat}`;
}

export function EvaluationRunRail({ data, className }: { data: Data; className?: string }) {
  const locale = useLocale();
  const agentId = useAgentId();
  const searchParams = useSearchParams();
  const runs = data.runs;
  if (!runs) return null;

  const items = runs.items; // newest first (the backend's journal order)
  const requested = searchParams.get(RUN_PARAM);
  const requestedRun = requested ? (items.find((r) => r.run_at === requested) ?? null) : null;
  const requestedUnknown = requested !== null && requestedRun === null;
  const selected = requestedRun ?? items[0] ?? null;
  const live = selected === null || selected.run_at === items[0]?.run_at;

  // The URL is the selection: each point is a deep-linkable door, the latest run
  // being the canonical (param-less) address. Other query params (e.g. the SR-01
  // scrubber's) ride along untouched.
  const hrefFor = (runAt: string | null): Route => {
    const params = new URLSearchParams(searchParams.toString());
    if (runAt === null || runAt === items[0]?.run_at) params.delete(RUN_PARAM);
    else params.set(RUN_PARAM, runAt);
    const query = params.toString();
    const base = agentPath(agentId, "evaluations");
    return (query ? `${base}?${query}` : base) as Route;
  };

  const oldestFirst = [...items].reverse();
  const fmt = nf(locale);

  return (
    <section
      className={cn(
        "flex min-w-0 flex-col gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3",
        className,
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[11px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
          {runs.title}
        </span>
        {/* The active mode, always visible (registre §1/§5). */}
        <span
          className={cn(
            "rounded-full border px-2 py-0.5 text-[10px] font-medium",
            live
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
              : "border-amber-500/40 bg-amber-500/10 text-amber-300",
          )}
        >
          {live
            ? pick(locale, "Live · dernier run", "Live · letzter Lauf", "Live · latest run")
            : `${pick(locale, "Historique · run du", "Historisch · Lauf vom", "History · run of")} ${selected?.label ?? ""}`}
        </span>
      </div>
      <p className="-mt-1 text-[10px] text-[var(--tessera-text-muted)]">{runs.subtitle}</p>

      {items.length === 0 ? (
        // Honest-empty: no run recorded — an explicitly empty rail, never a ghost
        // axis nor an invented zero.
        <p className="rounded-md border border-dashed border-[var(--tessera-border)] px-3 py-4 text-[11px] text-[var(--tessera-text-muted)]">
          {runs.empty_label}
        </p>
      ) : (
        <>
          <div className="flex items-end gap-1.5 overflow-x-auto pb-1 pt-1">
            {oldestFirst.map((run) => {
              const isSelected = selected?.run_at === run.run_at;
              const barClass = VERDICT_BAR[String(run.gate_passed)] ?? VERDICT_BAR.null;
              const height = run.total > 0 ? 10 + Math.round(run.pass_rate * 38) : 6;
              return (
                <Link
                  key={run.run_at}
                  replace
                  scroll={false}
                  href={hrefFor(run.run_at)}
                  aria-current={isSelected ? "true" : undefined}
                  title={`${provenance(run, locale)} · ${run.passed}/${run.total} · ${verdictLabel(run.gate_passed, locale)}`}
                  className={cn(
                    "flex shrink-0 flex-col items-center gap-1 rounded-md border px-1.5 pb-1 pt-1.5",
                    isSelected
                      ? "border-[#7c5cf5] bg-[#7c5cf5]/10"
                      : "border-transparent hover:border-[var(--tessera-border)]",
                  )}
                >
                  <span className="flex h-[52px] items-end">
                    <span
                      className={cn("w-4 rounded-sm", barClass, isSelected ? "" : "opacity-70")}
                      style={{ height: `${height}px` }}
                    />
                  </span>
                  <span
                    className={cn(
                      "text-[9px] tabular-nums",
                      isSelected
                        ? "text-[var(--tessera-text)]"
                        : "text-[var(--tessera-text-muted)]",
                    )}
                  >
                    {run.date_label}
                  </span>
                </Link>
              );
            })}
          </div>

          {requestedUnknown ? (
            <p className="text-[10px] text-amber-300">
              {pick(
                locale,
                "Run demandé introuvable — dernier run affiché.",
                "Angeforderter Lauf nicht gefunden — letzter Lauf angezeigt.",
                "Requested run not found — showing the latest run.",
              )}
            </p>
          ) : null}

          {selected ? (
            <SelectedRunFacts run={selected} items={items} locale={locale} fmt={fmt} />
          ) : null}

          {items.length === 1 ? (
            <p className="text-[10px] text-[var(--tessera-text-muted)]">
              {pick(
                locale,
                "Un seul run — un point n'est pas une tendance ; la comparaison apparaîtra au deuxième run.",
                "Nur ein Lauf — ein Punkt ist kein Trend; der Vergleich erscheint mit dem zweiten Lauf.",
                "A single run — one point is not a trend; the comparison appears with the second run.",
              )}
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}

/** The selected run's stored facts: provenance line, counts, recorded verdict, Δ. */
function SelectedRunFacts({
  run,
  items,
  locale,
  fmt,
}: {
  run: RunItem;
  items: RunItem[];
  locale: string;
  fmt: Intl.NumberFormat;
}) {
  const idx = items.findIndex((r) => r.run_at === run.run_at);
  const hasPrevious = idx >= 0 && idx + 1 < items.length;
  const verdictTone = VERDICT_TEXT[String(run.gate_passed)] ?? VERDICT_TEXT.null;
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1.5">
      <span className="text-[11px] font-medium text-[var(--tessera-text)]">
        {provenance(run, locale)}
      </span>
      <span className="text-[10px] text-[var(--tessera-text-muted)]">{run.label}</span>
      <span className="text-[10px] text-[var(--tessera-text-muted)]">{run.model}</span>
      <span className="text-[11px] tabular-nums text-[var(--tessera-text)]">
        {run.total > 0
          ? `${run.passed}/${run.total} (${fmt.format(run.pass_rate * 100)}%)`
          : pick(locale, "0 cas", "0 Faelle", "0 cases")}
      </span>
      <span className={cn("text-[11px] font-semibold", verdictTone)}>
        {pick(locale, "Gate :", "Gate:", "Gate:")} {verdictLabel(run.gate_passed, locale)}
      </span>
      {/* Δ only exists between TWO runs of the SAME catalogue version. */}
      {run.delta_pass_rate !== null ? (
        <span
          className={cn(
            "text-[11px] tabular-nums",
            run.delta_pass_rate > 0
              ? "text-emerald-300"
              : run.delta_pass_rate < 0
                ? "text-red-300"
                : "text-[var(--tessera-text-muted)]",
          )}
        >
          {`Δ ${run.delta_pass_rate > 0 ? "+" : ""}${fmt.format(run.delta_pass_rate * 100)} pt ${pick(locale, "vs run précédent", "ggue. vorherigem Lauf", "vs previous run")}`}
        </span>
      ) : hasPrevious ? (
        <span className="text-[10px] text-[var(--tessera-text-muted)]">
          {pick(
            locale,
            "Δ non comparable (version de catalogue différente)",
            "Δ nicht vergleichbar (andere Katalogversion)",
            "Δ not comparable (different catalogue version)",
          )}
        </span>
      ) : null}
    </div>
  );
}
