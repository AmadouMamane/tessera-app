import { EyeOff, ShieldOff, Unplug } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Card, CardContent } from "@/components/ui/card";
import type { EvalCase } from "@/lib/api/schemas";
import { coverageIsExpressible, passedBySilence } from "@/lib/eval-bench";
import { listCriteria } from "@/lib/eval-criteria";
import { type Floor, zeroPowerCategories } from "@/lib/eval-score";

/**
 * The bench's own blind spots, stated on the bench's own page.
 *
 * *Showing the holes in your own benchmark is the most complete form of the honesty doctrine.* All
 * three findings below are DERIVED from artefacts already committed — the case definitions, their
 * schema, and the null baseline. Nothing new is computed, nothing is guessed, and none of them
 * flatters the project.
 */
export async function BenchHonesty({
  catalogue,
  floor,
  categoryOf,
  caseSchemaFields,
  locale,
}: {
  catalogue: EvalCase[];
  floor: Floor | null;
  categoryOf: Readonly<Record<string, string>>;
  caseSchemaFields: string[];
  locale: string;
}) {
  const t = await getTranslations({ locale, namespace: "eval" });

  const weak = catalogue.filter((c) => passedBySilence(listCriteria(c.pass_criteria)));
  const zeroPower = floor ? zeroPowerCategories(floor, categoryOf) : [];
  // The floor's height, COUNTED from the verdicts this component already holds. The sentence
  // below used to say "the 70% floor" in the message catalogue while the committed floor was
  // re-measured to 124/174 (71.3%) — one half of the sentence interpolated, the other typed.
  const floorRuns = floor ? Object.values(floor.verdicts) : [];
  const floorPct = floorRuns.length
    ? Math.round((floorRuns.filter(Boolean).length / floorRuns.length) * 100)
    : null;
  const expressible = coverageIsExpressible(caseSchemaFields);
  const schemaUnreadable = caseSchemaFields.length === 0;

  return (
    <Card>
      <CardContent className="flex flex-col gap-4 p-5">
        <div className="flex flex-col gap-1">
          <h3 className="font-semibold text-base">{t("bench.title")}</h3>
          <p className="text-[var(--muted-foreground)] text-xs leading-relaxed">
            {t("bench.subtitle")}
          </p>
        </div>

        <ul className="flex flex-col gap-3">
          {/* §A1.8 — why the floor reaches 70%: the criteria are mostly negative. */}
          <Finding icon={<EyeOff className="h-4 w-4" />} title={t("bench.silence.title")}>
            <p>
              {t("bench.silence.body", {
                weak: weak.length,
                total: catalogue.length,
                floorPct: floorPct ?? "—",
              })}
            </p>
            {weak.length > 0 ? (
              <ul className="mt-1.5 flex flex-wrap gap-1">
                {weak.map((c) => (
                  <li
                    key={c.id}
                    className="rounded bg-warning-500/15 px-1.5 py-0.5 font-mono text-xs text-warning-800 dark:text-warning-200"
                  >
                    {c.id}
                  </li>
                ))}
              </ul>
            ) : null}
          </Finding>

          {/* §A1.7 / rule 3 — categories that cannot grade a model at all. Derived from the floor. */}
          <Finding icon={<ShieldOff className="h-4 w-4" />} title={t("bench.zeroPower.title")}>
            {zeroPower.length === 0 ? (
              <p>{t("bench.zeroPower.none")}</p>
            ) : (
              <p>
                {t("bench.zeroPower.body", {
                  categories: zeroPower.map((c) => t(`categories.${c}`)).join(", "),
                })}
              </p>
            )}
          </Finding>

          {/* The coverage map the dataset cannot draw — and the reason, which is worth more. */}
          <Finding icon={<Unplug className="h-4 w-4" />} title={t("bench.coverage.title")}>
            {schemaUnreadable ? (
              <p>{t("bench.coverage.schemaUnreadable")}</p>
            ) : expressible ? (
              <p>{t("bench.coverage.expressible")}</p>
            ) : (
              <p>{t("bench.coverage.inexpressible")}</p>
            )}
          </Finding>
        </ul>
      </CardContent>
    </Card>
  );
}

function Finding({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <li className="flex gap-3 border-warning-500/40 border-l-2 pl-3">
      <span className="mt-0.5 shrink-0 text-warning-600 dark:text-warning-400">{icon}</span>
      <div className="flex flex-col gap-0.5">
        <span className="font-medium text-sm">{title}</span>
        <div className="text-[var(--muted-foreground)] text-xs leading-relaxed">{children}</div>
      </div>
    </li>
  );
}
