import { getTranslations } from "next-intl/server";

import type { Criterion } from "@/lib/eval-criteria";

/**
 * One pass criterion, rendered readably — "must never contain: FR76 3000…" rather than a JSON key.
 *
 * Shared between the case sheet (what the bench DEMANDS) and the executed case (what the model DID
 * about it), so the two surfaces cannot end up describing the same rule in two different ways.
 */
export async function CriterionLine({
  criterion,
  locale,
}: {
  criterion: Criterion;
  locale: string;
}) {
  const t = await getTranslations({ locale, namespace: "eval" });

  const label =
    criterion.kind === "must_escalate"
      ? criterion.scalar === true
        ? t("criteria.must_escalate")
        : t("criteria.must_not_escalate")
      : t(`criteria.${criterion.kind}`);

  return (
    <li className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-xs">
      <span className="text-[var(--foreground)]">{label}</span>
      {criterion.values.length > 0 ? (
        <span className="flex flex-wrap gap-1">
          {criterion.values.map((value) => (
            <code
              key={value}
              className="rounded bg-[var(--muted)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--muted-foreground)]"
            >
              {value}
            </code>
          ))}
        </span>
      ) : null}
      {typeof criterion.scalar === "number" ? (
        <code className="rounded bg-[var(--muted)] px-1.5 py-0.5 font-mono text-[11px] tabular-nums">
          {criterion.scalar}
        </code>
      ) : null}
    </li>
  );
}
