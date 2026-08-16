import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * A number is formatted for its READER, not for the machine that rendered it.
 *
 * Two symmetric defects lived here, and only one of them was ever visible:
 *
 *  · `n.toLocaleString()` — no locale — asks the RUNTIME. Server-rendered, that runtime is Node,
 *    whose default is en-US, so a French page served `2,061,605`. That is the reading that
 *    reached the operator, on the overview's trace counter. Client-rendered, the same call
 *    follows the visitor's browser instead, so one screen can print two shapes of the same
 *    number.
 *  · `n.toLocaleString("fr-FR")` — hardcoded — is the mirror image, and it is the dangerous one
 *    precisely because it always looks right: it is wrong only for the German or English
 *    operator, who is not the person reading the demo.
 *
 * Both are refused here. The replacement is `lib/format-number` (`useIntFormat` /
 * `useNumberFormat` in client components, `formatInt(locale, …)` on the server), which reads the
 * locale next-intl already resolved for the page.
 *
 * DATES ARE OUT OF SCOPE: `new Date(x).toLocaleString()` is left to next-intl's
 * `useFormatter().dateTime()`, and mixing the two paths is how two dates on one screen come to
 * disagree. This witness says so rather than silently ignoring them.
 */

const ROOT = process.cwd();
const NUMERIC_CALL = /(?<!new Date\([^)]*\))\.toLocaleString\(/;
const BARE = /\.toLocaleString\(\s*\)/;
const HARDCODED_LOCALE = /\.toLocaleString\(\s*["'][a-z]{2}-[A-Z]{2}["']/;

/**
 * The THIRD shape, and the one that survived the first pass: `n.toFixed(1).replace(".", ",")`.
 *
 * It is `toLocaleString("fr-FR")` wearing different clothes — right in French, wrong for the
 * German or English operator, and silent in both. Measured 2026-08-15: 13 sites. Converted
 * 2026-08-16 to `Intl.NumberFormat`, which also fixes what the hand-written form structurally
 * cannot: the SPACE before a percent sign (fr/de have one, en does not) and the SIDE the
 * currency symbol sits on (`12,50 €` vs `€12.50`).
 *
 * Bare `toFixed` is deliberately NOT policed here. It is correct in an SVG path, a CSS width and
 * a sort key — the places it mostly lives — and a scan that cannot tell a coordinate from a
 * label would either cry wolf on charts or need an exemption list longer than the rule.
 */
const HARDCODED_COMMA = /\.toFixed\(\s*\d*\s*\)\s*\.replace\(\s*["']\.["']\s*,\s*["'],["']\s*\)/;

/**
 * Files that still format in a hardcoded language. Each entry is a debt with a reason, and the
 * list may only SHRINK.
 *
 * EMPTY SINCE 2026-08-16, and it got there the way a frozen list is supposed to: the two
 * survivors were Server Components sharing one module-level helper — 26 call sites across 12
 * functions in `agent-breakdown.tsx` — and the freeze said, correctly, that threading a locale
 * through every signature is a refactor rather than a sed. The refactor happened; the helpers
 * are now built once per render from the route's locale and passed down as one `fmt` bundle,
 * and this list emptied itself.
 *
 * The test below is what forced the cleanup: an entry that no longer offends is REFUSED, so a
 * freeze cannot quietly outlive the debt it described and go on excusing a file that is already
 * fine.
 */
const FROZEN_HARDCODED: Record<string, string> = {};

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry === ".next" || entry.startsWith(".")) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.tsx?$/.test(entry) && !entry.includes(".test.")) out.push(full);
  }
  return out;
}

/**
 * Strip comments before matching.
 *
 * Every module repaired by this pass now QUOTES the pattern it removed, in prose, to say why.
 * A detector that reads prose about code as code reports five explanations as five defects —
 * and makes deleting the explanation the cheapest way to go green. (`failed-read-is-not-an-empty-
 * result` learned this on its own first run; borrowed here for the same reason.)
 */
function withoutComments(text: string): string {
  return text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
}

function scan() {
  const scanned: string[] = [];
  const bare: string[] = [];
  const hardcoded: string[] = [];
  const comma: string[] = [];
  for (const dir of ["app", "components", "lib"]) {
    for (const file of walk(join(ROOT, dir))) {
      const rel = file.slice(ROOT.length + 1);
      // The module that OWNS the replacement necessarily names the pattern it replaces.
      if (rel === "lib/format-number.ts") continue;
      scanned.push(rel);
      const text = withoutComments(readFileSync(file, "utf8"));
      for (const line of text.split("\n")) {
        if (HARDCODED_COMMA.test(line)) comma.push(rel);
        if (!NUMERIC_CALL.test(line) || line.includes("new Date")) continue;
        if (BARE.test(line)) bare.push(rel);
        if (HARDCODED_LOCALE.test(line)) hardcoded.push(rel);
      }
    }
  }
  return {
    scanned,
    bare: [...new Set(bare)],
    hardcoded: [...new Set(hardcoded)],
    comma: [...new Set(comma)],
  };
}

/**
 * The one place a hand-written French decimal is still correct.
 *
 * `recouvrement-assistant-backend.ts` assembles a French-only draft — "Montant dû : 840,00 €",
 * "Échéancier indicatif — 3 mois" — as hardcoded prose. Formatting the ONE computed amount for
 * the reader's language while its neighbours stay French would produce `€280.00` inside a French
 * sentence: a number that is right about the locale and wrong about the paragraph it sits in.
 * The debt is the untranslated draft, not the separator, and it is recorded as such.
 */
const FROZEN_COMMA: Record<string, string> = {
  "components/recouvrement/recouvrement-assistant-backend.ts":
    "the amount sits inside hardcoded French prose; the debt is the untranslated draft",
};

describe("a number is formatted for its reader", () => {
  const { scanned, bare, hardcoded, comma } = scan();

  it("can still see — the positive control", () => {
    // Without this, a moved directory or a renamed extension would empty every list below and
    // read as a clean sweep. A zero that cannot tell "none" from "did not look" is not a
    // measurement (ADR 0026).
    expect(scanned.length).toBeGreaterThan(150);
  });

  it("detects both shapes — the negative control", () => {
    expect(BARE.test("const s = n.toLocaleString();")).toBe(true);
    expect(HARDCODED_LOCALE.test('const s = n.toLocaleString("fr-FR");')).toBe(true);
    // …and leaves the compliant form alone.
    expect(BARE.test("const s = fmtInt(n);")).toBe(false);
    expect(HARDCODED_LOCALE.test("const s = format.format(n);")).toBe(false);
    // …and the third shape, added 2026-08-16.
    expect(HARDCODED_COMMA.test('`${v.toFixed(2).replace(".", ",")} €`')).toBe(true);
    expect(HARDCODED_COMMA.test("x.toFixed(1).replace('.', ',')")).toBe(true);
    expect(HARDCODED_COMMA.test("const s = euro(v);")).toBe(false);
    // A `replace` that is not the decimal swap must not be caught.
    expect(HARDCODED_COMMA.test('name.replace(".", "-")')).toBe(false);
  });

  it("has no number formatted by the RUNTIME's locale", () => {
    // Not frozen, deliberately: this is the shape that served `2,061,605` on a French page, and
    // it is now empty. An exemption list here would be a licence to reintroduce it.
    expect(bare).toEqual([]);
  });

  it("has no NEW file formatting in a hardcoded language", () => {
    expect(hardcoded.filter((f) => !(f in FROZEN_HARDCODED))).toEqual([]);
  });

  it("keeps the frozen list honest — an entry that no longer offends must go", () => {
    const stale = Object.keys(FROZEN_HARDCODED).filter((f) => !hardcoded.includes(f));
    expect(stale).toEqual([]);
  });

  it("has no NEW hand-written French decimal", () => {
    expect(comma.filter((f) => !(f in FROZEN_COMMA))).toEqual([]);
  });

  it("keeps the comma exception honest too", () => {
    const stale = Object.keys(FROZEN_COMMA).filter((f) => !comma.includes(f));
    expect(stale).toEqual([]);
  });

  it("does not read its own explanations as defects", () => {
    // Five repaired modules now quote `.toFixed(1).replace(".", ",")` in prose to say why it
    // went. Without comment-stripping this suite would report them and make deleting the
    // explanation the cheapest way to green.
    expect(withoutComments('// a note about .toFixed(1).replace(".", ",")')).not.toMatch(
      HARDCODED_COMMA,
    );
    expect(withoutComments('const s = v.toFixed(1).replace(".", ",");')).toMatch(HARDCODED_COMMA);
  });
});
