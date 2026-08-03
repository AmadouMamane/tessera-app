// The RATCHET over the launcher surface — /login, /espaces, /select-space.
//
// WHY IT EXISTS, and it is an uncomfortable reason. On 2026-08-01 the launcher's
// palette moved out of a `style={SPACE_SELECTOR_TOKENS}` attribute in TSX and into
// `.launcher-surface` in `globals.css`, so that the theme class could finally reach
// it. That fixed the defect Amadou reported three times — the theme switch on those
// pages did nothing — but it also moved 14 colour constants OUT of the tree that
// `theme-contrast.test.ts` scans, and added roughly thirty new light ones nothing
// measured at all. A fix that relocates values past a witness has not made them
// safe; it has made them invisible. This file is what stops that from being the
// net effect: the values are measured where they now live.
//
// THE RULE. Parse `.launcher-surface` and `.light .launcher-surface` out of the
// stylesheet, resolve each token (including `rgba()` composited over the ground it
// actually sits on), and measure the pairs that a reader's eye actually forms.
// Text owes WCAG AA 4.5:1 — a cited standard. A separator owes a DESIGN floor,
// declared as such below, because 3:1 governs what identifies a component and a
// rule under a header identifies nothing.
//
// PAIRS ARE DECLARED, NOT INFERRED, and that is the honest limit of this witness.
// A stylesheet does not say which foreground lands on which background; only the
// markup does. So the pairing table below is authored, and it can therefore be
// INCOMPLETE in a way the file cannot detect on its own — if a future card puts
// `--gold` on `--bg-deep`, nothing here will notice until someone adds the row.
// What it does guarantee is that every pair anyone has thought about stays
// measured, and that the token set cannot be re-toned into unreadability in
// silence. Said plainly rather than left implied (ADR 0026).
//
// Mutation contract (each verified red before landing):
//   · re-tone `--text-secondary` light to the dark value  → red, names the pair;
//   · drop `--border-subtle` to the 2026-08-01 pre-fix alpha (dark .14 / light .10)
//                                                         → red, either theme;
//   · delete the `.light .launcher-surface` block         → red (a token is missing);
//   · rename `.launcher-surface`                          → red (anti-vacuity).
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const CSS = readFileSync(path.resolve(__dirname, "..", "..", "app", "globals.css"), "utf8");

/** Every declaration inside one selector's block. */
function block(selector: string): Map<string, string> {
  const start = CSS.indexOf(`${selector} {`);
  if (start === -1) return new Map();
  const end = CSS.indexOf("\n}", start);
  const body = CSS.slice(start, end);
  const out = new Map<string, string>();
  for (const m of body.matchAll(/(--[a-z0-9-]+):\s*([^;]+);/g)) {
    const [, name, value] = m;
    if (name === undefined || value === undefined) continue;
    out.set(name, value.trim().replace(/\s+/g, " "));
  }
  return out;
}

const DARK = block(".launcher-surface");
const LIGHT = block(".light .launcher-surface");

const srgb = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const luminance = (hex: string): number => {
  const [r = 0, g = 0, b = 0] = [1, 3, 5].map(
    (i) => Number.parseInt(hex.slice(i, i + 2), 16) / 255,
  );
  return 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b);
};
const contrast = (a: string, b: string): number => {
  const [hi = 0, lo = 0] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

/** `rgba(15,23,42,0.3)` over an opaque ground → the opaque hex a reader sees.
 *  A translucent token measured on its own is measured against nothing. */
function flatten(value: string, groundHex: string): string {
  const rgba = /rgba?\(([^)]+)\)/.exec(value);
  if (rgba === null) return value.startsWith("#") ? value : groundHex;
  const parts = (rgba[1] ?? "").split(",").map(Number);
  const [r = 0, g = 0, b = 0] = parts;
  const alpha = parts[3] ?? 1;
  const ground = [1, 3, 5].map((i) => Number.parseInt(groundHex.slice(i, i + 2), 16));
  return `#${[r, g, b]
    .map((c, i) => Math.round(c * alpha + (ground[i] ?? 0) * (1 - alpha)))
    .map((c) => c.toString(16).padStart(2, "0"))
    .join("")}`;
}

/** WCAG 2.1 AA for text. A standard, cited as such. */
const AA = 4.5;
/**
 * A DESIGN FLOOR, not a standards claim, and the distinction is deliberate.
 *
 * SC 1.4.11's 3:1 governs visual information REQUIRED TO IDENTIFY a component or
 * its state. A rule under a header identifies nothing; it separates. No reference
 * Amadou named clears 3:1 on a separator — Vercel's is about 1.17:1, Cloudflare's
 * about 1.3:1. The first draft of this file asserted 3:1 here anyway and went red
 * against a decision that was never wrong. A threshold nobody intends to meet is
 * not a strict witness, it is a broken one.
 *
 * LOWERED 1.8 → 1.4 ON 2026-08-03, and the lowering is the point of this comment.
 * A ratchet whose bound moves quietly is not a ratchet, so the reason is written
 * here, at the constant, and not only in a commit message:
 *
 *   · 2026-08-01 — Amadou reports the separators as invisible. They measured
 *     1.20–1.28:1. They go to 2.01–2.22:1, this floor is set at 1.8, and it is the
 *     right floor FOR THAT DECISION.
 *   · 2026-08-03 — he reports the result: "les pourtours trop vifs […] les rendre
 *     discret premium", same Cloudflare reference as before. Both reports are true.
 *     1.23 is invisible and 2.2 shouts; the answer was never at either end of the
 *     range, and holding the floor at 1.8 would have made this test forbid the
 *     correction rather than measure it.
 *
 * So the floor moves to 1.4 — still well above the 1.20:1 that produced the first
 * complaint, and above Cloudflare's own 1.24–1.30:1 rule, so this file continues to
 * refuse the state it was written to refuse. What it stops asserting is a specific
 * weight the design has since revised. The values it now guards land at 1.45–1.57:1.
 *
 * If it ever needs to move again: change it HERE, with the date and the report that
 * caused it. Never widen a pair's own `min` to dodge it.
 */
const SEPARATOR_FLOOR = 1.4;

/**
 * The dark separator was FROZEN at 1.19:1 for exactly one commit, and is not any more.
 *
 * It was frozen because Amadou's report said "en fond clair" and re-toning a theme
 * nobody complained about, on my own authority, inside a change about something else,
 * is not a fix — it is scope taken without asking. He then asked for the rest, so both
 * themes have been held to the SAME floor ever since. A frozen bound that goes away
 * because the debt was PAID is the only good ending for one.
 */

/** The pairs a reader's eye actually forms on these three pages. `ground` names the
 *  token the foreground sits on; `min` says which of the two bars applies. */
const PAIRS: ReadonlyArray<{
  fg: string;
  ground: string;
  min: number;
  what: string;
}> = [
  { fg: "--text-primary", ground: "--bg-app", min: AA, what: "headline on the page" },
  { fg: "--text-primary", ground: "--panel", min: AA, what: "card title" },
  { fg: "--text-secondary", ground: "--bg-app", min: AA, what: "sub-heading" },
  { fg: "--text-secondary", ground: "--panel", min: AA, what: "card body" },
  { fg: "--champagne", ground: "--panel", min: AA, what: "gold accent text" },
  { fg: "--cyan", ground: "--panel", min: AA, what: "cyan accent text" },
  { fg: "--rose", ground: "--panel", min: AA, what: "rose accent text" },
  { fg: "--amber", ground: "--panel", min: AA, what: "amber accent text" },
  { fg: "--success", ground: "--panel", min: AA, what: "success text" },
  { fg: "--danger", ground: "--panel", min: AA, what: "danger text" },
  { fg: "--indigo", ground: "--panel", min: AA, what: "indigo accent text" },
  { fg: "--violet", ground: "--panel", min: AA, what: "violet accent text" },
  { fg: "--border-subtle", ground: "--bg-app", min: SEPARATOR_FLOOR, what: "the header rule" },
  // The /espaces tiles, added 2026-08-02 when their surface stopped being a literal.
  // `flatten()` picks the LAST rgba() it finds in the dark gradient — which happens to be
  // its darkest stop, i.e. the worst case a reader meets. Stated because it is luck the
  // helper lands there, not design.
  { fg: "--text-primary", ground: "--launcher-tile-bg", min: AA, what: "surface tile title" },
  { fg: "--text-secondary", ground: "--launcher-tile-bg", min: AA, what: "surface tile body" },
];

// A DECLARED BLIND SPOT (ADR 0026): `--launcher-panel-bg` is `#ffffff` under "Clair" and a
// two-stop `color-mix()` gradient on the dark themes. `flatten()` cannot resolve a
// color-mix, and would silently fall back to the page ground — i.e. it would measure
// something else and report "ok". So the panel is NOT in the table above. What guards it
// instead is that its foregrounds all sit on `--panel`, which IS measured, and that the
// panel and `--panel` are re-toned together in the same block.

/** The pale ground each theme composites a translucent token over. */
const OPAQUE_GROUND: Record<string, string> = { dark: "#020817", light: "#fafafa" };

function measure(tokens: Map<string, string>, theme: "dark" | "light") {
  const ground = OPAQUE_GROUND[theme] ?? "#000000";
  const failures: string[] = [];
  let measured = 0;
  for (const pair of PAIRS) {
    const fgRaw = tokens.get(pair.fg);
    const bgRaw = tokens.get(pair.ground);
    if (fgRaw === undefined || bgRaw === undefined) {
      failures.push(`${theme}: ${pair.fg} or ${pair.ground} is not declared`);
      continue;
    }
    const bg = flatten(bgRaw, ground);
    const fg = flatten(fgRaw, bg);
    const ratio = contrast(fg, bg);
    measured++;
    if (ratio < pair.min) {
      failures.push(
        `${theme}: ${pair.what} — ${pair.fg} (${fg}) on ${pair.ground} (${bg}) = ${ratio.toFixed(2)}:1, below ${pair.min}`,
      );
    }
  }
  return { failures, measured };
}

describe("the launcher surface survives both themes", () => {
  it("finds the surface at all (anti-vacuity)", () => {
    expect(DARK.size).toBeGreaterThanOrEqual(25);
    expect(LIGHT.size).toBeGreaterThanOrEqual(25);
  });

  it("measures every declared pair (anti-vacuity)", () => {
    expect(measure(DARK, "dark").measured).toBe(PAIRS.length);
    expect(measure(LIGHT, "light").measured).toBe(PAIRS.length);
  });

  it("reads on the dark themes", () => {
    const { failures } = measure(DARK, "dark");
    expect(failures, failures.join("\n")).toHaveLength(0);
  });

  it("reads under Clair — the theme these pages used to ignore", () => {
    const { failures } = measure(LIGHT, "light");
    expect(failures, failures.join("\n")).toHaveLength(0);
  });

  it("withholds the wave band entirely under Clair, because it cannot be softened", () => {
    // This assertion used to say "dimmed, and greater than zero" — and dimming was the
    // wrong instrument. `tessera-waves-band.png` is 1672×372 8-bit **RGB**: no alpha. Its
    // ground is navy, so lowering the opacity does not reveal the waves on the page, it
    // composites the whole navy plate at that alpha. At 0.12 the result is a uniform
    // ~#dedee2 slab 300 px tall carrying two coloured smudges — reported on 2026-08-02 as
    // "le bas de la page ne ressemble plus à rien", which is precisely what it was.
    //
    // A decoration that cannot be re-toned does not belong on the pale ground at all. The
    // bottom of those pages is carried by `LauncherFooter` now. Pinned at exactly 0 so that
    // re-enabling it is a decision someone has to come here and make.
    expect(Number(LIGHT.get("--launcher-waves-opacity"))).toBe(0);
    expect(Number(DARK.get("--launcher-waves-opacity"))).toBe(1);
  });

  it("holds the cockpit's separator floor to the same number as this one", () => {
    // The two floors are declared in two files and the comments in both say they move
    // together. Prose that states an invariant and does not enforce it is how they
    // drift: on 2026-08-03 BOTH had to be lowered 1.8 → 1.4, and lowering one is a
    // one-character way to leave the cockpit holding a bar the launcher abandoned.
    const other = readFileSync(path.resolve(__dirname, "theme-contrast.test.ts"), "utf8");
    const found = /const SEPARATOR_FLOOR = ([\d.]+);/.exec(other);
    // Anti-vacuity: a renamed constant must fail LOUDLY, not match nothing and pass.
    expect(found, "theme-contrast.test.ts no longer declares SEPARATOR_FLOOR").not.toBeNull();
    expect(Number(found?.[1]), "the two separator floors have diverged").toBe(SEPARATOR_FLOOR);
  });

  it("keeps the /espaces tiles off black shadows under Clair", () => {
    // The two shadows this page carried were `0 18px 50px rgba(0,0,0,0.36)` (panel) and
    // `0 12px 28px rgba(0,0,0,0.34)` (tile hover). Both were literals in TSX, and both are
    // depth on navy and a grey bruise on #fafafa. The rule is not "no shadow" — it is that
    // a light surface never lifts on pure black at a third of full strength.
    for (const token of [
      "--launcher-panel-shadow",
      "--launcher-tile-shadow",
      "--launcher-tile-shadow-hover",
    ]) {
      const value = LIGHT.get(token);
      expect(value, `${token} is not declared under Clair`).toBeDefined();
      for (const [, alpha] of (value ?? "").matchAll(
        /rgba\(\s*0\s*,\s*0\s*,\s*0\s*,\s*([\d.]+)/g,
      )) {
        expect(
          Number(alpha),
          `${token} lifts on pure black at ${alpha} under Clair`,
        ).toBeLessThanOrEqual(0.08);
      }
    }
  });
});
