import { AlertTriangle, Ban, CircleSlash, ShieldCheck, TrendingUp } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { ScoreCard as ScoreCardModel } from "@/lib/eval-score";

/**
 * THE score component. Every score on this screen goes through it, and it is the reason no raw
 * rate can survive here: it has no branch that renders one.
 *
 * "157/174" is not a grade. It sums the deterministic floor the guard holds with no model at all
 * (122) and what the model contributes on top (+36) — two quantities of different natures. The
 * 2026-07-12 sweep settles it: `llama3.2:3b` and `gemma3:27b` both land on 157/174, and one of
 * them makes the agent WORSE than having no model, while the other does not. Publishing the sum
 * alone is not a fabricated number — every term of it is true — it is worse: it is true and it
 * misleads, which is the failure this project refuses everywhere else.
 *
 * So the absolute is shown only inside the decomposition, labelled as what it is, and the three
 * honest-empties (no model spoke / no committed floor / another référentiel) render a SENTENCE,
 * never a zero. A run with no model showing "0 regressions" would read as a commendation.
 */
export async function ScoreCard({
  card,
  locale,
  runAt,
  className,
}: {
  card: ScoreCardModel;
  locale: string;
  runAt?: string | null;
  className?: string;
}) {
  const t = await getTranslations({ locale, namespace: "eval" });
  const pct = (value: number, of: number) =>
    of === 0 ? "—" : new Intl.NumberFormat(locale, { style: "percent" }).format(value / of);

  const header = (
    <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
      <span className="font-mono font-semibold text-base text-[var(--foreground)]">
        {card.model ?? t("score.unnamedModel")}
      </span>
      {runAt ? (
        <span className="font-mono text-xs text-[var(--muted-foreground)]">{runAt}</span>
      ) : null}
    </div>
  );

  if (card.kind === "no-model") {
    return (
      <HonestEmpty
        className={className}
        header={header}
        icon={<CircleSlash className="h-4 w-4" />}
        title={t("score.noModel.title")}
        body={t("score.noModel.body")}
      />
    );
  }

  if (card.kind === "no-floor") {
    return (
      <HonestEmpty
        className={className}
        header={header}
        icon={<CircleSlash className="h-4 w-4" />}
        title={t("score.noFloor.title")}
        body={t("score.noFloor.body")}
      />
    );
  }

  if (card.kind === "off-referential") {
    return (
      <HonestEmpty
        className={className}
        header={header}
        icon={<AlertTriangle className="h-4 w-4" />}
        title={t("score.offReferential.title")}
        body={t("score.offReferential.body", {
          run: card.runVersion ?? t("score.unstamped"),
          floor: card.floorVersion ?? t("score.unstamped"),
        })}
      />
    );
  }

  const blocked = card.verdict === "block";
  const brokeRule1 = card.candidateBreaks.length > 0;
  const firstReason = card.reasons[0];

  return (
    <Card className={className}>
      <CardContent className="flex flex-col gap-3.5 p-5">
        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
          <div className="flex flex-col gap-0.5">{header}</div>
          <Badge tone={blocked ? "danger" : "success"} className="gap-1.5">
            {blocked ? <Ban className="h-3 w-3" /> : <ShieldCheck className="h-3 w-3" />}
            {blocked ? t("score.verdict.block") : t("score.verdict.pass")}
            {firstReason ? (
              <span className="font-normal opacity-80">
                · {t("score.rule", { n: firstReason.rule })}
              </span>
            ) : null}
          </Badge>
        </div>

        {/* The absolute, and the sentence that strips it of authority. It is never alone. */}
        <div className="flex items-baseline gap-2.5 border-[var(--border)] border-b pb-3">
          <span className="font-serif font-semibold text-2xl tabular-nums">
            {card.absolute.passed}/{card.absolute.total}
          </span>
          <span className="text-xs text-[var(--muted-foreground)] uppercase tracking-wide">
            {t("score.absoluteIsNotTheGrade")}
          </span>
        </div>

        <ul className="flex flex-col gap-2.5 text-sm">
          <Term
            icon={<ShieldCheck className="h-3.5 w-3.5 text-[var(--muted-foreground)]" />}
            label={t("score.floor")}
            value={String(card.floor)}
            hint={t("score.floorHint")}
          />
          <Term
            icon={<TrendingUp className="h-3.5 w-3.5 text-info-600 dark:text-info-400" />}
            label={t("score.contribution")}
            value={`+${card.contribution}`}
            valueClass="text-info-700 dark:text-info-300"
            hint={t("score.contributionHint", {
              population: card.contributionPopulation,
              rate: pct(card.contribution, card.contributionPopulation),
            })}
          />
          {brokeRule1 ? (
            <Term
              icon={<AlertTriangle className="h-3.5 w-3.5 text-danger-600 dark:text-danger-400" />}
              label={t("score.breaks")}
              value={String(card.candidateBreaks.length)}
              valueClass="text-danger-700 dark:text-danger-300"
              hint={t("score.breaksCandidate")}
              detail={card.candidateBreaks}
            />
          ) : (
            <Term
              icon={<ShieldCheck className="h-3.5 w-3.5 text-success-600 dark:text-success-400" />}
              label={t("score.breaksNone")}
              value="0"
              valueClass="text-success-700 dark:text-success-300"
              hint={t("score.breaksNoneHint")}
            />
          )}
        </ul>

        {/* The bar is a reasoned choice, not a measurement, and it says so wherever it appears. */}
        {card.minContribution !== null ? (
          <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
            {t("score.uncalibrated", { min: card.minContribution })}
          </p>
        ) : (
          <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
            {t("score.rule2NotGated")}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function Term({
  icon,
  label,
  value,
  valueClass,
  hint,
  detail,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  valueClass?: string;
  hint: string;
  detail?: string[];
}) {
  return (
    <li className="flex flex-col gap-1 border-[var(--border)] border-l-2 pl-3">
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className="flex items-center gap-1.5 self-center">{icon}</span>
        <span className="text-[var(--foreground)]">{label}</span>
        <span className={`font-semibold tabular-nums ${valueClass ?? ""}`}>{value}</span>
        <span className="text-[var(--muted-foreground)] text-xs">{hint}</span>
      </div>
      {detail?.length ? (
        <ul className="flex flex-col gap-0.5">
          {detail.map((key) => (
            <li key={key} className="font-mono text-xs text-danger-700 dark:text-danger-300">
              {key}
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

/** A sentence, never a zero. */
function HonestEmpty({
  header,
  icon,
  title,
  body,
  className,
}: {
  header: React.ReactNode;
  icon: React.ReactNode;
  title: string;
  body: string;
  className?: string;
}) {
  return (
    <Card className={className}>
      <CardContent className="flex flex-col gap-2.5 p-5">
        {header}
        <div className="flex items-center gap-2 text-[var(--muted-foreground)]">
          {icon}
          <span className="font-medium text-sm text-[var(--foreground)]">{title}</span>
        </div>
        <p className="text-[var(--muted-foreground)] text-xs leading-relaxed">{body}</p>
      </CardContent>
    </Card>
  );
}
