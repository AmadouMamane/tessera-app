"use client";

import { useQuery } from "@tanstack/react-query";
import { Brain, Clock, EyeOff, Gavel, Ruler } from "lucide-react";
import type { Route } from "next";
import { useFormatter, useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { fetchQualityRegimes } from "@/lib/api/client";
import type { QualityRegimeEntry } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

/**
 * The answer-quality rating methods (ADR 0017 §Amendment 4): one CARD per declared rating
 * method, each naming ITS agents and ITS counts, never blended with a neighbour's.
 * Rendered as the CONTENT of a house-mould Zone on the quality dashboard (operator
 * feedback 2026-08-25: the free-standing band between the hero and the temporal rail
 * broke the page's own "alert leads, temporal controls follow" sequence and wore a
 * foreign visual grammar). The Zone carries the label and the ⓘ; the honest-scope
 * sentence lives in the ⓘ (quality.explain.regimes) — and the counts span ALL history,
 * independent of the rail's window, which the ⓘ says out loud.
 *
 * Constraints this component must keep:
 *  · COUNTS only, never a rate — the hero owns the page's one percentage (insights
 *    361-363: two rulers never share a denominator), and its source cannot even reach the
 *    judge's numbers (no SLO fetch, no percent formatter — ratchet next door);
 *  · an unrated agent is not an invisible one: entries carry the declared
 *    publish-activity contract, chips mark the observed agents, and the card says how
 *    many stay watched on the cockpit (operator feedback, 2026-08-21);
 *  · every card carries a count in ITS unit (judged responses / checked runs / observed
 *    agents), and every chip is a door — the business ones to that agent's Métier view,
 *    the others to the agent's page, so "watched on the cockpit" is one click to prove;
 *  · fleet-scale legibility: chips cap at {@link MAX_NAMES} with "+N more", and each card
 *    speaks at the level of its population — one business agent gets its full counts,
 *    several get ONE total-runs line. Per-agent detail is the agent pages' job, never a
 *    synthesis card's: 200 agents render as counts, never as 200 six-figure sentences;
 *  · the pending state reserves the section's shape (title + three skeleton cards) so the
 *    page never jumps when the declaration arrives — and it claims nothing while waiting;
 *  · every counting card carries its LIVENESS: "last rated/checked N days ago" (warning
 *    tone past {@link STALE_AFTER_DAYS}) and "since {a named date}" instead of a vague
 *    "since the beginning" — a total without its recency reads as alive when it may be a
 *    fossil (ADR 0052);
 *  · and the silence of ONE agent is visible on its chip: an amber dot (with the
 *    silent-days tooltip) when that agent's own ruler has said nothing for more than
 *    {@link STALE_AFTER_DAYS} days while the card's population line still reads fresh.
 */
const REGIME_ORDER = ["llm_judged", "business_scored", "unscored"] as const;

type Regime = (typeof REGIME_ORDER)[number];

/** Per-method icon + accent — slim inline icons, the zone sub-card grammar (no tiles). */
const REGIME_STYLE: Record<Regime, { icon: typeof Gavel; accent: string }> = {
  // Theme TOKENS, not colour literals: a bare icon on a light card has no tile
  // background to save it, and the contrast ratchet measures exactly that.
  llm_judged: { icon: Gavel, accent: "text-[var(--tessera-fg-accent)]" },
  business_scored: { icon: Ruler, accent: "text-[var(--tessera-fg-success)]" },
  unscored: { icon: EyeOff, accent: "text-[var(--tessera-text-muted)]" },
};

/** Agent chips shown per card before collapsing into "+N more". */
const MAX_NAMES = 4;

/** A ruler silent longer than this is flagged: a stale total must not read as alive. */
const STALE_AFTER_DAYS = 14;
const DAY_MS = 86_400_000;

function daysSince(iso: string): number {
  return Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / DAY_MS));
}

/** Lexicographic bounds over ISO-8601 instants from one writer — same order, no parsing. */
function earliest(instants: Array<string | null | undefined>): string | undefined {
  const known = instants.filter((value): value is string => !!value);
  return known.length ? known.reduce((a, b) => (a < b ? a : b)) : undefined;
}
function latest(instants: Array<string | null | undefined>): string | undefined {
  const known = instants.filter((value): value is string => !!value);
  return known.length ? known.reduce((a, b) => (a > b ? a : b)) : undefined;
}

/** Shared chip chrome — every chip is a Link (Métier view or agent page). */
const CHIP_CLASS =
  "inline-flex items-center gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-muted)] px-1.5 py-0.5 text-[0.64rem] text-[var(--tessera-text)]";

/**
 * "Last spoke: N days ago" — the liveness line every counting card carries (ADR 0052:
 * a total without its recency reads as alive when it may be a fossil). Past
 * {@link STALE_AFTER_DAYS} of silence the line turns to the warning tone; a ruler that
 * has NEVER spoken says so instead of hiding the line.
 */
function FreshnessLine({
  lastIso,
  agoKey,
  neverKey,
}: {
  lastIso: string | undefined;
  agoKey: string;
  neverKey: string;
}) {
  const t = useTranslations("qualityRegimes");
  if (!lastIso) {
    return (
      <p className="flex items-center gap-1.5">
        <Clock className="h-3 w-3 shrink-0" aria-hidden />
        {t(neverKey)}
      </p>
    );
  }
  const days = daysSince(lastIso);
  return (
    <p
      className={cn(
        "flex items-center gap-1.5 tabular-nums",
        days > STALE_AFTER_DAYS && "font-medium text-[var(--tessera-fg-warning)]",
      )}
    >
      <Clock className="h-3 w-3 shrink-0" aria-hidden />
      {t(agoKey, { days })}
    </p>
  );
}

function ChipInner({
  entry,
  observedLabel,
  staleTitle,
}: {
  entry: QualityRegimeEntry;
  observedLabel: string;
  /** Set when THIS agent's own ruler has been silent past the staleness bar. */
  staleTitle?: string;
}) {
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
      {staleTitle ? (
        // The individual silence the population line hides: the card's "last rated" reads
        // the FRESHEST agent, so one agent gone quiet stays invisible up there — its own
        // chip carries the amber dot and names the silent days (operator ask, 2026-08-22).
        <span
          className="h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--tessera-fg-warning)]"
          title={staleTitle}
          aria-label={staleTitle}
        />
      ) : null}
    </>
  );
}

export function QualityRegimeBand() {
  const t = useTranslations("qualityRegimes");
  const format = useFormatter();
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
    // The zone stays, its content names the blindness (ADR 0026) — never a silent gap.
    return (
      <section aria-label={t("title")} className="py-0.5">
        <p role="alert" className="text-[0.68rem] text-[var(--tessera-fg-danger)]">
          {t("unreadable")}
        </p>
      </section>
    );
  }
  if (!data) {
    // Pending: reserve the zone's shape so the page does not jump when the declaration
    // arrives — and claim NOTHING (the Zone label above is static chrome; the skeleton
    // shows no method, no agent, no count while the read is in flight).
    return (
      <section aria-label={t("title")} aria-busy="true">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
          {REGIME_ORDER.map((regime) => (
            <div
              key={regime}
              className="h-[6.5rem] animate-pulse rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]"
              aria-hidden
            />
          ))}
        </div>
      </section>
    );
  }

  const byRegime = new Map<Regime, QualityRegimeEntry[]>();
  for (const entry of data.regimes) {
    const regime = entry.regime as Regime;
    const bucket = byRegime.get(regime) ?? [];
    bucket.push(entry);
    byRegime.set(regime, bucket);
  }
  const presentRegimes = REGIME_ORDER.filter((r) => (byRegime.get(r)?.length ?? 0) > 0);
  // §A5 (ADR 0053) — the reading plane rides BY DECLARATION: agents whose manifest
  // declares an LLM understanding layer get one extra card, a third ruler with its own
  // unit (requests read) — never a field on a neighbour's card, never a rate.
  const readingEntries = data.regimes.filter((entry) => entry.understanding != null);
  const cardCount = presentRegimes.length + (readingEntries.length > 0 ? 1 : 0);

  // "since {a named date}" — vague "since the beginning" only when the ruler never spoke.
  // The date comes through next-intl's formatter, never a bare toLocaleString (the
  // formatter is the reader's locale; the bare call is the RUNTIME's).
  const sinceText = (iso: string | undefined) =>
    iso
      ? t("since.date", { date: format.dateTime(new Date(iso), { dateStyle: "long" }) })
      : t("since.start");

  return (
    <section aria-label={t("title")}>
      <div
        className={cn(
          "grid grid-cols-1 gap-2",
          cardCount === 2 && "md:grid-cols-2",
          cardCount >= 3 && "md:grid-cols-3",
        )}
      >
        {presentRegimes.map((regime) => {
          const entries = byRegime.get(regime) ?? [];
          const { icon: Icon, accent } = REGIME_STYLE[regime];
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
          // The judged plane's own count, same population-level logic: responses rated by
          // the judge are one unit across llm_judged agents, so the sum stays inside ONE
          // ruler (a COUNT — the hero owns the page's only rate).
          const judgedResponsesTotal =
            regime === "llm_judged"
              ? entries.reduce((sum, entry) => sum + (entry.judged?.responses_total ?? 0), 0)
              : 0;
          // First and last instants THIS ruler spoke, across its whole population.
          const planeSince =
            regime === "llm_judged"
              ? earliest(entries.map((entry) => entry.judged?.since))
              : earliest(businessEntries.map((entry) => entry.business?.since));
          const planeLast =
            regime === "llm_judged"
              ? latest(entries.map((entry) => entry.judged?.last_scored_at))
              : latest(businessEntries.map((entry) => entry.business?.last_event_at));
          const observedCount = entries.filter((entry) => entry.observable).length;
          // Per-language COUNTS of the judged plane (fr/de/en, same unit — responses):
          // the judged plane's languages live on ITS card, not appended to a status ribbon.
          const judgedLanguages = { fr: 0, de: 0, en: 0 };
          if (regime === "llm_judged") {
            for (const entry of entries) {
              judgedLanguages.fr += entry.judged?.languages?.fr ?? 0;
              judgedLanguages.de += entry.judged?.languages?.de ?? 0;
              judgedLanguages.en += entry.judged?.languages?.en ?? 0;
            }
          }
          // The individual silence the population line hides: this agent's OWN ruler said
          // nothing for more than STALE_AFTER_DAYS — its chip carries the amber dot.
          const staleTitleOf = (entry: QualityRegimeEntry): string | undefined => {
            const last =
              regime === "llm_judged"
                ? entry.judged?.last_scored_at
                : regime === "business_scored"
                  ? entry.business?.last_event_at
                  : null;
            if (!last) return undefined;
            const days = daysSince(last);
            if (days <= STALE_AFTER_DAYS) return undefined;
            return t(regime === "llm_judged" ? "chipStale.rated" : "chipStale.checked", {
              days,
            });
          };
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
              <div className="flex items-center gap-2">
                <Icon className={cn("h-3.5 w-3.5 shrink-0", accent)} aria-hidden />
                <span className="min-w-0 flex-1 text-[0.7rem] font-semibold leading-snug">
                  {t(`${regime}.label`)}
                </span>
                <span className="shrink-0 rounded-full border border-[var(--tessera-border)] bg-[var(--tessera-muted)] px-2 py-0.5 text-[0.62rem] font-medium tabular-nums text-[var(--tessera-text-muted)]">
                  {t("agentCount", { count: entries.length })}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-1">
                {entries.slice(0, MAX_NAMES).map((entry) => (
                  // Every chip is a door — the business ones straight to that agent's
                  // Métier view, the others to the agent's page: at fleet scale the chips
                  // ARE the per-agent navigation, and "watched on the cockpit" becomes one
                  // click to prove instead of a claim to trust.
                  <Link
                    key={entry.agent_id}
                    href={
                      (regime === "business_scored"
                        ? `/agents/${entry.agent_id}/metier`
                        : `/agents/${entry.agent_id}`) as Route
                    }
                    className={cn(
                      CHIP_CLASS,
                      "transition-colors hover:text-[var(--tessera-text-strong)]",
                      regime === "business_scored"
                        ? "hover:border-emerald-500/50"
                        : "hover:border-[var(--tessera-text-muted)]/50",
                    )}
                  >
                    <ChipInner
                      entry={entry}
                      observedLabel={t("observedChip")}
                      staleTitle={staleTitleOf(entry)}
                    />
                  </Link>
                ))}
                {hiddenNames > 0 ? (
                  <span className="text-[0.64rem] text-[var(--tessera-text-muted)]">
                    {t("moreNames", { count: hiddenNames })}
                  </span>
                ) : null}
              </div>
              <div className="mt-auto space-y-1 text-[0.66rem] text-[var(--tessera-text-muted)]">
                {regime === "llm_judged" ? (
                  <p className="tabular-nums">
                    {t("llm_judged.counts", {
                      n: judgedResponsesTotal,
                      since: sinceText(planeSince),
                    })}
                  </p>
                ) : null}
                {regime === "llm_judged" ? (
                  <p className="tabular-nums">{t("llm_judged.languages", judgedLanguages)}</p>
                ) : null}
                {regime === "llm_judged" ? (
                  <FreshnessLine
                    lastIso={planeLast}
                    agoKey="freshness.ratedAgo"
                    neverKey="freshness.neverRated"
                  />
                ) : null}
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
                        since: sinceText(planeSince),
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
                    {t("business_scored.aggregate", {
                      runs: businessRunsTotal,
                      since: sinceText(planeSince),
                    })}
                  </p>
                ) : null}
                {regime === "business_scored" ? (
                  <FreshnessLine
                    lastIso={planeLast}
                    agoKey="freshness.checkedAgo"
                    neverKey="freshness.neverChecked"
                  />
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
        {readingEntries.length > 0 ? <ReadingPlaneCard entries={readingEntries} /> : null}
      </div>
    </section>
  );
}

/**
 * §A5 (ADR 0053) — the reading plane's card: the agents whose MANIFEST declares an LLM
 * understanding layer (`understanding: llm_structured`), by declaration, never by what a
 * score table happens to hold. COUNTS only, like every card here — the reading's measured
 * accuracy lives on the evaluation plane (the labeled bench, quoted on the agent's
 * Évaluations view), never as a rate beside the judge's. Chips door to each agent's
 * Métier view, where the full reading card lives.
 */
function ReadingPlaneCard({ entries }: { entries: QualityRegimeEntry[] }) {
  const t = useTranslations("qualityRegimes");
  const format = useFormatter();
  const summaries = entries
    .map((entry) => entry.understanding?.summary)
    .filter((summary): summary is NonNullable<typeof summary> => summary != null);
  const sum = (pick: (summary: (typeof summaries)[number]) => number) =>
    summaries.reduce((total, summary) => total + pick(summary), 0);
  const observed = sum((summary) => summary.observed);
  const verdicts = sum((summary) => summary.verdicts);
  const agree = sum((summary) => summary.agree);
  const disagree = sum((summary) => summary.disagree);
  const failures = sum((summary) =>
    Object.values(summary.failures).reduce((total, n) => total + n, 0),
  );
  // The model's median reading time does not SUM across agents: shown while ONE agent
  // declares the plane (today's fleet), dropped past that — never a fake fleet median.
  const soleLatency = entries.length === 1 ? (summaries[0]?.latency_ms_p50 ?? null) : null;
  const lastRead = latest(summaries.map((summary) => summary.latest_at));
  return (
    <article className="flex flex-col gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3.5 py-3">
      <div className="flex items-center gap-2">
        <Brain className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-fg-info)]" aria-hidden />
        <span className="min-w-0 flex-1 text-[0.7rem] font-semibold leading-snug">
          {t("understanding.label")}
        </span>
        <span className="shrink-0 rounded-full border border-[var(--tessera-border)] bg-[var(--tessera-muted)] px-2 py-0.5 text-[0.62rem] font-medium tabular-nums text-[var(--tessera-text-muted)]">
          {t("agentCount", { count: entries.length })}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-1">
        {entries.slice(0, MAX_NAMES).map((entry) => (
          // The chip doors to the Métier view: that is where the full reading card
          // (failures named by kind, mode, model) lives.
          <Link
            key={entry.agent_id}
            href={`/agents/${entry.agent_id}/metier` as Route}
            className={cn(
              CHIP_CLASS,
              "transition-colors hover:border-sky-500/50 hover:text-[var(--tessera-text-strong)]",
            )}
          >
            <ChipInner entry={entry} observedLabel={t("observedChip")} />
          </Link>
        ))}
        {entries.length > MAX_NAMES ? (
          <span className="text-[0.64rem] text-[var(--tessera-text-muted)]">
            {t("moreNames", { count: entries.length - MAX_NAMES })}
          </span>
        ) : null}
      </div>
      <div className="mt-auto space-y-1 text-[0.66rem] text-[var(--tessera-text-muted)]">
        {summaries.length === 0 ? (
          // Declared but nothing read yet — an honest empty, never an invented zero rate.
          <p>{t("understanding.empty")}</p>
        ) : (
          <>
            <p className="tabular-nums">
              {t("understanding.counts", { observed, verdicts, agree, disagree })}
            </p>
            {failures > 0 ? (
              <p className="tabular-nums">{t("understanding.failures", { count: failures })}</p>
            ) : null}
            {soleLatency != null ? (
              <p className="tabular-nums">
                {t("understanding.latency", {
                  seconds: format.number(soleLatency / 1000, { maximumFractionDigits: 1 }),
                })}
              </p>
            ) : null}
            <FreshnessLine
              lastIso={lastRead}
              agoKey="freshness.readAgo"
              neverKey="freshness.neverRead"
            />
          </>
        )}
      </div>
    </article>
  );
}
