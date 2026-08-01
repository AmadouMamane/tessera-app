// The RATCHET over foreground colours that cannot survive a theme flip
// (docs/ui-style-reference.md §4).
//
// A colour written as a LITERAL does not flip. The cockpit re-tones ONE set of
// `--tessera-*` variables per theme, so every surface follows automatically — except
// wherever a class string named a colour outright. Those literals were all chosen against
// a DARK card, so under "Clair" they land on white: on 2026-08-01, 738 of them scored
// below WCAG AA, most of them far below. The sidebar's AGENTS / GOUVERNER / PLATEFORME
// headers were white on a white rail (1.00:1). Every page's biggest number — the KPI
// value — was white on a white card. `text-emerald-300` scored 1.52:1, `text-[#87bfff]`
// 1.92:1, where AA asks 4.5:1.
//
// ONE RULE, MEASURED, NOT NAMED. This does not blacklist `text-white` or any palette
// shade: it resolves each foreground literal to its actual hex and computes the WCAG
// contrast it would have on the light theme's card. Below 4.5:1 → red. That is why it
// catches `text-white`, `text-emerald-300` and `text-[#87bfff]` with the same sentence,
// and why a NEW pale colour nobody has thought of yet is caught too.
//
// THE ONE EXEMPTION. A literal is fine when the SAME class string also sets an OPAQUE,
// non-theme background — a red count badge, the violet primary button, a navy gradient.
// That background is the same colour under every theme, so its foreground must not move
// either. A TRANSLUCENT tint does NOT count: `bg-[#b9a6ff]/15` over a white card is
// white, which is the bug itself.
//
// WHAT THIS WITNESS CANNOT SEE, said out loud (ADR 0026). It reads one literal at a time,
// so it cannot know a background set by an ANCESTOR. That is the whole content of the
// frozen set: the alert ribbon's own opaque `bg-[#1f0e16]` band, and the Credit Aurore
// navy headers. Held two-sided at its measured size, so it can only ever shrink.
//
// SECOND RULE, SAME DISEASE, OTHER GRAMMAR: SVG PAINT. A chart line is not a class string.
// `stroke="#34d399"` is a presentation attribute, so the scan above — which only reads
// inside string literals — never saw one, and reported green over 20 chart traces that were
// unreadable under "Clair": eight emerald-400 gauge arcs and sparklines at 1.92:1, four
// emerald-500 lines at 2.54:1, a cyan cost line at 1.81:1. They are measured here against
// 3:1, not 4.5:1 — WCAG 2.1 SC 1.4.11 asks 3:1 of a GRAPHICAL object; 4.5:1 is what body
// text owes. Two thresholds because there are two kinds of thing, not to be lenient.
//
// THIRD RULE — THE COLOUR CONSTANT, which is where the second rule's blind spot lived. A
// paint fed by an EXPRESSION — `stroke={s.color}`, `stroke={DONUT_COLORS[i]}` — keeps its
// colour in a JS table, and a per-attribute scan cannot follow it there. That population was
// counted (48 sites) rather than measured, and counting was too weak: behind those 48 sites
// sat 142 hex constants below 3:1, one of which drew a 1.92:1 availability line on a white
// card that an operator could see. So the witness now reads the constants themselves —
// every bare `"#rrggbb"` in a `.ts`/`.tsx`, wherever it lives — and measures it.
//
// A STRONGER WITNESS REPLACING A WEAKER ONE IS NOT A LOOSENING. The count survives below as
// a secondary bound, but it no longer stands in for the thing: the colours it used to hide
// are now measured one by one.
//
// WHAT EVEN THIS CANNOT SEE, said plainly: a colour that arrives from the API — `c.color ??
// "#2e72d2"` in the sources tree — is not in the source at all. The fallback is measured;
// the served value is not. No number is offered for it, because a number nobody can compute
// is worse than the admission.
//
// Mutation contract (each verified red before landing):
//   · restore `text-white` on the sidebar's super-section header  → red, named by line;
//   · restore `text-emerald-300` on a card                        → red;
//   · claim a translucent tint counts as a background             → red;
//   · lower a frozen count without removing the literal           → red;
//   · point the scan at nothing                                   → red (anti-vacuity);
//   · restore `stroke="#34d399"` on a real chart                  → red, named by line;
//   · let the expression-fed population grow by one               → red;
//   · put a pale hex back in a colour TABLE                       → red, named by line.
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/** The trees this ratchet governs: the whole rendered surface of both apps — and `lib`,
 *  because a class map is not always in a component. `lib/overview.ts` holds the shared
 *  tone table every fleet status pill reads; scanning only `.tsx` left it unpoliced. */
const SCANNED_DIRS = ["components", "app", "lib"] as const;
const SCANNED_EXTENSIONS = [".tsx", ".ts"] as const;

/** Anti-vacuity: 238 `.tsx` were scanned on 2026-08-01 (more now that `.ts` and `lib` count); a floor just under it catches a
 *  scan pointed at nothing without going red because one component was deleted. */
const EXPECTED_MIN_FILES = 230;
/** ...and the resolver must still turn utilities into hexes, or "0 violations" would only
 *  mean the regex stopped matching. 69 literals still resolve AFTER the sweep (the ones
 *  that already clear AA, plus the frozen set); a floor of 60 keeps that witness alive.
 *  The exact-count assertion on the frozen set below is the second, stronger witness. */
const EXPECTED_MIN_RESOLVED = 60;

/** WCAG 2.1 AA for body text. */
const AA = 4.5;
/** WCAG 2.1 SC 1.4.11 for non-text content — a chart line, a gauge arc, a legend swatch.
 *  A graphical object owes 3:1, not the 4.5:1 a glyph owes. Applying 4.5 here would be a
 *  different (stricter) rule than the standard, and applying 4.5's exemptions to a stroke
 *  would be a weaker one; both would make the number mean something else. */
const AA_NON_TEXT = 3;
/** The lightest surface a cockpit foreground can land on: a card under "Clair". */
const LIGHT_CARD = "#ffffff";

/**
 * Occurrences whose dark background comes from an ANCESTOR, which a per-literal scan
 * cannot see. TWO-SIDED — the count must match exactly — so it can only SHRINK.
 *
 * · the Credit Aurore product/collections decor carries a navy header that is navy under
 *   every cockpit theme; it never consumed the `--tessera-*` surface tokens.
 *
 * `alert-ribbon` used to hold 15 of these and now holds none. It was the honest case for
 * the exemption — a band that paints its own dark ground, whose children legitimately
 * wear pale ink — right up until someone asked whether a dark slab belongs on a light
 * page at all. It does not, and the answer was a design decision rather than a fix, which
 * is exactly why it sat frozen instead of being quietly "corrected". Now the band flips
 * with the theme and names no colour at all, so the exemption has nothing left to cover.
 */
const FROZEN_ANCESTOR_BACKED: ReadonlyMap<string, number> = new Map([
  ["components/product/chat-widget.tsx", 6],
  ["components/product/mes-comptes-host.tsx", 6],
  ["components/recouvrement/recouvrement-product-experience.tsx", 4],
  ["components/recouvrement/recouvrement-logo.tsx", 1],
]);

/**
 * SVG paint whose colour IS the content, not a role. A logo that changes hue is no longer
 * the logo; an illustration of a card and a coin is not a status. Each also sits on ground
 * painted by an ANCESTOR — a navy product header, a lilac panel — which a per-attribute
 * scan cannot see. TWO-SIDED at its measured size, so it can only SHRINK.
 */
const FROZEN_DECORATIVE_PAINT: ReadonlyMap<string, number> = new Map([
  ["components/brand/credit-aurore-logo.tsx", 3],
  ["components/product/credit-aurore-mes-comptes-host.tsx", 8],
  ["components/recouvrement/recouvrement-product-experience.tsx", 6],
]);

/** Anti-vacuity for the paint rule: 34 hex paint attributes survive the sweep (the frozen
 *  decor, plus the handful that already clear 3:1). A floor just under it catches a regex
 *  that stopped matching, which would otherwise read as "no chart is broken". */
const EXPECTED_MIN_PAINTS = 30;

/** Sites whose paint is resolved at RUNTIME rather than written on the element. Their
 *  constants are measured by the third rule now, so this is no longer the primary witness
 *  — it is a secondary bound, held downward-only, on how much of the surface answers to a
 *  value this scan reads indirectly. */
const UNSEEN_EXPRESSION_FED = 48;

/** Decorative colour CONSTANTS where the colour is the content, or where the component
 *  carries its own painted ground. TWO-SIDED, so it can only shrink.
 *
 *  · `theme-swatch` paints the disc that REPRESENTS a theme. Making the pale-neutral swatch
 *    darker so it clears contrast would make it stop being the pale neutral theme.
 *
 *  `landing-launcher` held 14 of these until 2026-08-01 and now holds none. It was the
 *  honest case for the exemption — a page that declared its own scoped design system as
 *  inline custom properties over its own panel — right up until someone noticed that an
 *  inline style attribute is precisely what a theme class cannot reach, which is why the
 *  theme control on /login, /espaces and /select-space did nothing at all. The tokens
 *  moved into `.launcher-surface` in the stylesheet, so they left this scan's tree.
 *  THAT IS NOT THE SAME AS BEING SAFE: they are measured now by
 *  `launcher-surface-contrast.test.ts`, which reads them where they live and holds both
 *  themes. A value that merely walks out of one witness's field of view has not been
 *  checked; it has been hidden. */
const FROZEN_DECOR_CONSTANT: ReadonlyMap<string, number> = new Map([
  ["components/layout/theme-swatch.tsx", 1],
]);

/** Anti-vacuity for the constant rule. Was 20 against a population of 25; the launcher's
 *  14 left the tree for the stylesheet on 2026-08-01, so 9 remain here and the floor
 *  follows them down. Lowering an anti-vacuity floor is exactly how a witness goes blind,
 *  so it is only defensible because the colours did not disappear — they are measured by
 *  `launcher-surface-contrast.test.ts` instead, and that file is the reason this number
 *  may move. Nothing else licenses it. */
const EXPECTED_MIN_CONSTANTS = 8;

/** The Tailwind shades ever used as a foreground here, 100 → 600. The 400/500 band matters
 *  as much as the pale end: `emerald-400` is 1.92:1 on a white card, `amber-500` 2.15:1. */
const SHADES = ["100", "200", "300", "400", "500", "600"] as const;
type Ramp = readonly [string, string, string, string, string, string];
const PALETTE: Readonly<Record<string, Ramp>> = {
  slate: ["#f1f5f9", "#e2e8f0", "#cbd5e1", "#94a3b8", "#64748b", "#475569"],
  gray: ["#f3f4f6", "#e5e7eb", "#d1d5db", "#9ca3af", "#6b7280", "#4b5563"],
  zinc: ["#f4f4f5", "#e4e4e7", "#d4d4d8", "#a1a1aa", "#71717a", "#52525b"],
  neutral: ["#f5f5f5", "#e5e5e5", "#d4d4d4", "#a3a3a3", "#737373", "#525252"],
  stone: ["#f5f5f4", "#e7e5e4", "#d6d3d1", "#a8a29e", "#78716c", "#57534e"],
  red: ["#fee2e2", "#fecaca", "#fca5a5", "#f87171", "#ef4444", "#dc2626"],
  orange: ["#ffedd5", "#fed7aa", "#fdba74", "#fb923c", "#f97316", "#ea580c"],
  amber: ["#fef3c7", "#fde68a", "#fcd34d", "#fbbf24", "#f59e0b", "#d97706"],
  yellow: ["#fef9c3", "#fef08a", "#fde047", "#facc15", "#eab308", "#ca8a04"],
  lime: ["#ecfccb", "#d9f99d", "#bef264", "#a3e635", "#84cc16", "#65a30d"],
  green: ["#dcfce7", "#bbf7d0", "#86efac", "#4ade80", "#22c55e", "#16a34a"],
  emerald: ["#d1fae5", "#a7f3d0", "#6ee7b7", "#34d399", "#10b981", "#059669"],
  teal: ["#ccfbf1", "#99f6e4", "#5eead4", "#2dd4bf", "#14b8a6", "#0d9488"],
  cyan: ["#cffafe", "#a5f3fc", "#67e8f9", "#22d3ee", "#06b6d4", "#0891b2"],
  sky: ["#e0f2fe", "#bae6fd", "#7dd3fc", "#38bdf8", "#0ea5e9", "#0284c7"],
  blue: ["#dbeafe", "#bfdbfe", "#93c5fd", "#60a5fa", "#3b82f6", "#2563eb"],
  indigo: ["#e0e7ff", "#c7d2fe", "#a5b4fc", "#818cf8", "#6366f1", "#4f46e5"],
  violet: ["#ede9fe", "#ddd6fe", "#c4b5fd", "#a78bfa", "#8b5cf6", "#7c3aed"],
  purple: ["#f3e8ff", "#e9d5ff", "#d8b4fe", "#c084fc", "#a855f7", "#9333ea"],
  fuchsia: ["#fae8ff", "#f5d0fe", "#f0abfc", "#e879f9", "#d946ef", "#c026d3"],
  pink: ["#fce7f3", "#fbcfe8", "#f9a8d4", "#f472b6", "#ec4899", "#db2777"],
  rose: ["#ffe4e6", "#fecdd3", "#fda4af", "#fb7185", "#f43f5e", "#e11d48"],
  // The Tessera brand ramp (declared in globals.css `@theme`), not a Tailwind default.
  gold: ["#f6eed9", "#f2e7c4", "#e8d5a8", "#dfc89a", "#d7be8a", "#c5ab6a"],
};

// The trailing `(\/\d{1,3})?` is load-bearing: `text-amber-200/70` is amber-200 at 70 %,
// which on a white card is WEAKER than the full-strength colour, not exempt from it. An
// earlier version ended `(?![\w/-])` and so skipped every opacity-modified foreground —
// 52 of them, including the ones in the `comprendre` guides.
const FOREGROUND =
  /(?<![\w:-])(?:group-hover:|hover:|focus:|focus-visible:|active:)?text-(?:\[#([0-9a-fA-F]{6})\]|([a-z]+)-(100|200|300|400|500|600)|(white))(\/\d{1,3})?(?![\w/-])/g;

const OPAQUE_BACKGROUND =
  /bg-(?:blue|red|amber|emerald|green|sky|violet|rose|orange|cyan|indigo|fuchsia|slate|zinc|neutral|gray|navy|danger|success|warning|info)-\d{2,3}(?![\d\/])|bg-\[#[0-9a-fA-F]{6}\](?!\/)|bg-\[linear-gradient|bg-gradient-to|bg-\[var\(--tessera-danger|bg-black/;

const STRING_LITERAL = /"[^"\n]*"|`[^`]*`|'[^'\n]*'/g;

/** A paint written straight onto the element. `stopColor` counts: a gradient stop under a
 *  sparkline is the same ink as the line above it, and letting it drift leaves the area
 *  fill emerald-400 while the line it belongs to has become emerald-700. */
const SVG_PAINT = /\b(?:stroke|fill|stopColor)="(#[0-9a-fA-F]{3,8})"/g;

/** The same three attributes fed by an expression — the population bounded above. */
const SVG_PAINT_EXPRESSION = /\b(?:stroke|fill|stopColor)=\{/g;

/** A bare colour CONSTANT: a quoted hex that is a value in its own right — an entry in a
 *  `DONUT_COLORS` table, a `color:` field, a ternary arm, an inline `background:`. The
 *  `(?<!=)` is what keeps this rule distinct from the paint rule above: `stroke="#34d399"`
 *  is an attribute and belongs to that one. A hex inside a class string never matches
 *  either — `bg-[#0d3561]` has a bracket between the hex and the quote, and a chip that
 *  paints its own opaque ground is not this rule's business. */
const COLOUR_CONSTANT = /(?<![\w=])(['"])(#[0-9a-fA-F]{6})\1/g;

interface Finding {
  readonly file: string;
  readonly line: number;
  readonly utility: string;
  readonly ratio: number;
}

function srgbChannel(byte: number): number {
  const value = byte / 255;
  return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
}

/** `#fff`, `#ffffff` and `#ffffff80` all name a colour; only the middle one is 7 chars.
 *  The alpha of an 8-digit paint is dropped deliberately: over a white card, translucency
 *  only ever WEAKENS the contrast, so judging the opaque value is the lenient reading — it
 *  can produce a false green, never a false red. */
function normaliseHex(raw: string): string | null {
  const body = raw.slice(1);
  if (body.length === 3 || body.length === 4)
    return `#${body
      .slice(0, 3)
      .split("")
      .map((c) => c + c)
      .join("")}`;
  if (body.length === 6 || body.length === 8) return `#${body.slice(0, 6)}`;
  return null;
}

function relativeLuminance(hex: string): number {
  const r = srgbChannel(Number.parseInt(hex.slice(1, 3), 16));
  const g = srgbChannel(Number.parseInt(hex.slice(3, 5), 16));
  const b = srgbChannel(Number.parseInt(hex.slice(5, 7), 16));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(foreground: string, background: string): number {
  const a = relativeLuminance(foreground);
  const b = relativeLuminance(background);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

/** Split one source into the foregrounds that fail on a white card and the resolved total. */
function scanSource(file: string, source: string): { failing: Finding[]; resolved: number } {
  const failing: Finding[] = [];
  let resolved = 0;
  for (const literal of source.matchAll(STRING_LITERAL)) {
    const body = literal[0];
    if (OPAQUE_BACKGROUND.test(body)) continue;
    // A literal that already pairs a base colour with a `dark:` variant is theme-aware:
    // the base IS the light value and the variant IS the dark one. Tokenising it would
    // throw away a correct answer the repo already wrote (`text-emerald-600
    // dark:text-emerald-400`). 57 literals are in that shape; they are not defects.
    if (body.includes("dark:text-")) continue;
    for (const match of body.matchAll(FOREGROUND)) {
      const [utility, hex, family, shade, white] = match;
      void match; // `match[5]` is the opacity modifier: captured to be consumed, not used.
      const colour = white
        ? "#ffffff"
        : hex
          ? `#${hex}`
          : (PALETTE[family ?? ""]?.[SHADES.indexOf((shade ?? "") as (typeof SHADES)[number])] ??
            "");
      if (!colour) continue;
      resolved += 1;
      const ratio = contrast(colour, LIGHT_CARD);
      if (ratio >= AA) continue;
      failing.push({
        file,
        line: source.slice(0, literal.index ?? 0).split("\n").length,
        utility,
        ratio: Math.round(ratio * 100) / 100,
      });
    }
  }
  return { failing, resolved };
}

/** Split one source into the SVG paints that fail 3:1 on a white card, the resolved total,
 *  and the count of paints this witness cannot resolve at all. */
function scanPaint(
  file: string,
  source: string,
): { failing: Finding[]; resolved: number; unseen: number } {
  const failing: Finding[] = [];
  let resolved = 0;
  for (const match of source.matchAll(SVG_PAINT)) {
    const colour = normaliseHex(match[1] ?? "");
    if (!colour) continue;
    resolved += 1;
    const ratio = contrast(colour, LIGHT_CARD);
    if (ratio >= AA_NON_TEXT) continue;
    failing.push({
      file,
      line: source.slice(0, match.index ?? 0).split("\n").length,
      utility: match[0],
      ratio: Math.round(ratio * 100) / 100,
    });
  }
  return { failing, resolved, unseen: [...source.matchAll(SVG_PAINT_EXPRESSION)].length };
}

/** Split one source into the bare colour constants that fail 3:1 on a white card. Same
 *  threshold as the paint rule: a constant here ends up as a chart line, a donut arc or a
 *  data bar — a graphical object either way, never body text. */
function scanConstants(file: string, source: string): { failing: Finding[]; resolved: number } {
  const failing: Finding[] = [];
  let resolved = 0;
  for (const match of source.matchAll(COLOUR_CONSTANT)) {
    const colour = normaliseHex(match[2] ?? "");
    if (!colour) continue;
    resolved += 1;
    const ratio = contrast(colour, LIGHT_CARD);
    if (ratio >= AA_NON_TEXT) continue;
    failing.push({
      file,
      line: source.slice(0, match.index ?? 0).split("\n").length,
      utility: match[2] ?? "",
      ratio: Math.round(ratio * 100) / 100,
    });
  }
  return { failing, resolved };
}

function walkSources(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walkSources(full, acc);
    else if (
      SCANNED_EXTENSIONS.some((ext) => entry.name.endsWith(ext)) &&
      !entry.name.includes(".test.")
    )
      acc.push(full);
  }
  return acc;
}

interface TreeScan {
  readonly failing: Finding[];
  readonly resolved: number;
  readonly files: number;
  readonly paintFailing: Finding[];
  readonly paintResolved: number;
  readonly unseen: number;
  readonly constFailing: Finding[];
  readonly constResolved: number;
}

function scanTree(): TreeScan {
  const root = process.cwd();
  const failing: Finding[] = [];
  const paintFailing: Finding[] = [];
  const constFailing: Finding[] = [];
  let resolved = 0;
  let paintResolved = 0;
  let constResolved = 0;
  let unseen = 0;
  let files = 0;
  for (const dir of SCANNED_DIRS) {
    for (const absolute of walkSources(path.join(root, dir))) {
      files += 1;
      const relative = path.relative(root, absolute);
      const source = readFileSync(absolute, "utf8");
      const found = scanSource(relative, source);
      failing.push(...found.failing);
      resolved += found.resolved;
      const painted = scanPaint(relative, source);
      paintFailing.push(...painted.failing);
      paintResolved += painted.resolved;
      unseen += painted.unseen;
      const constants = scanConstants(relative, source);
      constFailing.push(...constants.failing);
      constResolved += constants.resolved;
    }
  }
  return {
    failing,
    resolved,
    files,
    paintFailing,
    paintResolved,
    unseen,
    constFailing,
    constResolved,
  };
}

describe("every foreground literal survives the light theme", () => {
  const scan = scanTree();

  it("sees the whole rendered surface, and actually resolves colours", () => {
    expect(scan.files).toBeGreaterThanOrEqual(EXPECTED_MIN_FILES);
    expect(scan.resolved).toBeGreaterThanOrEqual(EXPECTED_MIN_RESOLVED);
  });

  it("leaves no sub-AA foreground outside the frozen ancestor-backed set", () => {
    const offending = scan.failing.filter((f) => !FROZEN_ANCESTOR_BACKED.has(f.file));
    expect(
      offending.map((f) => `${f.file}:${f.line}  ${f.utility}  ${f.ratio}:1 on a white card`),
      "use a --tessera-fg-* / --tessera-text-* token; a literal needs its OWN opaque background",
    ).toEqual([]);
  });

  it("holds the frozen set at its exact measured size, so it can only shrink", () => {
    const actual: Record<string, number> = {};
    for (const finding of scan.failing) {
      if (!FROZEN_ANCESTOR_BACKED.has(finding.file)) continue;
      actual[finding.file] = (actual[finding.file] ?? 0) + 1;
    }
    expect(actual).toEqual(Object.fromEntries(FROZEN_ANCESTOR_BACKED));
  });

  it("has teeth: the two defects that started this are rejected if restored", () => {
    const superHeader = scanSource(
      "sidebar.tsx",
      'cn("border-l-2 text-[0.7rem] uppercase tracking-[0.1em] text-white", ACCENT[a])',
    );
    expect(superHeader.failing.map((f) => f.ratio)).toEqual([1]);

    const status = scanSource("x.tsx", '"text-xs font-medium text-emerald-300"');
    expect(status.failing).toHaveLength(1);
    expect(status.failing[0]?.ratio).toBeLessThan(2);
  });

  it("has teeth: a translucent tint is not a background, an opaque chip is", () => {
    const tinted = scanSource("x.tsx", '"border-[#b9a6ff]/60 bg-[#b9a6ff]/15 text-white"');
    expect(tinted.failing).toHaveLength(1);

    const chip = scanSource("x.tsx", '"rounded-full bg-red-500 px-1 text-white"');
    expect(chip.failing).toEqual([]);
    expect(chip.resolved).toBe(0);
  });

  // The exemption regex once ended `\d{2,3}(?!\/)`, and a quantifier BACKTRACKS: on
  // `bg-amber-500/10` it matched `50`, saw `0` instead of `/`, and declared the tint an
  // opaque background. 227 status pills -- PRET, BLOQUE, "57 metier en attente", the ones
  // an operator actually reads on the fleet page -- were skipped by a lookahead that was
  // never reached. The screen found it; the test had said green.
  it("has teeth: a shade followed by an opacity modifier is still translucent", () => {
    const pill = scanSource("x.tsx", '"border-amber-500/35 bg-amber-500/10 text-amber-200"');
    expect(pill.failing).toHaveLength(1);
    expect(pill.failing[0]?.utility).toBe("text-amber-200");
  });

  it("has teeth: a token passes, because a token is not a literal", () => {
    const tokenised = scanSource("x.tsx", '"text-xs text-[var(--tessera-fg-success)]"');
    expect(tokenised.failing).toEqual([]);
  });
});

describe("every SVG chart paint survives the light theme", () => {
  const scan = scanTree();

  it("sees the paint attributes at all, and actually resolves them", () => {
    expect(scan.paintResolved).toBeGreaterThanOrEqual(EXPECTED_MIN_PAINTS);
  });

  it("leaves no sub-3:1 chart paint outside the frozen decorative set", () => {
    const offending = scan.paintFailing.filter((f) => !FROZEN_DECORATIVE_PAINT.has(f.file));
    expect(
      offending.map((f) => `${f.file}:${f.line}  ${f.utility}  ${f.ratio}:1 on a white card`),
      "a chart trace is a graphical object: use a --tessera-fg-* token so it flips with the theme",
    ).toEqual([]);
  });

  it("holds the decorative set at its exact measured size, so it can only shrink", () => {
    const actual: Record<string, number> = {};
    for (const finding of scan.paintFailing) {
      if (!FROZEN_DECORATIVE_PAINT.has(finding.file)) continue;
      actual[finding.file] = (actual[finding.file] ?? 0) + 1;
    }
    expect(actual).toEqual(Object.fromEntries(FROZEN_DECORATIVE_PAINT));
  });

  // ADR 0026: a witness that cannot see must say so, and must never report "ok" over the
  // part it cannot see. This one cannot follow `stroke={s.color}` into a JS colour table.
  // So it counts that population instead, and refuses to let it grow.
  it("says out loud what it cannot see, and refuses to let that grow", () => {
    expect(
      scan.unseen,
      "a paint fed by an expression is invisible to this scan — tokenise it, do not add one",
    ).toBeLessThanOrEqual(UNSEEN_EXPRESSION_FED);
  });

  it("has teeth: restoring an emerald chart stroke is rejected, named and measured", () => {
    const arc = scanPaint("gauge.tsx", '<circle fill="none" stroke="#34d399" strokeWidth="3" />');
    expect(arc.failing).toHaveLength(1);
    expect(arc.failing[0]?.ratio).toBe(1.92);

    const dot = scanPaint("spark.tsx", '<circle r={0.9} fill="#10b981" />');
    expect(dot.failing.map((f) => f.ratio)).toEqual([2.54]);

    const stop = scanPaint("area.tsx", '<stop offset="0%" stopColor="#34d399" />');
    expect(stop.failing).toHaveLength(1);
  });

  it("has teeth: the threshold really is 3:1, not the 4.5:1 owed by text", () => {
    // #8b7cf0 scores 3.37:1 — a failing GLYPH, a passing chart line. One colour, two
    // verdicts, which is the whole reason the two rules do not share a number.
    const line = scanPaint("x.tsx", '<path stroke="#8b7cf0" />');
    expect(line.resolved).toBe(1);
    expect(line.failing).toEqual([]);
    expect(contrast("#8b7cf0", LIGHT_CARD)).toBeLessThan(AA);
  });

  it("has teeth: a token passes, a short hex is still read", () => {
    const tokenised = scanPaint("x.tsx", '<path stroke="var(--tessera-fg-success)" />');
    expect(tokenised.resolved).toBe(0);
    expect(tokenised.failing).toEqual([]);

    const short = scanPaint("x.tsx", '<path stroke="#fff" />');
    expect(short.failing.map((f) => f.ratio)).toEqual([1]);
  });

  it("has teeth: an expression-fed paint is counted as unseen, not as clean", () => {
    const expression = scanPaint("x.tsx", "<path stroke={DONUT_COLORS[i]} fill={s.color} />");
    expect(expression.resolved).toBe(0);
    expect(expression.failing).toEqual([]);
    expect(expression.unseen).toBe(2);
  });
});

describe("every colour constant survives the light theme", () => {
  const scan = scanTree();

  it("reads the constants at all, and actually resolves them", () => {
    expect(scan.constResolved).toBeGreaterThanOrEqual(EXPECTED_MIN_CONSTANTS);
  });

  it("leaves no sub-3:1 colour constant outside the frozen decor", () => {
    const offending = scan.constFailing.filter((f) => !FROZEN_DECOR_CONSTANT.has(f.file));
    expect(
      offending.map((f) => `${f.file}:${f.line}  ${f.utility}  ${f.ratio}:1 on a white card`),
      "a colour table paints charts: use --tessera-cat-* for identity, --tessera-fg-* for a verdict",
    ).toEqual([]);
  });

  it("holds the frozen decor at its exact measured size, so it can only shrink", () => {
    const actual: Record<string, number> = {};
    for (const finding of scan.constFailing) {
      if (!FROZEN_DECOR_CONSTANT.has(finding.file)) continue;
      actual[finding.file] = (actual[finding.file] ?? 0) + 1;
    }
    expect(actual).toEqual(Object.fromEntries(FROZEN_DECOR_CONSTANT));
  });

  it("has teeth: a pale hex back in a colour table is rejected, named and measured", () => {
    const table = scanConstants("board.tsx", 'const DONUT_COLORS = ["#34d399", "#60a5fa"];');
    expect(table.failing.map((f) => `${f.utility} ${f.ratio}`)).toEqual([
      "#34d399 1.92",
      "#60a5fa 2.54",
    ]);

    const ternary = scanConstants("x.tsx", 'const t = ok ? "#10b981" : "#ef4444";');
    expect(ternary.failing.map((f) => f.utility)).toEqual(["#10b981"]);
  });

  it("has teeth: it does not poach the other two rules' territory", () => {
    // An ATTRIBUTE belongs to the paint rule — counting it here would double-report it.
    const attribute = scanConstants("x.tsx", '<path stroke="#34d399" />');
    expect(attribute.resolved).toBe(0);

    // A hex inside a class string belongs to the foreground rule, which knows about the
    // opaque-background exemption this rule has no way to evaluate.
    const utility = scanConstants("x.tsx", '"rounded bg-[#0d3561] text-[#d8eaff]"');
    expect(utility.resolved).toBe(0);

    // A token is not a literal, here as everywhere.
    const token = scanConstants("x.tsx", 'const c = "var(--tessera-cat-1)";');
    expect(token.resolved).toBe(0);
  });
});
