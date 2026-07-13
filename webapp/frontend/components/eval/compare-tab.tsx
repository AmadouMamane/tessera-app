import { AlertTriangle, ChevronRight, Clock, Hash, Scale } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { CompareControls } from "@/components/eval/compare-controls";
import { CriterionLine } from "@/components/eval/criterion-line";
import { ScoreCard } from "@/components/eval/score-card";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import type { EvalCase, ScorecardDocument, ScorecardResult } from "@/lib/api/schemas";
import { type Disagreement, compareRuns, sizeBuysNothing } from "@/lib/eval-compare";
import { evaluateCriteria, listCriteria } from "@/lib/eval-criteria";
import { type CellState, MIN_CONTRIBUTION_UNCALIBRATED, decomposeRun } from "@/lib/eval-score";
import type { Sweep, SweepRun } from "@/lib/eval-sweep";

/**
 * `Comparaison` — the same case set, two models (§3 C, §A1.6).
 *
 * It ranks nothing. The sweep measured `llama3.2:3b` and `gemma3:27b` at the SAME 157/174 while one
 * of them degrades the agent, so an ordering by the total would be an ordering of noise. What this
 * tab shows instead is where they DISAGREE — the only cases that say anything about either — with
 * the model's regression on the floor at the top, because nothing outranks being worse than having
 * no model at all.
 *
 * And it shows the cost. Comparing quality without cost is half a decision.
 */
export async function CompareTab({
  sweep,
  a,
  b,
  docA,
  docB,
  locale,
}: {
  sweep: Sweep;
  a: SweepRun;
  b: SweepRun;
  docA: ScorecardDocument;
  docB: ScorecardDocument;
  locale: string;
}) {
  const t = await getTranslations({ locale, namespace: "eval" });

  const comparison = compareRuns(a, b, sweep.floor?.verdicts ?? null, sweep.categoryOf);
  const cardA = decomposeRun(a, sweep.floor, MIN_CONTRIBUTION_UNCALIBRATED);
  const cardB = decomposeRun(b, sweep.floor, MIN_CONTRIBUTION_UNCALIBRATED);

  const finding =
    cardA.kind === "decomposed" && cardB.kind === "decomposed"
      ? sizeBuysNothing(
          { model: a.model, contribution: cardA.contribution },
          { model: b.model, contribution: cardB.contribution },
        )
      : null;

  const resultsA = new Map(docA.results.map((r) => [`${r.case_id}|${r.language}`, r]));
  const resultsB = new Map(docB.results.map((r) => [`${r.case_id}|${r.language}`, r]));
  const caseOf = new Map(sweep.catalogue.map((c) => [c.id, c]));

  return (
    <div className="flex flex-col gap-5">
      <CompareControls
        runs={sweep.runs.map((r) => ({ id: r.id, model: r.model, runAt: r.runAt }))}
        a={a.id}
        b={b.id}
        version={sweep.catalogueVersion}
        labels={{
          referential: t("compare.referential"),
          modelA: t("compare.modelA"),
          modelB: t("compare.modelB"),
          locked: t("compare.locked"),
        }}
      />

      {/* Criterion 2: never a delta without its référentiel — and when it is not held, SHOUT. */}
      {comparison.offReferential ? (
        <div className="flex items-start gap-2 rounded-md border border-danger-500/40 bg-danger-50 p-3 text-danger-800 text-xs leading-relaxed dark:bg-danger-700/15 dark:text-danger-100">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            {t("compare.offReferential", {
              a: a.catalogueVersion ?? "—",
              b: b.catalogueVersion ?? "—",
            })}
          </span>
        </div>
      ) : null}

      {/* The head comparison: floor · contribution · breaks · verdict. Through the one card that
          cannot render a bare rate, so the totals can never become the comparison. */}
      <div className="grid gap-4 md:grid-cols-2">
        <ScoreCard card={cardA} locale={locale} runAt={a.runAt} />
        <ScoreCard card={cardB} locale={locale} runAt={b.runAt} />
      </div>

      <CostRow
        a={a}
        b={b}
        labels={{
          title: t("compare.cost"),
          subtitle: t("compare.costWhy"),
          tokens: t("detail.tokens"),
          duration: t("detail.duration"),
          notRecorded: t("detail.notRecorded"),
        }}
      />

      {/* The sweep's most counter-intuitive result, derived — never a sentence someone typed. */}
      {finding ? (
        <div className="flex items-start gap-2 rounded-md border border-gold-500/40 bg-gold-50 p-3 text-xs leading-relaxed dark:bg-gold-900/20">
          <Scale className="mt-0.5 h-4 w-4 shrink-0 text-gold-700 dark:text-gold-300" />
          <span className="text-gold-900 dark:text-gold-100">
            {t("compare.sizeBuysNothing", {
              bigger: finding.bigger,
              biggerB: finding.biggerB,
              smaller: finding.smaller,
              smallerB: finding.smallerB,
            })}
          </span>
        </div>
      ) : null}

      {/* The disagreements. The cases both models get right are noise: they are collapsed below. */}
      <Card>
        <CardContent className="flex flex-col gap-4 p-5">
          <div className="flex flex-col gap-1">
            <h3 className="font-semibold text-base">
              {t("compare.disagreements", { count: comparison.disagreements.length })}
            </h3>
            <p className="text-[var(--muted-foreground)] text-xs leading-relaxed">
              {t("compare.disagreementsWhy", { agreed: comparison.agreed })}
            </p>
          </div>

          {comparison.disagreements.length === 0 ? (
            <EmptyState
              icon={<Scale />}
              title={t("compare.noDisagreement.title")}
              description={t("compare.noDisagreement.body")}
            />
          ) : (
            <ul className="flex flex-col gap-2">
              {comparison.disagreements.map((d) => (
                <DisagreementRow
                  key={d.key}
                  disagreement={d}
                  evalCase={caseOf.get(d.caseId) ?? null}
                  resultA={resultsA.get(d.key) ?? null}
                  resultB={resultsB.get(d.key) ?? null}
                  modelA={a.model}
                  modelB={b.model}
                  locale={locale}
                />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {/* Per-category delta: a model is not better on average, it is better SOMEWHERE. */}
      <Card>
        <CardContent className="flex flex-col gap-3 p-5">
          <h3 className="font-semibold text-base">{t("compare.byCategory")}</h3>
          <ul className="flex flex-col gap-1.5">
            {comparison.byCategory.map((row) => (
              <li key={row.category} className="flex items-center gap-3 text-xs">
                <span className="w-52 shrink-0 truncate text-[var(--muted-foreground)]">
                  {t(`categories.${row.category}`)}
                </span>
                <span className="flex-1 tabular-nums">
                  {row.aOnly === 0 && row.bOnly === 0 ? (
                    <span className="text-[var(--muted-foreground)] italic">
                      {t("compare.categoryTie")}
                    </span>
                  ) : (
                    <span className="flex flex-wrap gap-x-4">
                      {row.aOnly > 0 ? (
                        <span className="text-info-700 dark:text-info-300">
                          {t("compare.categoryWins", { model: a.model ?? "A", n: row.aOnly })}
                        </span>
                      ) : null}
                      {row.bOnly > 0 ? (
                        <span className="text-info-700 dark:text-info-300">
                          {t("compare.categoryWins", { model: b.model ?? "B", n: row.bOnly })}
                        </span>
                      ) : null}
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

function CostRow({
  a,
  b,
  labels,
}: {
  a: SweepRun;
  b: SweepRun;
  labels: {
    title: string;
    subtitle: string;
    tokens: string;
    duration: string;
    notRecorded: string;
  };
}) {
  const minutes = (ms: number | null) =>
    ms === null ? labels.notRecorded : `${(ms / 60_000).toFixed(1)} min`;

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 p-5">
        <div className="flex flex-col gap-0.5">
          <h3 className="font-semibold text-base">{labels.title}</h3>
          <p className="text-[var(--muted-foreground)] text-xs">{labels.subtitle}</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {[a, b].map((run) => (
            <div
              key={run.id}
              className="flex flex-col gap-1.5 rounded-md border border-[var(--border)] p-3"
            >
              <span className="font-mono font-medium text-xs">{run.model ?? "—"}</span>
              <span className="flex items-center gap-1.5 text-[var(--muted-foreground)] text-xs">
                <Hash className="h-3.5 w-3.5" />
                {labels.tokens}
                <span className="text-[var(--foreground)] tabular-nums">
                  {(run.cost?.output_tokens ?? 0).toLocaleString()} out
                </span>
              </span>
              <span className="flex items-center gap-1.5 text-[var(--muted-foreground)] text-xs">
                <Clock className="h-3.5 w-3.5" />
                {labels.duration}
                <span className="text-[var(--foreground)] tabular-nums">
                  {minutes(run.durationMs)}
                </span>
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

const STATE_TONE: Record<CellState, "success" | "danger" | "neutral"> = {
  "floor-pass": "neutral",
  "model-pass": "success",
  "model-break": "danger",
  "both-fail": "danger",
  unknown: "neutral",
};

async function DisagreementRow({
  disagreement,
  evalCase,
  resultA,
  resultB,
  modelA,
  modelB,
  locale,
}: {
  disagreement: Disagreement;
  evalCase: EvalCase | null;
  resultA: ScorecardResult | null;
  resultB: ScorecardResult | null;
  modelA: string | null;
  modelB: string | null;
  locale: string;
}) {
  const t = await getTranslations({ locale, namespace: "eval" });
  const broke = disagreement.a.state === "model-break" || disagreement.b.state === "model-break";

  return (
    <li
      className={`rounded-md border ${
        broke
          ? "border-danger-500/40 bg-danger-50/40 dark:bg-danger-700/10"
          : "border-[var(--border)]"
      }`}
    >
      <details className="group">
        <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-1.5 p-3">
          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-[var(--muted-foreground)] transition-transform group-open:rotate-90" />
          <span className="font-mono text-[11px] text-[var(--muted-foreground)]">
            {disagreement.caseId}
          </span>
          <span className="rounded bg-[var(--muted)] px-1.5 py-0.5 font-mono text-[10px] uppercase">
            {disagreement.language}
          </span>
          <span className="flex-1 truncate text-[var(--muted-foreground)] text-xs">
            {evalCase?.title}
          </span>
          <Badge tone={STATE_TONE[disagreement.a.state]}>
            {modelA} · {t(`matrix.legend.${legendKey(disagreement.a.state)}`)}
          </Badge>
          <Badge tone={STATE_TONE[disagreement.b.state]}>
            {modelB} · {t(`matrix.legend.${legendKey(disagreement.b.state)}`)}
          </Badge>
        </summary>
        <div className="grid gap-3 border-[var(--border)] border-t p-3 md:grid-cols-2">
          <Side
            model={modelA}
            result={resultA}
            evalCase={evalCase}
            locale={locale}
            emptyLabel={t("detail.emptyResponse")}
            brokeLabel={t("detail.brokeBy")}
          />
          <Side
            model={modelB}
            result={resultB}
            evalCase={evalCase}
            locale={locale}
            emptyLabel={t("detail.emptyResponse")}
            brokeLabel={t("detail.brokeBy")}
          />
        </div>
      </details>
    </li>
  );
}

function legendKey(state: CellState): string {
  if (state === "model-break") return "modelBreak";
  if (state === "model-pass") return "modelPass";
  if (state === "floor-pass") return "floorPass";
  return "bothFail";
}

/** One model's answer to the case, and the criterion it broke — reconstructed the same way. */
async function Side({
  model,
  result,
  evalCase,
  locale,
  emptyLabel,
  brokeLabel,
}: {
  model: string | null;
  result: ScorecardResult | null;
  evalCase: EvalCase | null;
  locale: string;
  emptyLabel: string;
  brokeLabel: string;
}) {
  if (!result) return null;
  const violated = evalCase
    ? evaluateCriteria(listCriteria(evalCase.pass_criteria), {
        response: result.final_response,
        needsEscalation: result.needs_escalation,
      }).filter((o) => o.status === "violated")
    : [];

  return (
    <div className="flex flex-col gap-2">
      <span className="font-mono font-medium text-[11px]">{model}</span>
      <p className="whitespace-pre-wrap rounded border border-[var(--border)] bg-[var(--muted)]/30 p-2.5 text-[11px] text-[var(--foreground)] leading-relaxed">
        {result.final_response || <span className="italic">{emptyLabel}</span>}
      </p>
      {violated.length > 0 ? (
        <div className="flex flex-col gap-1 rounded border border-danger-500/30 bg-danger-50 p-2 dark:bg-danger-700/10">
          <span className="font-medium text-[10px] text-danger-800 uppercase tracking-wide dark:text-danger-200">
            {brokeLabel}
          </span>
          <ul className="flex flex-col gap-1">
            {violated.map((o) => (
              <CriterionLine key={o.criterion.kind} criterion={o.criterion} locale={locale} />
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
