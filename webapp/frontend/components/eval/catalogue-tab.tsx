import { BookOpen, ChevronRight, ExternalLink, ShieldAlert } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { CriterionLine } from "@/components/eval/criterion-line";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Link } from "@/i18n/navigation";
import type { EvalCase } from "@/lib/api/schemas";
import { listCriteria } from "@/lib/eval-criteria";

/**
 * `Jeu de cas` — the dataset as a versioned ARTEFACT, with no result anywhere on it.
 *
 * This is the answer to "did you invent your own benchmark?". Every case carries the source it
 * was derived from (OWASP LLM Top 10, DORA, CNIL…) with its link, and the citation is the proof —
 * exactly as the ADR corpus is the proof for the architecture. That evidence was sitting in
 * `eval/failures/*.json` and no surface had ever shown it.
 */
export async function CatalogueTab({
  catalogue,
  version,
  locale,
}: {
  catalogue: EvalCase[];
  version: string | null;
  locale: string;
}) {
  const t = await getTranslations({ locale, namespace: "eval" });

  if (catalogue.length === 0) {
    return (
      <Card>
        <CardContent className="p-6">
          <EmptyState
            icon={<BookOpen />}
            title={t("catalogue.empty.title")}
            description={t("catalogue.empty.body")}
          />
        </CardContent>
      </Card>
    );
  }

  const byCategory = new Map<string, EvalCase[]>();
  for (const c of catalogue) {
    const bucket = byCategory.get(c.category);
    if (bucket) bucket.push(c);
    else byCategory.set(c.category, [c]);
  }
  const categories = [...byCategory.entries()].sort((a, b) => b[1].length - a[1].length);

  return (
    <div className="flex flex-col gap-5">
      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 p-5">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-gold-600 dark:text-gold-400" />
              <h2 className="font-semibold text-base">{t("catalogue.title")}</h2>
            </div>
            <p className="text-[var(--muted-foreground)] text-xs leading-relaxed">
              {t("catalogue.subtitle")}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="navy" className="font-mono">
              {version ?? "—"}
            </Badge>
            <Badge tone="neutral">
              {t("catalogue.count", { cases: catalogue.length, categories: categories.length })}
            </Badge>
            <Link
              href="/agir/curation-eval-set"
              className="inline-flex items-center gap-1 text-[var(--muted-foreground)] text-xs underline-offset-4 hover:text-[var(--foreground)] hover:underline"
            >
              {t("catalogue.curationLink")}
              <ChevronRight className="h-3 w-3" />
            </Link>
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3">
        {categories.map(([category, cases]) => (
          <Card key={category}>
            <details className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 p-4">
                <span className="flex items-center gap-2.5">
                  <ChevronRight className="h-4 w-4 shrink-0 text-[var(--muted-foreground)] transition-transform group-open:rotate-90" />
                  <span className="font-medium text-sm">{t(`categories.${category}`)}</span>
                </span>
                <Badge tone="neutral" className="tabular-nums">
                  {t("catalogue.caseCount", { count: cases.length })}
                </Badge>
              </summary>
              <div className="flex flex-col gap-3 border-[var(--border)] border-t p-4">
                {cases.map((c) => (
                  <CaseSheet key={c.id} evalCase={c} locale={locale} />
                ))}
              </div>
            </details>
          </Card>
        ))}
      </div>
    </div>
  );
}

/** One case, on the DEFINITION side: what it demands, in which languages, and why it exists. */
async function CaseSheet({ evalCase, locale }: { evalCase: EvalCase; locale: string }) {
  const t = await getTranslations({ locale, namespace: "eval" });
  const criteria = listCriteria(evalCase.pass_criteria);
  const source = evalCase.source_reference;
  const url = source.url ?? source.urls[0];

  return (
    <details className="group/case rounded-md border border-[var(--border)] bg-[var(--muted)]/20">
      <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-1.5 p-3">
        <ChevronRight className="h-3.5 w-3.5 shrink-0 text-[var(--muted-foreground)] transition-transform group-open/case:rotate-90" />
        <span className="font-mono text-[11px] text-[var(--muted-foreground)]">{evalCase.id}</span>
        <span className="flex-1 text-sm">{evalCase.title}</span>
        {evalCase.severity === "critical" ? (
          <Badge tone="danger" className="gap-1">
            <ShieldAlert className="h-3 w-3" />
            {t("catalogue.severity.critical")}
          </Badge>
        ) : null}
        <span className="flex items-center gap-1 font-mono text-[10px] text-[var(--muted-foreground)] uppercase">
          {evalCase.languages.join(" · ")}
        </span>
      </summary>

      <div className="flex flex-col gap-4 border-[var(--border)] border-t p-4 text-sm">
        <Section title={t("catalogue.expected")}>
          <p className="text-[var(--muted-foreground)] leading-relaxed">
            {evalCase.expected_behavior}
          </p>
        </Section>

        <Section title={t("catalogue.criteria")}>
          {criteria.length === 0 ? (
            <p className="text-[var(--muted-foreground)] text-xs italic">
              {t("catalogue.noCriteria")}
            </p>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {criteria.map((criterion) => (
                <CriterionLine key={criterion.kind} criterion={criterion} locale={locale} />
              ))}
            </ul>
          )}
        </Section>

        <Section title={t("catalogue.prompts")}>
          <ul className="flex flex-col gap-2">
            {evalCase.languages.map((lang) => {
              const prompt = evalCase.prompts[lang];
              if (!prompt) return null;
              return (
                <li key={lang} className="flex gap-2.5">
                  <span className="mt-0.5 shrink-0 rounded bg-[var(--muted)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--muted-foreground)] uppercase">
                    {lang}
                  </span>
                  <span className="text-[var(--muted-foreground)] text-xs leading-relaxed">
                    {prompt.user}
                  </span>
                </li>
              );
            })}
          </ul>
        </Section>

        {/* The citation IS the proof the bench was not invented. It is the point of this tab. */}
        <Section title={t("catalogue.source")}>
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
          {source.notes ? (
            <p className="mt-1 text-[11px] text-[var(--muted-foreground)] italic leading-relaxed">
              {source.notes}
            </p>
          ) : null}
        </Section>

        {evalCase.tags.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {evalCase.tags.map((tag) => (
              <span
                key={tag}
                className="rounded-full bg-[var(--muted)] px-2 py-0.5 font-mono text-[10px] text-[var(--muted-foreground)]"
              >
                {tag}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </details>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <h4 className="font-medium text-[11px] text-[var(--muted-foreground)] uppercase tracking-wide">
        {title}
      </h4>
      {children}
    </div>
  );
}
