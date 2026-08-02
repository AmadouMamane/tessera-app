// @vitest-environment jsdom
//
// "Pas encore d'historique" was the one reason a control has no curve that explained nothing.
//
// The other three carry a `.why` on hover — a fixed-corpus probe, a whole-sample statistic, an
// undeclared source — and each names a property of the METRIC. This one names a property of the
// WINDOW, and it was the one an operator could actually act on: at 7 days the cockpit showed
// it on every row while holding 7 scored turns, 39 captured ones and a full probe run. The
// history existed. It sat inside a single 21 h slice, so there was one point, and one point is
// not a trend.
//
// These tests read the rendered `title`, not the message catalogue: a sentence that is correct
// in `fr.json` and never reaches an attribute explains nothing either.
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { cleanup, render, screen } from "@testing-library/react";
import { type AbstractIntlMessages, NextIntlClientProvider, createTranslator } from "next-intl";
import { afterEach, describe, expect, it } from "vitest";

import de from "@/messages/de.json";
import en from "@/messages/en.json";
import fr from "@/messages/fr.json";

import { NoHistoryLabel } from "@/components/overview/metric-sparkline";

const MESSAGES = { fr, de, en } as const;

afterEach(cleanup);

function titleOf(
  values: (number | null)[],
  bucketHours: number | null,
  locale: keyof typeof MESSAGES = "fr",
): string | null {
  render(
    <NextIntlClientProvider
      locale={locale}
      messages={MESSAGES[locale] as unknown as AbstractIntlMessages}
    >
      <NoHistoryLabel values={values} bucketHours={bucketHours} />
    </NextIntlClientProvider>,
  );
  const label = screen.getByText(
    locale === "fr" ? "pas encore d'historique" : locale === "en" ? "no history yet" : /Verlauf/,
  );
  return label.getAttribute("title");
}

/** 14 slices, one of which carries a measurement — the reported 7-day state. */
const ONE_OF_FOURTEEN = [...Array<number | null>(13).fill(null), 0.29];

/** A message key asked for with the dot LAST — the shape that resolves to its own path. */
const FLAT_DOTTED_KEY = /\}\.why`|\.why", \{/;

describe("the empty trend cell says which window it is empty of", () => {
  it("names how many slices carry a measurement, and how wide one is", () => {
    const title = titleOf(ONE_OF_FOURTEEN, 12);
    expect(title).toContain("14");
    expect(title).toContain("12 h");
    // Not "no data": the distinction between an empty window and a window whose data does not
    // span two slices is the entire content of this tooltip.
    expect(title).toMatch(/Une seule/);
  });

  it("says none rather than one when the window is genuinely empty", () => {
    const title = titleOf(Array<number | null>(30).fill(null), 24);
    expect(title).toMatch(/Aucune/);
    expect(title).toContain("30");
    // 24 h is a day, and reads as one.
    expect(title).toContain("1 jour");
  });

  it.each(["fr", "de", "en"] as const)("explains itself in %s", (locale) => {
    const title = titleOf(ONE_OF_FOURTEEN, 12, locale);
    expect(title).toBeTruthy();
    // The ICU placeholders must be SPENT, not printed: an unresolved `{total}` in a tooltip
    // is how a missing param has shipped before.
    expect(title).not.toMatch(/[{}]/);
    expect(title).toContain("14");
  });
});

describe("every reason a control has no curve reaches the screen", () => {
  // The tooltip that explains nothing was not the only one. `fixed-corpus.why` and its two
  // siblings were written, translated three ways, and asked for under a key whose DOT
  // next-intl reads as a namespace step — so `t("fixed-corpus.why")` looked up
  // `noCurve → "fixed-corpus" → "why"`, found a string where it wanted an object, and
  // rendered the literal path `overview.noCurve.fixed-corpus.why` as the tooltip. Measured on
  // the deployed build on 2026-08-02, in both tables, since the day they were written. Nothing
  // fails when a message is missing — it prints its own name, which looks like a tooltip.
  it.each(["fixed-corpus", "no-timestamp", "not-measured"])(
    "resolves why.%s through next-intl rather than to its own key",
    (reason) => {
      for (const locale of ["fr", "de", "en"] as const) {
        const t = createTranslator({
          locale,
          messages: MESSAGES[locale] as never,
          namespace: "overview.noCurve" as never,
          onError: () => {},
        });
        const why = t(`why.${reason}` as never) as string;
        expect(why.length, `${locale}/${reason}`).toBeGreaterThan(40);
        // A message that failed to resolve renders its own path, which contains the namespace.
        expect(why, `${locale}/${reason}`).not.toContain("noCurve");
      }
    },
  );

  it("asks for it in that order at both call sites", () => {
    // The catalogue alone cannot hold this: the sentences were always present and correct.
    // What was wrong was the ORDER of the key, in the two components that render it — so that
    // is what gets read here, from the source of the things themselves.
    for (const file of [
      "components/overview/overview-dashboard.tsx",
      "components/observability/signals-table.tsx",
      "components/overview/metric-sparkline.tsx",
    ]) {
      const source = readFileSync(join(process.cwd(), file), "utf8");
      expect(source, file).toMatch(/why\.\$\{|t\("why\./);
      expect(source, file).not.toMatch(FLAT_DOTTED_KEY);
    }
  });

  it("would have caught the two shapes that shipped", () => {
    // A guard nobody has seen refuse is a guard nobody knows works. These are the exact
    // expressions that were in the tree, verbatim.
    expect("tnc(`${c.noCurve}.why`)").toMatch(FLAT_DOTTED_KEY);
    expect('t("tooShort.why", { n: measured, total, width })').toMatch(FLAT_DOTTED_KEY);
  });
});

describe("it refuses to describe a window it has not got", () => {
  it("carries no tooltip before the series arrives", () => {
    // An empty `values` is "the request has not landed", not "the window is empty". Saying
    // "0 of 0 slices" would be a confident sentence about nothing — the exact failure mode
    // this repo calls a witness reporting over a hole.
    expect(titleOf([], null)).toBeNull();
  });

  it("carries no tooltip when the report has no window to slice", () => {
    expect(titleOf(ONE_OF_FOURTEEN, null)).toBeNull();
  });
});
