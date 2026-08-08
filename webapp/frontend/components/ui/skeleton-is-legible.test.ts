import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * A skeleton has exactly one job: say "I do not know yet", as opposed to "there is nothing".
 *
 * It did neither. The gradient was
 * `linear-gradient(110deg, var(--secondary) 8%, var(--muted) 18%, var(--secondary) 33%)` and in
 * BOTH themes `--secondary` and `--muted` resolve to `--tessera-muted` — three identical stops.
 * The 2s shimmer swept a monochrome band, so nothing moved; and in dark mode the resulting flat
 * block (#071b2e) sat on a card of #06182a, a difference no eye resolves. All 102 skeletons in
 * this app rendered as empty panels.
 *
 * That is not a cosmetic complaint here. This cockpit spends most of its guard-rails keeping
 * "not measured" apart from "measured as zero"; a loading state that looks like an empty state
 * is the same confusion, drawn instead of written. It cost a real misdiagnosis: a ten-second
 * judge-calibration read was taken for a broken panel during a review of that very panel.
 *
 * Two properties, and the second is the one a naive fix forgets: `prefers-reduced-motion`
 * freezes the sweep, so the BASE alone must read as a block against the card.
 */

const CSS = readFileSync(join(process.cwd(), "app/globals.css"), "utf8");
const SKELETON_FILE = readFileSync(join(process.cwd(), "components/ui/skeleton.tsx"), "utf8");
/** The class string only. The docstring above it QUOTES the old gradient, deliberately —
 * scanning the whole file would make this assertion fail on its own explanation. */
const SKELETON = SKELETON_FILE.slice(SKELETON_FILE.indexOf("export function Skeleton"));

/** Every `--name: #hex;` declared inside the block opened by `selector`. */
function tokensIn(selector: string): Record<string, string> {
  const start = CSS.indexOf(`${selector} {`);
  if (start < 0) throw new Error(`no ${selector} block in globals.css`);
  const end = CSS.indexOf("\n}", start);
  const block = CSS.slice(start, end);
  const out: Record<string, string> = {};
  for (const [, name, hex] of block.matchAll(/(--[\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) {
    if (name && hex) out[name] = hex.toLowerCase();
  }
  return out;
}

function srgb(hex: string): [number, number, number] {
  const v = [1, 3, 5].map((i) => Number.parseInt(hex.slice(i, i + 2), 16) / 255);
  return v.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)) as [
    number,
    number,
    number,
  ];
}

function luminance(hex: string): number {
  const [r, g, b] = srgb(hex);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return ((hi ?? 0) + 0.05) / ((lo ?? 0) + 0.05);
}

// `:root` carries the dark palette (the default); `.light` overrides it.
const THEMES = [
  { name: "dark", selector: ":root" },
  { name: "light", selector: ".light" },
] as const;

describe("the loading block is distinguishable from an empty one", () => {
  it.each(THEMES)("$name declares both skeleton tokens", ({ selector }) => {
    const t = tokensIn(selector);
    expect(t["--tessera-skeleton"]).toBeTruthy();
    expect(t["--tessera-skeleton-sheen"]).toBeTruthy();
  });

  /**
   * The defect, stated as a test: the two stops of the sweep were the same colour. Held as a
   * measured ratio rather than `!==`, because two hexes one unit apart are also "different"
   * and would sweep just as invisibly.
   */
  it.each(THEMES)("$name gives the sheen a visible step over the base", ({ selector }) => {
    const t = tokensIn(selector);
    const base = t["--tessera-skeleton"] ?? "#000000";
    const sheen = t["--tessera-skeleton-sheen"] ?? "#000000";
    expect(base).not.toBe(sheen);
    expect(contrast(base, sheen)).toBeGreaterThan(1.28);
  });

  /**
   * WITHOUT motion. `prefers-reduced-motion` and the manual "reduce motion" setting both stop
   * the animation dead, and a frozen skeleton the colour of its card is exactly the empty panel
   * this is meant to prevent.
   */
  it.each(THEMES)("$name keeps the base legible against the card, unanimated", ({ selector }) => {
    const t = tokensIn(selector);
    const base = t["--tessera-skeleton"] ?? "#000000";
    const card = t["--tessera-surface"] ?? "#000000";
    expect(contrast(base, card)).toBeGreaterThan(1.3);
  });

  it("goes red on the palette it replaced", () => {
    // What the old gradient actually resolved to, in each theme: one colour, three times.
    for (const selector of [":root", ".light"]) {
      const muted = tokensIn(selector)["--tessera-muted"] ?? "#000000";
      expect(contrast(muted, muted)).toBeLessThan(1.28);
    }
    // …and in dark mode it was not even visible as a block.
    const dark = tokensIn(":root");
    expect(
      contrast(dark["--tessera-muted"] ?? "#000", dark["--tessera-surface"] ?? "#000"),
    ).toBeLessThan(1.3);
  });
});

describe("the component spends those tokens", () => {
  it("paints from the skeleton pair, not from --muted/--secondary", () => {
    expect(SKELETON).toContain("var(--tessera-skeleton)");
    expect(SKELETON).toContain("var(--tessera-skeleton-sheen)");
    expect(SKELETON).not.toContain("var(--secondary)");
  });

  it("sets a flat background too, so a stopped sweep still shows a block", () => {
    expect(SKELETON).toContain("bg-[var(--tessera-skeleton)]");
  });
});
