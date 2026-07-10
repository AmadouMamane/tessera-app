import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * A number in the chrome is a promise: this page holds that many things, and clicking takes
 * you there. For as long as the cockpit existed, six sidebar badges (24 / 8 / 52 / 11 / 6 /
 * 200) and the bell's 7 were string literals typed into TSX. Nothing in the product could
 * have made them true — `/configurer/signal-catalog` announced 200 signals over a catalogue
 * of ten.
 *
 * They are gone. This is the test that stops them coming back, because they will be easy to
 * add: a badge literal is one word, and it renders beautifully.
 */

const root = process.cwd();
const LAYOUT_DIR = "components/layout";

const layoutSources = readdirSync(join(root, LAYOUT_DIR))
  .filter((name) => name.endsWith(".tsx"))
  .map((name) => ({ name, source: readFileSync(join(root, LAYOUT_DIR, name), "utf8") }));

/** `badge="7"`, `badge: "24"`, `badge={11}`, `badge={"6"}` — every way to type one in. */
const BADGE_LITERAL = /badge[A-Za-z]*\s*[:=]\s*\{?\s*["'`]?\d/;

describe("no numeric literal may reach a badge", () => {
  it("finds every layout component, so the guard cannot pass by looking at nothing", () => {
    expect(layoutSources.length).toBeGreaterThan(5);
    expect(layoutSources.map((f) => f.name)).toContain("sidebar.tsx");
    expect(layoutSources.map((f) => f.name)).toContain("app-header.tsx");
  });

  it.each(layoutSources)("$name has no hardcoded badge count", ({ source }) => {
    const offenders = source
      .split("\n")
      .map((line, index) => ({ line: line.trim(), number: index + 1 }))
      .filter(({ line }) => BADGE_LITERAL.test(line));
    expect(offenders).toEqual([]);
  });

  it("has teeth: the pattern it forbids is one it actually recognises", () => {
    // A guard that cannot fail guards nothing. These are the exact shapes that shipped.
    expect(BADGE_LITERAL.test('        badge="7"')).toBe(true);
    expect(BADGE_LITERAL.test('      badge: "24",')).toBe(true);
    expect(BADGE_LITERAL.test("      badge={11}")).toBe(true);
    expect(BADGE_LITERAL.test('      badgeTone: "danger",')).toBe(false); // a tone, not a count
    expect(BADGE_LITERAL.test('      badgeKey: "a_traiter",')).toBe(false); // the replacement
  });
});

describe("the chrome reads its counts, it does not invent them", () => {
  const sidebar = readFileSync(join(root, LAYOUT_DIR, "sidebar.tsx"), "utf8");
  const appHeader = readFileSync(join(root, LAYOUT_DIR, "app-header.tsx"), "utf8");

  it("the sidebar resolves badges through the chrome projection", () => {
    expect(sidebar).toContain("useChromeBadge");
    // The nav tree names a *fact*, never a value.
    expect(sidebar).toContain('badgeKey: "a_traiter"');
    expect(sidebar).toContain('badgeKey: "signal_catalog"');
  });

  it("the bell counts notifications the backend composed", () => {
    expect(appHeader).toContain("useChromeNotifications");
  });

  it("the bell's accessible name carries the real count, never a static word", () => {
    // `aria-label={label}` where label is built from `items.length` — a screen reader hears
    // "3 facts to act on", not "Notifications".
    expect(appHeader).toContain("notificationsWithCount");
    expect(appHeader).toContain("notificationsEmpty");
    expect(appHeader).not.toContain('label="Notifications"');
  });

  it("Qualité IA carries no badge at all — its page counts nothing outstanding", () => {
    const qualiteIaLeaf = sidebar.slice(
      sidebar.indexOf('labelKey: "item.qualiteIa"'),
      sidebar.indexOf('labelKey: "item.qualiteIa"') + 200,
    );
    expect(qualiteIaLeaf).not.toContain("badgeKey");
  });
});
