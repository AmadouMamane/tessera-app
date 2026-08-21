"use client";

import { useQuery } from "@tanstack/react-query";
import { EyeOff, Gavel, Ruler } from "lucide-react";
import type { Route } from "next";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { fetchQualityRegimes } from "@/lib/api/client";
import type { QualityRegimeEntry } from "@/lib/api/schemas";

/**
 * The answer-quality rating band (ADR 0017 §Amendment 4): one row per declared rating
 * method, each naming ITS agents and ITS counts — never blended with a neighbour's. The
 * subtitle states the scope honestly: cross-cutting controls (security, compliance, cost)
 * cover EVERY agent; what differs per agent is only how its ANSWERS are rated.
 *
 * Constraints this component must keep:
 *  · it renders COUNTS only, never a rate — the only percentage on this screen belongs to
 *    the hero, whose sample it names; a rate here would invite the cross-method
 *    comparison the two-rulers rule forbids (insights 361-363);
 *  · it never reads the SLO query — the judge's numbers stay in the hero, so the two
 *    samples cannot meet in one component's props, let alone one figure;
 *  · it stays legible at fleet scale: names cap at {@link MAX_NAMES} with a "+N more"
 *    overflow, detailed business lines cap at {@link MAX_BUSINESS_LINES} — 200 agents
 *    render as counts, never as 200 names.
 */
const REGIME_ORDER = ["llm_judged", "business_scored", "unscored"] as const;

const REGIME_ICON = {
  llm_judged: Gavel,
  business_scored: Ruler,
  unscored: EyeOff,
} as const;

/** Names shown inline per row before collapsing into "+N more". */
const MAX_NAMES = 4;
/** Detailed per-agent count lines on the business row before collapsing. */
const MAX_BUSINESS_LINES = 3;

export function QualityRegimeBand() {
  const t = useTranslations("qualityRegimes");
  // The manifest reason keys live under the `quality_regime.` namespace (validated against
  // all three catalogues by the backend conformance gate, so a declared key always resolves).
  const tReason = useTranslations("quality_regime");
  const { data, isError } = useQuery({
    queryKey: ["quality-regimes"],
    queryFn: ({ signal }) => fetchQualityRegimes(signal),
    staleTime: 60_000,
  });
  // A failed read is not an empty result: a band that silently vanished would recreate the
  // very defect it exists to fix — a measured method reading as "nothing else is rated".
  // The blind state is named (ADR 0026); only the transient pending state renders nothing.
  if (isError) {
    return (
      <section
        aria-label={t("title")}
        className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-4 py-3"
      >
        <div className="flex flex-wrap items-baseline gap-x-2">
          <h2 className="text-[0.8rem] font-semibold">{t("title")}</h2>
          <p className="text-[0.66rem] text-[var(--tessera-text-muted)]">{t("unreadable")}</p>
        </div>
      </section>
    );
  }
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
          const shownNames = entries
            .slice(0, MAX_NAMES)
            .map((entry) => entry.name)
            .join(" · ");
          const hiddenNames = entries.length - Math.min(entries.length, MAX_NAMES);
          const businessEntries =
            regime === "business_scored" ? entries.filter((entry) => entry.business) : [];
          const hiddenBusiness =
            businessEntries.length - Math.min(businessEntries.length, MAX_BUSINESS_LINES);
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
                  <span className="text-[0.66rem] tabular-nums text-[var(--tessera-text-muted)]">
                    {t("agentCount", { count: entries.length })}
                  </span>
                  <span className="text-[0.66rem] text-[var(--tessera-text-muted)]">
                    {shownNames}
                    {hiddenNames > 0 ? ` · ${t("moreNames", { count: hiddenNames })}` : null}
                  </span>
                  {regime === "llm_judged" ? (
                    <span className="text-[0.66rem] text-[var(--tessera-text-muted)]">
                      {t("llm_judged.note")}
                    </span>
                  ) : null}
                </span>
                {businessEntries.slice(0, MAX_BUSINESS_LINES).map((entry) =>
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
                )}
                {hiddenBusiness > 0 ? (
                  <span className="mt-0.5 block text-[0.66rem] text-[var(--tessera-text-muted)]">
                    {t("business_scored.moreAgents", { count: hiddenBusiness })}
                  </span>
                ) : null}
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
