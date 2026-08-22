"use client";

import { useQuery } from "@tanstack/react-query";
import { EyeOff, Gavel, Ruler } from "lucide-react";
import type { Route } from "next";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { fetchQualityRegimes } from "@/lib/api/client";
import type { QualityRegimeEntry } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

/**
 * The answer-quality rating section (ADR 0017 §Amendment 4): one CARD per declared rating
 * method — the same visual grammar as the view-switch doors above it — each naming ITS
 * agents and ITS counts, never blended with a neighbour's. The subtitle states the honest
 * scope first: cross-cutting controls (security, compliance, cost) cover EVERY agent;
 * what differs per agent is only how its answers are rated.
 *
 * Constraints this component must keep:
 *  · COUNTS only, never a rate — the hero owns the page's one percentage (insights
 *    361-363: two rulers never share a denominator), and its source cannot even reach the
 *    judge's numbers (no SLO fetch, no percent formatter — ratchet next door);
 *  · an unrated agent is not an invisible one: entries carry the declared
 *    publish-activity contract, chips mark the observed agents, and the card says how
 *    many stay watched on the cockpit (operator feedback, 2026-08-21);
 *  · fleet-scale legibility: chips cap at {@link MAX_NAMES} with "+N more", and the
 *    business card speaks at the level of its population — a lone agent gets its full
 *    counts, several agents get ONE total-runs line with each chip opening that agent's
 *    Métier view. Per-agent detail is the Métier view's job, never a synthesis card's:
 *    200 agents render as counts, never as 200 six-figure sentences.
 */
const REGIME_ORDER = ["llm_judged", "business_scored", "unscored"] as const;

type Regime = (typeof REGIME_ORDER)[number];

/** Per-method icon + tile accent — sober tints over the shared card chrome. */
const REGIME_STYLE: Record<Regime, { icon: typeof Gavel; tile: string }> = {
  llm_judged: {
    icon: Gavel,
    tile: "border-[#7c5cf5]/40 bg-[#7c5cf5]/15 text-[var(--tessera-text)]",
  },
  business_scored: {
    icon: Ruler,
    tile: "border-emerald-500/40 bg-emerald-500/10 text-[var(--tessera-text)]",
  },
  unscored: {
    icon: EyeOff,
    tile: "border-[var(--tessera-border)] bg-[var(--tessera-muted)] text-[var(--tessera-text-muted)]",
  },
};

/** Agent chips shown per card before collapsing into "+N more". */
const MAX_NAMES = 4;

/** Shared chip chrome — the business card renders it as a Link, the others as a span. */
const CHIP_CLASS =
  "inline-flex items-center gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-muted)] px-1.5 py-0.5 text-[0.64rem] text-[var(--tessera-text)]";

function ChipInner({ entry, observedLabel }: { entry: QualityRegimeEntry; observedLabel: string }) {
  return (
    <>
      {entry.observable ? (
        // The observed marker: this agent publishes its activity and is already watched
        // on the cockpit — unrated never means unseen.
        <span
          className="h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500"
          title={observedLabel}
          aria-label={observedLabel}
        />
      ) : null}
      {entry.name}
    </>
  );
}

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
  // A failed read is not an empty result: a section that silently vanished would recreate
  // the very defect it exists to fix — a rated method reading as "nothing else is rated".
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

  const byRegime = new Map<Regime, QualityRegimeEntry[]>();
  for (const entry of data.regimes) {
    const regime = entry.regime as Regime;
    const bucket = byRegime.get(regime) ?? [];
    bucket.push(entry);
    byRegime.set(regime, bucket);
  }
  const presentRegimes = REGIME_ORDER.filter((r) => (byRegime.get(r)?.length ?? 0) > 0);

  return (
    <section aria-label={t("title")}>
      <div className="flex flex-wrap items-baseline gap-x-2">
        <h2 className="text-[0.8rem] font-semibold">{t("title")}</h2>
        <p className="text-[0.66rem] text-[var(--tessera-text-muted)]">{t("subtitle")}</p>
      </div>
      <div
        className={cn(
          "mt-2 grid grid-cols-1 gap-2.5",
          presentRegimes.length === 2 && "md:grid-cols-2",
          presentRegimes.length >= 3 && "md:grid-cols-3",
        )}
      >
        {presentRegimes.map((regime) => {
          const entries = byRegime.get(regime) ?? [];
          const { icon: Icon, tile } = REGIME_STYLE[regime];
          const hiddenNames = entries.length - Math.min(entries.length, MAX_NAMES);
          const businessEntries =
            regime === "business_scored" ? entries.filter((entry) => entry.business) : [];
          // The card speaks at the level of its population: one agent → its full counts;
          // several → one total (runs are the same unit across business agents, so the sum
          // stays inside ONE ruler) and the per-agent detail lives in each Métier view.
          const soleBusiness = businessEntries.length === 1 ? businessEntries[0] : undefined;
          const businessRunsTotal = businessEntries.reduce(
            (sum, entry) => sum + (entry.business?.runs_total ?? 0),
            0,
          );
          const observedCount = entries.filter((entry) => entry.observable).length;
          // One reason per distinct declared key — agents sharing a blind spot share a line.
          const reasonKeys =
            regime === "unscored"
              ? [...new Set(entries.map((e) => e.reason_key).filter((k): k is string => !!k))]
              : [];
          return (
            <article
              key={regime}
              className="flex flex-col gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3.5 py-3"
            >
              <div className="flex items-center gap-2.5">
                <span
                  className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-md border",
                    tile,
                  )}
                >
                  <Icon className="h-4 w-4" aria-hidden />
                </span>
                <span className="min-w-0 flex-1 text-[0.72rem] font-semibold leading-snug">
                  {t(`${regime}.label`)}
                </span>
                <span className="shrink-0 rounded-full border border-[var(--tessera-border)] bg-[var(--tessera-muted)] px-2 py-0.5 text-[0.62rem] font-medium tabular-nums text-[var(--tessera-text-muted)]">
                  {t("agentCount", { count: entries.length })}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-1">
                {entries.slice(0, MAX_NAMES).map((entry) =>
                  // On the business card each chip is a door to that agent's Métier view —
                  // at fleet scale the chips ARE the per-agent navigation.
                  regime === "business_scored" ? (
                    <Link
                      key={entry.agent_id}
                      href={`/agents/${entry.agent_id}/metier` as Route}
                      className={cn(
                        CHIP_CLASS,
                        "transition-colors hover:border-emerald-500/50 hover:text-[var(--tessera-text-strong)]",
                      )}
                    >
                      <ChipInner entry={entry} observedLabel={t("observedChip")} />
                    </Link>
                  ) : (
                    <span key={entry.agent_id} className={CHIP_CLASS}>
                      <ChipInner entry={entry} observedLabel={t("observedChip")} />
                    </span>
                  ),
                )}
                {hiddenNames > 0 ? (
                  <span className="text-[0.64rem] text-[var(--tessera-text-muted)]">
                    {t("moreNames", { count: hiddenNames })}
                  </span>
                ) : null}
              </div>
              <div className="mt-auto space-y-1 text-[0.66rem] text-[var(--tessera-text-muted)]">
                {regime === "llm_judged" ? <p>{t("llm_judged.note")}</p> : null}
                {soleBusiness?.business ? (
                  // A lone business agent earns its full counts — the one scale where a
                  // six-figure sentence is still legible.
                  <p className="flex flex-wrap items-baseline gap-x-2">
                    <span className="tabular-nums">
                      {t("business_scored.counts", {
                        runs: soleBusiness.business.runs_total,
                        declared: soleBusiness.business.signals_declared,
                        scored: soleBusiness.business.signals_scored,
                        unknown: soleBusiness.business.signals_unknown,
                        na: soleBusiness.business.signals_not_applicable,
                      })}
                    </span>
                    <Link
                      href={`/agents/${soleBusiness.agent_id}/metier` as Route}
                      className="font-medium text-[var(--tessera-fg-accent)] transition-colors hover:text-[var(--tessera-text-strong)]"
                    >
                      {t("business_scored.link")} →
                    </Link>
                  </p>
                ) : null}
                {businessEntries.length > 1 ? (
                  <p className="tabular-nums">
                    {t("business_scored.aggregate", { runs: businessRunsTotal })}
                  </p>
                ) : null}
                {reasonKeys.map((key) => (
                  <p key={key}>{tReason(key.slice("quality_regime.".length))}</p>
                ))}
                {regime === "unscored" && observedCount > 0 ? (
                  <p className="flex items-start gap-1.5 text-[var(--tessera-text)]">
                    <span
                      className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500"
                      aria-hidden
                    />
                    <span>{t("unscored.observedNote", { observed: observedCount })}</span>
                  </p>
                ) : null}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
