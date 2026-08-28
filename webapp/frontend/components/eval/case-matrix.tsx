import { getTranslations } from "next-intl/server";

import { EVAL_PATHNAME, evalQuery } from "@/components/eval/eval-route";
import { Card, CardContent } from "@/components/ui/card";
import { Link } from "@/i18n/navigation";
import type { EvalCase } from "@/lib/api/schemas";
import { type CaseKey, type CellState, caseKey, cellState } from "@/lib/eval-score";

/**
 * The case × language matrix — the most important change on this screen (§A1.5).
 *
 * A run is not a pass/fail total (criterion 3), and a green cell is not a model's achievement.
 * `policy_violation` is 15/15 AT THE FLOOR: the guard closes every one of them with no model at
 * all. An operator reading a wall of green has no way to tell the guard's reliability from the
 * model's competence — unless the screen SHOWS the difference. So it does, in three states:
 *
 *   · passed by the GUARD  — the floor holds it alone, the model proves nothing here
 *   · passed by the MODEL  — the floor fails it, the model closes it. The only cells that grade it.
 *   · BROKEN by the model  — the floor passed it and the model broke it. Worse than no model.
 *
 * A model can pass in French and fail in German — that is what the `language_mixing` category
 * exists to catch, and it is invisible in any per-case total.
 */
const CELL_CLASS: Record<CellState, string> = {
  // Muted, outlined: green, but nothing to do with the model.
  "floor-pass":
    "border border-success-500/40 bg-transparent text-success-700/70 dark:text-success-400/60",
  // Solid: the model earned this one. OPAQUE and at the 700 shade, like the red cell
  // below: at `success-500/80` the white glyph scored 1.9:1 on a light card — under even
  // the 3:1 WCAG asks of non-text content — because 80 % of a bright green over white is
  // a bright green. The darker, fully opaque fill reads on both themes.
  "model-pass": "border border-transparent bg-success-700 font-semibold text-white",
  // Bright red, filled: a regression against having no model at all.
  "model-break": "border border-danger-500 bg-danger-500 font-semibold text-white",
  // Neither closes it.
  "both-fail": "border border-[var(--border)] bg-[var(--muted)]/60 text-[var(--muted-foreground)]",
  // Not in the floor. Never guessed.
  unknown:
    "border border-dashed border-[var(--border)] bg-transparent text-[var(--muted-foreground)]",
};

const CELL_GLYPH: Record<CellState, string> = {
  "floor-pass": "✓",
  "model-pass": "✓",
  "model-break": "✗",
  "both-fail": "✗",
  unknown: "?",
};

const LANGS = ["fr", "de", "en"] as const;

export async function CaseMatrix({
  catalogue,
  runVerdicts,
  floorVerdicts,
  runId,
  selected,
  locale,
}: {
  catalogue: EvalCase[];
  runVerdicts: Readonly<Record<CaseKey, boolean>>;
  floorVerdicts: Readonly<Record<CaseKey, boolean>> | null;
  runId: string;
  selected: { caseId: string; lang: string } | null;
  locale: string;
}) {
  const t = await getTranslations({ locale, namespace: "eval" });

  const byCategory = new Map<string, EvalCase[]>();
  for (const c of catalogue) {
    const bucket = byCategory.get(c.category);
    if (bucket) bucket.push(c);
    else byCategory.set(c.category, [c]);
  }

  return (
    <Card>
      <CardContent className="flex flex-col gap-4 p-5">
        <div className="flex flex-col gap-1">
          <h3 className="font-semibold text-base">{t("matrix.title")}</h3>
          <p className="text-[var(--muted-foreground)] text-xs leading-relaxed">
            {t("matrix.subtitle")}
          </p>
        </div>

        <Legend
          labels={{
            floorPass: t("matrix.legend.floorPass"),
            modelPass: t("matrix.legend.modelPass"),
            modelBreak: t("matrix.legend.modelBreak"),
            bothFail: t("matrix.legend.bothFail"),
          }}
        />

        {!floorVerdicts ? (
          <p className="rounded-md border border-warning-500/30 bg-warning-50 p-2.5 text-warning-800 text-xs dark:bg-warning-700/15 dark:text-warning-100">
            {t("matrix.noFloor")}
          </p>
        ) : null}

        <div className="flex flex-col gap-4">
          {[...byCategory.entries()].map(([category, cases]) => (
            <section key={category} className="flex flex-col gap-1.5">
              <h4 className="font-medium text-xs text-[var(--muted-foreground)] uppercase tracking-wide">
                {t(`categories.${category}`)}
              </h4>
              <ul className="flex flex-col gap-1">
                {cases.map((c) => (
                  <li key={c.id} className="flex items-center gap-2">
                    <span className="w-[13rem] shrink-0 truncate font-mono text-xs text-[var(--muted-foreground)]">
                      {c.id}
                    </span>
                    <span className="hidden flex-1 truncate text-[var(--muted-foreground)] text-xs lg:block">
                      {c.title}
                    </span>
                    <span className="flex shrink-0 gap-1">
                      {LANGS.map((lang) => (
                        <Cell
                          key={lang}
                          evalCase={c}
                          lang={lang}
                          runId={runId}
                          runVerdicts={runVerdicts}
                          floorVerdicts={floorVerdicts}
                          isSelected={selected?.caseId === c.id && selected.lang === lang}
                        />
                      ))}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function Cell({
  evalCase,
  lang,
  runId,
  runVerdicts,
  floorVerdicts,
  isSelected,
}: {
  evalCase: EvalCase;
  lang: string;
  runId: string;
  runVerdicts: Readonly<Record<CaseKey, boolean>>;
  floorVerdicts: Readonly<Record<CaseKey, boolean>> | null;
  isSelected: boolean;
}) {
  const key = caseKey(evalCase.id, lang);

  // A case declares its languages. `18_hallucination_taux_livret_a` is French only, and an empty
  // cell there is the CATALOGUE saying "not asked in German" — not the model failing to answer.
  if (!evalCase.languages.includes(lang as "fr" | "de" | "en") || runVerdicts[key] === undefined) {
    return (
      <span
        aria-hidden
        className="flex h-7 w-9 items-center justify-center rounded text-[var(--muted-foreground)]/40 text-xs"
      >
        ·
      </span>
    );
  }

  const state: CellState = floorVerdicts ? cellState(key, runVerdicts, floorVerdicts) : "unknown";

  return (
    <Link
      href={{
        pathname: EVAL_PATHNAME,
        query: evalQuery({ tab: "runs", run: runId, case: evalCase.id, lang }),
      }}
      scroll={false}
      aria-label={`${evalCase.id} ${lang}`}
      title={`${evalCase.id} · ${lang}`}
      className={`flex h-7 w-9 items-center justify-center rounded text-xs transition-all hover:scale-110 ${CELL_CLASS[state]} ${
        isSelected ? "ring-2 ring-gold-500 ring-offset-1 ring-offset-[var(--card)]" : ""
      }`}
    >
      <span className="sr-only">{lang}</span>
      <span aria-hidden>{CELL_GLYPH[state]}</span>
    </Link>
  );
}

function Legend({
  labels,
}: {
  labels: { floorPass: string; modelPass: string; modelBreak: string; bothFail: string };
}) {
  const items: [CellState, string][] = [
    ["floor-pass", labels.floorPass],
    ["model-pass", labels.modelPass],
    ["model-break", labels.modelBreak],
    ["both-fail", labels.bothFail],
  ];
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-2">
      {items.map(([state, label]) => (
        <li key={state} className="flex items-center gap-1.5">
          <span
            aria-hidden
            className={`flex h-5 w-7 items-center justify-center rounded text-xs ${CELL_CLASS[state]}`}
          >
            {CELL_GLYPH[state]}
          </span>
          <span className="text-[var(--muted-foreground)] text-xs">{label}</span>
        </li>
      ))}
    </ul>
  );
}
