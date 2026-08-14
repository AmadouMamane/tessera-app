"use client";

import { useLocale } from "next-intl";
import { useMemo } from "react";

/**
 * Numbers formatted in the language the page is being read in — one door, not thirty.
 *
 * The cockpit had TWO symmetric defects, and only one of them was visible:
 *
 *  · `n.toLocaleString()` with no locale (10 sites) uses the *runtime's* locale. Server-rendered,
 *    that runtime is Node, whose default is en-US — so a French page served `2,061,605`, which is
 *    the reading that reached the operator. Client-rendered, the same call silently follows the
 *    visitor's browser, so the same screen could print two different formats.
 *  · `n.toLocaleString("fr-FR")` hardcoded (~20 sites) is the mirror image: it always looks right
 *    in French and is always wrong for a German or English operator. Nobody complains, because
 *    the person who would is not the person reading the demo.
 *
 * Both come from the same missing idea: the format is a property of the READER, and the reader's
 * language is what next-intl already resolved for the page. `useLocale()` is that answer, and the
 * `Intl.NumberFormat` is memoised per locale so a table of a hundred cells builds one formatter.
 *
 * Dates are deliberately NOT covered here: `useFormatter().dateTime()` from next-intl already
 * owns them, and a second date path is how two dates on one screen come to disagree.
 */
export function useNumberFormat(options?: Intl.NumberFormatOptions): Intl.NumberFormat {
  const locale = useLocale();
  // The options object is usually an inline literal, so it is a new reference on every render;
  // keying the memo on its VALUE keeps one formatter per (locale, options) instead of per render.
  const key = options ? JSON.stringify(options) : "";
  return useMemo(
    () => new Intl.NumberFormat(locale, options ? JSON.parse(key) : undefined),
    [locale, key, options],
  );
}

/**
 * The common case: an integer, grouped in the reader's language.
 *
 * Returns a formatting FUNCTION rather than a string so a component calls it per cell without
 * rebuilding the formatter — the shape every table here needs.
 */
export function useIntFormat(): (value: number | null | undefined) => string {
  const format = useNumberFormat({ maximumFractionDigits: 0 });
  // `null`/`undefined` render as an em dash, never as "0": a value that was not read is not a
  // value that is zero — the distinction this cockpit keeps re-learning (ADR 0026).
  return (value) => (value === null || value === undefined ? "—" : format.format(value));
}

/**
 * The server twin of {@link useIntFormat}, for Server Components.
 *
 * A hook cannot run there, but the locale is never missing either: it arrives as a route param.
 * Same output for the same locale, so a number does not change shape when a panel moves across
 * the server/client boundary.
 */
export function formatInt(locale: string, value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(value);
}
