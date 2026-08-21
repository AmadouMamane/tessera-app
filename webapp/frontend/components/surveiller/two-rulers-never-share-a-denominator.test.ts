import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * TWO RULERS NEVER SHARE A DENOMINATOR (ADR 0017 §Amendment 4, insights 361-363).
 *
 * The quality page carries two disjoint populations: responses judged by the LLM judge
 * (the hero's rate) and runs scored by the deterministic business ruler (the band's
 * counts). The defect already paid for on the certifying matrix is one figure quietly
 * absorbing both. This ratchet pins the two mechanical guarantees that make that defect
 * unrepresentable on this page:
 *
 *  · the band's SOURCE cannot reach the LLM plane's numbers at all — no SLO fetch, no
 *    good_rate, no percent formatter: the populations cannot meet in one component;
 *  · the band's CATALOGUE lines keep one population noun each — the judged plane says
 *    responses, the business plane says runs, and neither line may borrow the other's
 *    noun or carry a rate placeholder.
 */

const read = (rel: string) => readFileSync(join(process.cwd(), rel), "utf-8");

const BAND = read("components/surveiller/quality-regime-band.tsx");
const HERO = read("components/surveiller/signal-breach-hero.tsx");

type Locale = "fr" | "en" | "de";
const LOCALES: Locale[] = ["fr", "en", "de"];

interface RegimeCatalogue {
  llm_judged: { label: string; note: string };
  business_scored: { label: string; counts: string; link: string };
  unscored: { label: string };
}

const catalogue = (locale: Locale): RegimeCatalogue =>
  (JSON.parse(read(`messages/${locale}.json`)) as { qualityRegimes: RegimeCatalogue })
    .qualityRegimes;

// The population nouns, as SHAPES (article/inflection-tolerant), per locale.
const RESPONSES_NOUN: Record<Locale, RegExp> = {
  fr: /réponses?/iu,
  en: /responses?/iu,
  de: /antworten/iu,
};
const RUNS_NOUN: Record<Locale, RegExp> = {
  fr: /exécutions?/iu,
  en: /\bruns?\b/iu,
  de: /ausführung/iu,
};

describe("the band's source cannot reach the LLM plane", () => {
  it("never fetches the SLO, reads good_rate, or formats a percentage", () => {
    expect(BAND).not.toMatch(/fetchSLO/);
    expect(BAND).not.toMatch(/good_rate/);
    expect(BAND).not.toMatch(/usePercentFormat/);
  });

  it("has teeth: the hero next door matches every pattern the band is banned from", () => {
    // Guards die silently when their pattern stops matching anything real (the blind-spec
    // trap). The hero USES each banned symbol, so the regexes are provably matchable.
    expect(HERO).toMatch(/fetchSLO/);
    expect(HERO).toMatch(/good_rate/);
    expect(HERO).toMatch(/usePercentFormat/);
  });
});

describe("one population, one noun", () => {
  it.each(LOCALES)("%s: the judged plane says responses and never runs", (locale) => {
    const { llm_judged } = catalogue(locale);
    expect(llm_judged.label).toMatch(RESPONSES_NOUN[locale]);
    expect(llm_judged.label).not.toMatch(RUNS_NOUN[locale]);
  });

  it.each(LOCALES)("%s: the business plane says runs and never responses", (locale) => {
    const { business_scored } = catalogue(locale);
    expect(business_scored.label).toMatch(RUNS_NOUN[locale]);
    for (const line of [business_scored.label, business_scored.counts]) {
      expect(line).not.toMatch(RESPONSES_NOUN[locale]);
    }
  });

  it.each(LOCALES)("%s: the business counts line carries no rate in either notation", (locale) => {
    const { business_scored } = catalogue(locale);
    expect(business_scored.counts).not.toMatch(/\{rate\}/);
    expect(business_scored.counts).not.toMatch(/%/);
  });
});

describe("the ratchet has teeth", () => {
  it("a line merging the two populations trips the noun exclusions", () => {
    // The forged sentence a future edit could plausibly produce: one rate over both
    // populations. It matches BOTH nouns, so whichever row it lands on, an exclusion
    // above turns red.
    const forged = "92 % des réponses et exécutions au niveau exigé";
    expect(forged).toMatch(RESPONSES_NOUN.fr);
    expect(forged).toMatch(RUNS_NOUN.fr);
  });

  it("a rate smuggled into the counts line trips the rate exclusions", () => {
    const forged = "{rate} des exécutions au niveau exigé";
    expect(forged).toMatch(/\{rate\}/);
  });
});
