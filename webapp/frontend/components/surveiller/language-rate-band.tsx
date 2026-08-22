"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";

import { ProportionStrip } from "@/components/surveiller/proportion-strip";
import { AGENT_SCOPE_PARAM, parseAgentScope } from "@/lib/agent-scope";
import { fetchSLO } from "@/lib/api/client";
import { usePercentFormat } from "@/lib/format-number";
import { useWindowStore } from "@/lib/stores/window-store";

/**
 * Per-language slices of the judged plane (the refonte's remaining item): three tiles —
 * FR · DE · EN — each carrying its own n and, when the sample is publishable, its rate.
 * Same endpoint, same query key, same scope and period as the hero above, so the two can
 * never quote different reads of one window; the slices are sub-populations of the ONE
 * judged plane (the hero's), never a second ruler.
 *
 * Honesty rules inherited from the hero: a language nobody spoke reads "no rated
 * responses" (n=0 is a fact, 0.0 % would be a fabrication); a thin sample leads with its
 * COUNTS and withholds the rate (same MIN_N threshold as the hero's gauge).
 */
const LANGUAGES = ["fr", "de", "en"] as const;

/** Same publishability floor as the hero's gauge — a rate below this is fabricated precision. */
const MIN_N_FOR_A_RATE = 100;

export function LanguageRateBand() {
  const t = useTranslations("qualityRegimes.byLanguage");
  const searchParams = useSearchParams();
  const scope = parseAgentScope(searchParams.get(AGENT_SCOPE_PARAM));
  const period = useWindowStore((s) => s.period);
  const { data, isError } = useQuery({
    queryKey: ["slo", null, scope, period],
    queryFn: ({ signal }) => fetchSLO(signal, undefined, scope, period),
    staleTime: 30_000,
  });
  const percent = usePercentFormat(1);

  // A failed read is named; an absent field (older payload) or a wholly unmeasured plane
  // renders nothing — this band is a refinement of the hero, which already leads with the
  // plane's own unmeasured state.
  if (isError) {
    return <p className="text-[0.66rem] text-[var(--tessera-text-muted)]">{t("unreadable")}</p>;
  }
  const slices = data?.by_language;
  if (!data || !slices || data.n === 0) return null;

  return (
    <section aria-label={t("title")} className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <span className="text-[0.66rem] font-medium text-[var(--tessera-text-muted)]">
        {t("title")}
      </span>
      {/* Each language's share of the judged responses — one unit (responses), so the
          strip stays inside the hero's own plane. Hidden when only one language spoke. */}
      <ProportionStrip
        className="w-24 shrink-0"
        label={t("title")}
        segments={LANGUAGES.map((language, index) => ({
          key: language,
          title: `${language.toUpperCase()} · ${slices[language]?.n ?? 0}`,
          value: slices[language]?.n ?? 0,
          className: ["bg-[#7c5cf5]", "bg-[#7c5cf5]/60", "bg-[#7c5cf5]/30"][index] ?? "",
        }))}
      />
      {LANGUAGES.map((language) => {
        const slice = slices[language];
        const n = slice?.n ?? 0;
        return (
          <span
            key={language}
            className="inline-flex items-baseline gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-2 py-0.5 text-[0.66rem] tabular-nums"
          >
            <span className="font-semibold uppercase text-[var(--tessera-text)]">{language}</span>
            {slice === undefined || n === 0 ? (
              <span className="text-[var(--tessera-text-muted)]">{t("none")}</span>
            ) : n >= MIN_N_FOR_A_RATE ? (
              <span className="text-[var(--tessera-text)]">
                {t("rated", { rate: percent(slice.good_rate), n })}
              </span>
            ) : (
              <span className="text-[var(--tessera-text)]">
                {t("counts", { good: slice.n_good, n })}
              </span>
            )}
          </span>
        );
      })}
    </section>
  );
}
