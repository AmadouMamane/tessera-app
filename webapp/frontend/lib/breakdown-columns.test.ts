/**
 * The one thing about these widths that a browser will not tell you.
 *
 * The geometry belongs in `e2e/table-rhythm.spec.ts`, which measures the rendered page. What
 * lives here are the two ways these constants fail SILENTLY — the layout stays plausible,
 * nothing errors, and the only symptom is a table that is subtly wrong:
 *
 *  1. **A class assembled from a variable emits no CSS.** Tailwind's scanner only finds
 *     literals, so `w-[${X}]` produces no rule and the column simply has no width.
 *  2. **A `calc()` mixing a percentage with a length is dropped.** Under `table-layout: fixed`
 *     Chromium ignores it and falls back to the equal share. `calc((100% - 10rem) * 2 / 6)`
 *     was written, built into a probe image, and measured 294.5 px where 471 was intended —
 *     with no warning anywhere. Confirmed against the browser in a scratch page: `34.7%` and
 *     `calc(100% * 2 / 6)` are honoured, `calc((100% - 160px) * 2 / 6)` is not.
 *
 * Both rules are the same rule, really: a width here must be a form the toolchain and the
 * browser can both see. That is checkable without a browser, so it is checked here.
 */

import { describe, expect, it } from "vitest";

import { COL_IDENTITY, COL_VERDICT, TABLE_BREAKDOWN } from "@/lib/breakdown-columns";

describe("the widths are written in forms that survive the toolchain", () => {
  it.each([
    ["identity", COL_IDENTITY],
    ["verdict", COL_VERDICT],
  ])("states the %s width as a literal arbitrary-value class", (_name, cls) => {
    // Not a template, not a concatenation: the scanner reads source text, not values.
    expect(cls).toMatch(/^w-\[[^${}]+\]$/);
  });

  it("never mixes a percentage with a length in a width", () => {
    for (const cls of [COL_IDENTITY, COL_VERDICT]) {
      const value = /^w-\[(.+)\]$/.exec(cls)?.[1] ?? "";
      const mixed = value.includes("%") && /\d(px|rem|em|ch|vw|vh)/.test(value);
      expect(mixed, `${cls} mixes units and a table cell would ignore it`).toBe(false);
    }
  });

  it("declares a fixed layout, without which both widths are only hints", () => {
    // Under `table-layout: auto` a cell width is a suggestion the browser may override in
    // favour of content — the layout this module exists to replace.
    expect(TABLE_BREAKDOWN).toContain("table-fixed");
    expect(TABLE_BREAKDOWN).toContain("w-full");
  });
});

describe("the two named columns leave room for the values between them", () => {
  const px = (cls: string, table: number): number => {
    const value = /^w-\[(.+)\]$/.exec(cls)?.[1] ?? "";
    if (value.endsWith("%")) return (table * Number.parseFloat(value)) / 100;
    if (value.endsWith("rem")) return Number.parseFloat(value) * 16;
    throw new Error(`unhandled width: ${value}`);
  };

  it.each([1338, 1150, 946])("keeps a majority of a %i px table for the values", (table) => {
    const named = px(COL_IDENTITY, table) + px(COL_VERDICT, table);
    expect(named).toBeLessThan(table * 0.5);
  });

  it("gives the verdict more than a value column but never half the table", () => {
    // The failure this bounds is a share rule that handed the verdict 669 px of 1338 on the
    // two-value lens, leaving 23 px between its neighbours' ink.
    const table = 1338;
    const verdict = px(COL_VERDICT, table);
    const smallestLens = (table - px(COL_IDENTITY, table) - verdict) / 2;
    expect(verdict).toBeGreaterThan(smallestLens * 0.5);
    expect(verdict).toBeLessThan(table * 0.5);
  });
});
