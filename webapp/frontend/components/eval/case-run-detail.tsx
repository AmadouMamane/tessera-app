import { AlertTriangle, Check, Clock, ExternalLink, Hash, Wrench, X } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { CriterionLine } from "@/components/eval/criterion-line";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { EvalCase, ScorecardResult } from "@/lib/api/schemas";
import {
  type CriterionOutcome,
  evaluateCriteria,
  listCriteria,
  segmentByHits,
} from "@/lib/eval-criteria";
import type { CellState } from "@/lib/eval-score";

/**
 * One executed case: the whole evidence chain behind a single verdict.
 *
 * "Failed" is not an answer. The screen owes the operator WHICH criterion broke and ON WHAT, and
 * both are available: the report keeps the model's real response, and the catalogue keeps the rule.
 * So the criterion is RECOMPUTED here from the two of them, and the offending substring is pointed
 * at inside the response — "it emitted `FR76 3000 4000 5000 6000 7000 123`, forbidden by
 * must_not_contain". Zero change to the harness: the proof was always reconstructible.
 *
 * What it will NOT do is reconstruct a criterion it cannot see. The confidence, the retrieved
 * citations and each tool call's success flag are not in the report; the harness checked them, and
 * for those the screen shows the harness's own reason, labelled as reported rather than verified.
 * A reconstruction that cannot see the same inputs is not evidence.
 */
export async function CaseRunDetail({
  evalCase,
  result,
  state,
  locale,
  recomputable,
}: {
  evalCase: EvalCase | null;
  result: ScorecardResult;
  state: CellState;
  locale: string;
  /**
   * False when the case set moved since this run: the definition on disk is no longer the one the
   * run was scored against, so recomputing against it would produce a criterion that never applied.
   */
  recomputable: boolean;
}) {
  const t = await getTranslations({ locale, namespace: "eval" });

  const criteria = listCriteria(evalCase?.pass_criteria);
  const outcomes =
    recomputable && evalCase
      ? evaluateCriteria(criteria, {
          response: result.final_response,
          needsEscalation: result.needs_escalation,
        })
      : [];

  const violated = outcomes.filter((o) => o.status === "violated");
  const notVerifiable = outcomes.filter((o) => o.status === "not-verifiable");
  const spans = violated.flatMap((o) => o.spans);
  const prompt = evalCase?.prompts[result.language]?.user ?? null;
  const source = evalCase?.source_reference ?? null;
  const url = source?.url ?? source?.urls[0];

  return (
    <Card id="case-detail" className="scroll-mt-4">
      <CardContent className="flex flex-col gap-5 p-5">
        <header className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="font-mono text-xs text-[var(--muted-foreground)]">{result.case_id}</span>
          <span className="rounded bg-[var(--muted)] px-1.5 py-0.5 font-mono text-xs uppercase">
            {result.language}
          </span>
          <span className="flex-1 font-medium text-sm">{result.title || evalCase?.title}</span>
          <StateBadge state={state} passed={result.passed} t={t} />
        </header>

        {/* 1 — the prompt actually sent, in the language of the cell */}
        <Block title={t("detail.prompt")}>
          {prompt ? (
            <p className="rounded-md border border-[var(--border)] bg-[var(--muted)]/30 p-3 text-[var(--foreground)] text-xs leading-relaxed">
              {prompt}
            </p>
          ) : (
            <Empty>{t("detail.noPrompt")}</Empty>
          )}
        </Block>

        {/* 2 — the model's real response, with what broke it highlighted in place */}
        <Block title={t("detail.response")}>
          {result.final_response ? (
            <p className="whitespace-pre-wrap rounded-md border border-[var(--border)] bg-[var(--muted)]/30 p-3 text-[var(--foreground)] text-xs leading-relaxed">
              {segmentByHits(result.final_response, spans).map((segment) =>
                segment.hit ? (
                  <mark
                    key={segment.start}
                    className="rounded-sm bg-danger-500/25 px-0.5 font-semibold text-danger-800 dark:text-danger-200"
                  >
                    {segment.text}
                  </mark>
                ) : (
                  <span key={segment.start}>{segment.text}</span>
                ),
              )}
            </p>
          ) : (
            // An empty response is a FACT about the run, and §A1.8's whole point: a system that says
            // nothing satisfies every negative criterion. It is never rendered as "no data".
            <Empty>{t("detail.emptyResponse")}</Empty>
          )}
        </Block>

        {/* 3 — THE criterion that broke, recomputed, with what decided it */}
        <Block title={t("detail.criterion")}>
          {!recomputable ? (
            <Empty>{t("detail.notRecomputable")}</Empty>
          ) : violated.length > 0 ? (
            <ul className="flex flex-col gap-2">
              {violated.map((outcome) => (
                <li
                  key={outcome.criterion.kind}
                  className="flex flex-col gap-1.5 rounded-md border border-danger-500/30 bg-danger-50 p-3 dark:bg-danger-700/10"
                >
                  <span className="flex items-center gap-1.5 font-medium text-danger-800 text-xs dark:text-danger-200">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    {t("detail.brokeBy")}
                  </span>
                  <ul>
                    <CriterionLine criterion={outcome.criterion} locale={locale} />
                  </ul>
                  {outcome.decidedBy.length > 0 ? (
                    <p className="text-danger-800 text-xs leading-relaxed dark:text-danger-200">
                      {t("detail.emitted")}{" "}
                      {outcome.decidedBy.map((v) => (
                        <code
                          key={v}
                          className="rounded bg-danger-500/20 px-1 py-0.5 font-mono text-xs"
                        >
                          {v}
                        </code>
                      ))}
                    </p>
                  ) : (
                    <p className="text-danger-800 text-xs leading-relaxed dark:text-danger-200">
                      {t("detail.brokeByAbsence")}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          ) : result.passed ? (
            <p className="flex items-center gap-1.5 text-[var(--muted-foreground)] text-xs">
              <Check className="h-3.5 w-3.5 text-success-600" />
              {t("detail.allSatisfied")}
            </p>
          ) : (
            // The harness failed it on something this screen cannot re-verify. Say so, and show
            // what the harness itself wrote — never a silent "no reason found".
            <Empty>{t("detail.failedOnUnverifiable")}</Empty>
          )}

          {/* The harness's own words, always available, always labelled as REPORTED. */}
          {result.reasons.length > 0 ? (
            <div className="mt-2 flex flex-col gap-1">
              <span className="font-medium text-xs text-[var(--muted-foreground)] uppercase tracking-wide">
                {t("detail.harnessReasons")}
              </span>
              <ul className="flex flex-col gap-1">
                {result.reasons.map((reason) => (
                  <li
                    key={reason}
                    className="rounded bg-[var(--muted)]/40 px-2 py-1 font-mono text-xs text-[var(--muted-foreground)] leading-relaxed"
                  >
                    {reason}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {notVerifiable.length > 0 ? (
            <div className="mt-2 flex flex-col gap-1.5">
              <span className="font-medium text-xs text-[var(--muted-foreground)] uppercase tracking-wide">
                {t("detail.notVerifiableHere")}
              </span>
              <ul className="flex flex-col gap-1">
                {notVerifiable.map((outcome) => (
                  <CriterionLine
                    key={outcome.criterion.kind}
                    criterion={outcome.criterion}
                    locale={locale}
                  />
                ))}
              </ul>
              <p className="text-xs text-[var(--muted-foreground)] italic leading-relaxed">
                {t("detail.notVerifiableWhy")}
              </p>
            </div>
          ) : null}
        </Block>

        {/* 4 — execution context */}
        <Block title={t("detail.context")}>
          <ul className="flex flex-wrap gap-x-6 gap-y-2 text-xs">
            <Fact icon={<Wrench className="h-3.5 w-3.5" />} label={t("detail.tools")}>
              {result.invoked_tools.length > 0 ? (
                <span className="flex flex-wrap gap-1">
                  {result.invoked_tools.map((tool) => (
                    <code
                      key={tool}
                      className="rounded bg-[var(--muted)] px-1.5 py-0.5 font-mono text-xs"
                    >
                      {tool}
                    </code>
                  ))}
                </span>
              ) : (
                <span className="text-[var(--muted-foreground)]">{t("detail.noTool")}</span>
              )}
            </Fact>
            <Fact icon={<AlertTriangle className="h-3.5 w-3.5" />} label={t("detail.escalation")}>
              {result.needs_escalation ? t("detail.yes") : t("detail.no")}
            </Fact>
            <Fact icon={<Clock className="h-3.5 w-3.5" />} label={t("detail.duration")}>
              {result.duration_ms === null
                ? t("detail.notRecorded")
                : `${Math.round(result.duration_ms)} ms`}
            </Fact>
            <Fact icon={<Hash className="h-3.5 w-3.5" />} label={t("detail.tokens")}>
              {result.output_tokens === null ? (
                t("detail.notRecorded")
              ) : (
                <span className="tabular-nums">
                  {result.input_tokens ?? 0} in · {result.output_tokens} out
                </span>
              )}
            </Fact>
          </ul>
        </Block>

        {/* 5 — why this test exists at all */}
        {source ? (
          <Block title={t("detail.source")}>
            <p className="text-[var(--muted-foreground)] text-xs leading-relaxed">
              {url ? (
                <a
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-baseline gap-1 text-info-700 underline-offset-4 hover:underline dark:text-info-300"
                >
                  {source.citation}
                  <ExternalLink className="h-3 w-3 shrink-0 self-center" />
                </a>
              ) : (
                source.citation
              )}
            </p>
          </Block>
        ) : null}
      </CardContent>
    </Card>
  );
}

function StateBadge({
  state,
  passed,
  t,
}: {
  state: CellState;
  passed: boolean;
  t: (key: string) => string;
}) {
  if (state === "model-break") {
    return (
      <Badge tone="danger" className="gap-1">
        <X className="h-3 w-3" />
        {t("matrix.legend.modelBreak")}
      </Badge>
    );
  }
  if (state === "model-pass") {
    return (
      <Badge tone="success" className="gap-1">
        <Check className="h-3 w-3" />
        {t("matrix.legend.modelPass")}
      </Badge>
    );
  }
  if (state === "floor-pass") {
    return (
      <Badge tone="neutral" className="gap-1">
        <Check className="h-3 w-3" />
        {t("matrix.legend.floorPass")}
      </Badge>
    );
  }
  return (
    <Badge tone={passed ? "success" : "danger"} className="gap-1">
      {passed ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
      {passed ? t("passed") : t("matrix.legend.bothFail")}
    </Badge>
  );
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-1.5">
      <h4 className="font-medium text-xs text-[var(--muted-foreground)] uppercase tracking-wide">
        {title}
      </h4>
      {children}
    </section>
  );
}

function Fact({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <li className="flex items-center gap-1.5">
      <span className="text-[var(--muted-foreground)]">{icon}</span>
      <span className="text-[var(--muted-foreground)]">{label}</span>
      <span className="text-[var(--foreground)]">{children}</span>
    </li>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-md border border-[var(--border)] border-dashed bg-transparent p-3 text-[var(--muted-foreground)] text-xs italic leading-relaxed">
      {children}
    </p>
  );
}

export type { CriterionOutcome };
