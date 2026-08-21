import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * Two numbers, one word, four points apart — and neither was wrong.
 *
 * Measured on the served stack over the same 19 turns:
 *
 *   /observability/slo            good_rate 0.5263  → 10 of 19 responses cleared the 0.80 bar
 *   /observability/score-series   mean      0.4947  → the arithmetic mean of those 19 scores
 *
 * The SLO ribbon printed "Fidélité — 52,6 %" and the KPI tile two rows below printed
 * "Fidélité 49 %". Both true, both labelled with the metric alone, and close enough that the
 * only available reading was "one of these is broken". A share of responses and a mean of
 * scores are different statistics; the fix is to say which, not to pick one.
 *
 * This holds the naming, because copy drifts back: a later edit shortening the ribbon to
 * "{metric} — {rate}" would restore the ambiguity in silence, and no rendering test would care.
 */

const LOCALES = ["fr", "en", "de"] as const;

/** The phrase each locale uses to say "a share OF RESPONSES", not "the metric's value". */
/**
 * The NOUN is what the rule is about — a share of *responses*, never a bare number beside a
 * metric name. An adjective between the article and the noun is allowed, and one arrived on
 * 2026-08-21: "of JUDGED responses", because the online judge only runs on the `/chat` route
 * and `recouvrement`'s 261 turns are never scored at all. Narrowing the population is exactly
 * the kind of honesty this file exists to protect, so the pattern had to stop matching a fixed
 * phrase and start matching the shape.
 */
const NAMES_A_SHARE_OF_RESPONSES = {
  fr: /des (?:\w+ )?réponses/u,
  en: /of (?:\w+ )?responses/u,
  de: /der (?:\w+ )?Antworten/u,
} as const;

/**
 * The count form, added 2026-08-21, states how many responses were judged instead of what share
 * passed — because below 100 judged responses one of them is worth more than a percentage point,
 * so a rate there is a count wearing a percent sign. Different sentence, SAME rule: it must name
 * the responses, never leave a bare number beside the metric.
 */
const NAMES_A_COUNT_OF_RESPONSES = {
  fr: /\{n, plural[^}]*réponses? jugées?/u,
  en: /\{n, plural[^}]*judged responses?/u,
  de: /\{n, plural[^}]*bewerteten Antwort/u,
} as const;

function catalogue(locale: string) {
  return JSON.parse(readFileSync(join(process.cwd(), `messages/${locale}.json`), "utf8")) as {
    signalHero: Record<string, string> & { metric: Record<string, string> };
    quality: { kpi: Record<string, string>; metrics: Record<string, string> };
  };
}

describe("the SLO ribbon says WHICH statistic it is showing", () => {
  it.each(LOCALES)("%s names the responses in every COUNT sentence too", (locale) => {
    const { signalHero } = catalogue(locale);
    for (const key of ["breachedCount", "okCount"]) {
      const sentence = signalHero[key];
      expect(sentence, `signalHero.${key} is missing`).toBeTruthy();
      expect(sentence, `signalHero.${key} must name the responses it counted`).toMatch(
        NAMES_A_COUNT_OF_RESPONSES[locale],
      );
      // A count sentence must NOT also carry a rate: showing both is how the reader is invited
      // to trust the percentage the sample cannot support.
      expect(sentence, `signalHero.${key} must not smuggle a rate back in`).not.toMatch(
        /\{rate\}/u,
      );
    }
  });

  it.each(LOCALES)("%s names a share of responses in every verdict sentence", (locale) => {
    const { signalHero } = catalogue(locale);
    for (const key of ["breached", "ok", "breachedShort", "okShort"]) {
      const sentence = signalHero[key];
      expect(sentence, `signalHero.${key}`).toBeTruthy();
      expect(sentence, `signalHero.${key} must name a SHARE, not just the metric`).toMatch(
        NAMES_A_SHARE_OF_RESPONSES[locale],
      );
      // Both operands stay on screen: the share measured and the share required.
      expect(sentence).toContain("{rate}");
      expect(sentence).toContain("{threshold}");
    }
  });
});

describe("the metric KPI tile says its number is a mean", () => {
  it.each(LOCALES)("%s carries a mean tag, short enough to sit beside the figure", (locale) => {
    const tag = catalogue(locale).quality.kpi.meanTag;
    expect(tag).toBeTruthy();
    expect(tag?.length ?? 0).toBeLessThan(16);
  });

  it("renders that tag beside the value rather than hiding it in the ⓘ", () => {
    const source = readFileSync(
      join(process.cwd(), "components/observability/evolution-chart.tsx"),
      "utf8",
    );
    expect(source).toContain('tq("kpi.meanTag")');
  });
});

describe("the ratchet has teeth", () => {
  /**
   * Restoring the sentence that started this must turn it red. Without this the assertions
   * above are three regexes that happen to match today's copy — a guard whose failure mode
   * nobody has seen is a guard nobody knows the shape of.
   */
  it("goes red on the ambiguous sentence it replaced", () => {
    const restored = "{metric} — {rate} < objectif {threshold}";
    expect(restored).not.toMatch(NAMES_A_SHARE_OF_RESPONSES.fr);
    // …and it is not merely the accents: the English and German forms fail too.
    expect("{metric} — {rate} < target {threshold}").not.toMatch(NAMES_A_SHARE_OF_RESPONSES.en);
    expect("{metric} — {rate} < Ziel {threshold}").not.toMatch(NAMES_A_SHARE_OF_RESPONSES.de);
  });

  it("goes red when the two blocks disagree on a metric's name", () => {
    const hero = { faithfulness: "Treue" };
    const quality = { faithfulness: "Faktentreue" };
    expect(hero.faithfulness).not.toBe(quality.faithfulness);
  });
});

describe("one metric, one name", () => {
  /**
   * German carried two spellings for the same metric — `quality.metrics.faithfulness` said
   * "Treue" while `signalHero.metric.faithfulness` said "Faktentreue". Two names on one screen
   * read as two metrics, which is the same defect as one name on two statistics, mirrored.
   */
  it.each(LOCALES)("%s spells each shared metric the same way in both blocks", (locale) => {
    const { signalHero, quality } = catalogue(locale);
    for (const key of Object.keys(signalHero.metric)) {
      const other = quality.metrics[key];
      if (!other) continue; // the two maps cover different metric sets; only the overlap binds
      expect(signalHero.metric[key], `${locale}:${key}`).toBe(other);
    }
  });
});
