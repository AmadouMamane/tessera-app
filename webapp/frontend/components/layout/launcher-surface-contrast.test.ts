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
//   · drop `--border-subtle` light back to 0.12 alpha     → red at 1.28:1;
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
 * about 1.3:1 — and the cockpit's own new chrome line, chosen the same day and on
 * purpose, is 2.01:1. The first draft of this file asserted 3:1 here anyway and
 * went red against a decision that was never wrong. A threshold nobody intends to
 * meet is not a strict witness, it is a broken one.
 *
 * So separators are held at the level the design actually decided: at least as
 * strong as the cockpit's chrome line, i.e. visibly present rather than the
 * 1.28:1 hairline that started this whole conversation.
 */
const SEPARATOR_FLOOR = 1.8;

/**
 * The dark separator, FROZEN at its measured value rather than raised.
 *
 * Amadou's report was explicit about scope: "en fond clair". The dark launcher's
 * rule measures 1.20:1 — the same faintness the light one had — but touching it
 * would be re-toning a theme nobody complained about, on my own authority, inside
 * a change about something else. So it is recorded at what it is, one-sided: it may
 * rise, never fall. That is a debt written down, not a defect called fixed.
 */
const DARK_SEPARATOR_FROZEN = 1.19;

/** The pairs a reader's eye actually forms on these three pages. `ground` names the
 *  token the foreground sits on; `min` says which of the two standards applies, and
 *  `darkMin` overrides it where the two themes are honestly held to different bars. */
const PAIRS: ReadonlyArray<{
  fg: string;
  ground: string;
  min: number;
  darkMin?: number;
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
  {
    fg: "--border-subtle",
    ground: "--bg-app",
    min: SEPARATOR_FLOOR,
    darkMin: DARK_SEPARATOR_FROZEN,
    what: "the header rule",
  },
];

/** The pale ground each theme composites a translucent token over. */
const OPAQUE_GROUND: Record<string, string> = { dark: "#020817", light: "#f6f8fc" };

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
    const floor = theme === "dark" && pair.darkMin !== undefined ? pair.darkMin : pair.min;
    measured++;
    if (ratio < floor) {
      failures.push(
        `${theme}: ${pair.what} — ${pair.fg} (${fg}) on ${pair.ground} (${bg}) = ${ratio.toFixed(2)}:1, below ${floor}`,
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

  it("keeps the light waves softened, so the band is not a dark slab on a pale page", () => {
    // The wave artwork is night-blue. The alert ribbon already made this mistake
    // once (a dark band on a light cockpit) and it took a design decision, not a
    // fix, to undo. Here the band is dimmed by token instead.
    const opacity = Number(LIGHT.get("--launcher-waves-opacity"));
    expect(opacity).toBeGreaterThan(0);
    expect(opacity).toBeLessThanOrEqual(0.5);
    expect(Number(DARK.get("--launcher-waves-opacity"))).toBe(1);
  });
});
