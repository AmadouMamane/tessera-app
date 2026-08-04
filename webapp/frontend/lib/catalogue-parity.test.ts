import { describe, expect, it } from "vitest";

import de from "@/messages/de.json";
import en from "@/messages/en.json";
import fr from "@/messages/fr.json";

/**
 * The three catalogues carry the SAME keys.
 *
 * This is the ratchet that keeps the missing-message fallback's case empty (see
 * `i18n/fallback.ts`). ~490 `t()` calls across 65 components build their key at runtime — from
 * a status, a severity, a locale, a control id — and the failure that class produces is not a
 * crash: it is a French operator seeing a correct label while a German one sees an em dash on
 * the same screen, because the key was added to `fr.json` and to nothing else.
 *
 * Measured when this was written: 7292 leaf keys in each of the three, union 7292, zero
 * missing anywhere. So this locks a state that is already clean rather than declaring a debt —
 * which is the only moment a parity assertion is cheap to add and worth having.
 *
 * It does NOT check that a translation was actually translated (a German value that is still
 * the French sentence passes here), and it cannot: that is a human judgement, and
 * `/observability/localization` is the surface that reports on it.
 */

type Catalogue = Record<string, unknown>;

function leafKeys(node: unknown, prefix = ""): string[] {
  if (node === null || typeof node !== "object" || Array.isArray(node)) return [prefix];
  return Object.entries(node as Catalogue).flatMap(([key, value]) =>
    leafKeys(value, prefix ? `${prefix}.${key}` : key),
  );
}

const CATALOGUES = { fr, de, en } as const;

describe("message catalogue parity", () => {
  const keys = Object.fromEntries(
    Object.entries(CATALOGUES).map(([locale, cat]) => [locale, new Set(leafKeys(cat))]),
  ) as Record<keyof typeof CATALOGUES, Set<string>>;

  it("reads real catalogues — the positive control", () => {
    // A resolution failure that yielded `{}` would make every assertion below pass on nothing.
    for (const [locale, set] of Object.entries(keys)) {
      expect(set.size, `${locale} resolved to an empty catalogue`).toBeGreaterThan(5000);
    }
  });

  it("flattens nested keys — the negative control", () => {
    expect(leafKeys({ a: { b: 1, c: { d: 2 } } }).sort()).toEqual(["a.b", "a.c.d"]);
  });

  for (const locale of ["fr", "de", "en"] as const) {
    it(`${locale} is missing no key another locale declares`, () => {
      const union = new Set([...keys.fr, ...keys.de, ...keys.en]);
      const missing = [...union].filter((k) => !keys[locale].has(k)).sort();
      expect(missing).toEqual([]);
    });
  }
});
