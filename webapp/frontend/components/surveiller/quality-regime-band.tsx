"use client";

import { useQuery } from "@tanstack/react-query";
import { EyeOff, Gavel, Ruler } from "lucide-react";
import type { Route } from "next";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { fetchQualityRegimes } from "@/lib/api/client";
import type { QualityRegimeEntry } from "@/lib/api/schemas";

/**
 * The grouped-population band (ADR 0017 §Amendment 4): one row per declared quality
 * regime, each naming ITS population, ITS ruler and ITS counts — never summed with a
 * neighbour's. The hero above this band carries the LLM-judged plane's verdict; without
 * this band, its "0 of N judged responses" reads as "nothing else is measured" while a
 * second plane is measured by a stricter ruler two clicks away.
 *
 * Two constraints this component must keep:
 *  · it renders COUNTS only, never a rate — the only percentage on this screen belongs to
 *    the hero, whose population (judged responses) it names; a rate here would invite the
 *    cross-plane comparison the two-rulers rule forbids (insights 361-363);
 *  · it never reads the SLO query — the LLM plane's numbers stay in the hero, so the two
 *    populations cannot meet in one component's props, let alone one figure.
 */
const REGIME_ORDER = ["llm_judged", "business_scored", "unscored"] as const;

const REGIME_ICON = {
  llm_judged: Gavel,
  business_scored: Ruler,
  unscored: EyeOff,
} as const;

export function QualityRegimeBand() {
  const t = useTranslations("qualityRegimes");
  // The manifest reason keys live under the `quality_regime.` namespace (validated against
  // all three catalogues by the backend conformance gate, so a declared key always resolves).
  const tReason = useTranslations("quality_regime");
  const { data } = useQuery({
    queryKey: ["quality-regimes"],
    queryFn: ({ signal }) => fetchQualityRegimes(signal),
    staleTime: 60_000,
  });
  if (!data) return null;

  const byRegime = new Map<string, QualityRegimeEntry[]>();
  for (const entry of data.regimes) {
    const bucket = byRegime.get(entry.regime) ?? [];
    bucket.push(entry);
    byRegime.set(entry.regime, bucket);
  }

  return (
    <section
      aria-label={t("title")}
      className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-4 py-3"
    >
      <div className="flex flex-wrap items-baseline gap-x-2">
        <h2 className="text-[0.8rem] font-semibold">{t("title")}</h2>
        <p className="text-[0.66rem] text-[var(--tessera-text-muted)]">{t("subtitle")}</p>
      </div>
      <ul className="mt-2 space-y-1.5">
        {REGIME_ORDER.map((regime) => {
          const entries = byRegime.get(regime);
          if (!entries || entries.length === 0) return null;
          const Icon = REGIME_ICON[regime];
          const names = entries.map((entry) => entry.name).join(" · ");
          // One reason per distinct declared key — agents sharing a blind spot share a line.
          const reasonKeys =
            regime === "unscored"
              ? [...new Set(entries.map((e) => e.reason_key).filter((k): k is string => !!k))]
              : [];
          return (
            <li key={regime} className="flex items-start gap-2.5">
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-muted)] text-[var(--tessera-text-muted)]">
                <Icon className="h-3.5 w-3.5" aria-hidden />
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-baseline gap-x-2">
                  <span className="text-[0.72rem] font-medium">{t(`${regime}.label`)}</span>
                  <span className="text-[0.66rem] text-[var(--tessera-text-muted)]">{names}</span>
                  {regime === "llm_judged" ? (
                    <span className="text-[0.66rem] text-[var(--tessera-text-muted)]">
                      {t("llm_judged.note")}
                    </span>
                  ) : null}
                </span>
                {regime === "business_scored"
                  ? entries.map((entry) =>
                      entry.business ? (
                        <span
                          key={entry.agent_id}
                          className="mt-0.5 flex flex-wrap items-baseline gap-x-2 text-[0.66rem] text-[var(--tessera-text-muted)]"
                        >
                          <span className="tabular-nums">
                            {t("business_scored.counts", {
                              runs: entry.business.runs_total,
                              declared: entry.business.signals_declared,
                              scored: entry.business.signals_scored,
                              unknown: entry.business.signals_unknown,
                              na: entry.business.signals_not_applicable,
                            })}
                          </span>
                          <Link
                            href={`/agents/${entry.agent_id}/metier` as Route}
                            className="font-medium text-[var(--tessera-fg-accent)] transition-colors hover:text-[var(--tessera-text-strong)]"
                          >
                            {t("business_scored.link")} →
                          </Link>
                        </span>
                      ) : null,
                    )
                  : null}
                {reasonKeys.map((key) => (
                  <span
                    key={key}
                    className="mt-0.5 block text-[0.66rem] text-[var(--tessera-text-muted)]"
                  >
                    {tReason(key.slice("quality_regime.".length))}
                  </span>
                ))}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
