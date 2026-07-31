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
// Mutation contract (each verified red before landing):
//   · restore `text-white` on the sidebar's super-section header  → red, named by line;
//   · restore `text-emerald-300` on a card                        → red;
//   · claim a translucent tint counts as a background             → red;
//   · lower a frozen count without removing the literal           → red;
//   · point the scan at nothing                                   → red (anti-vacuity).
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/** The trees this ratchet governs: the whole rendered surface of both apps. */
const SCANNED_DIRS = ["components", "app"] as const;

/** Anti-vacuity: 238 `.tsx` were scanned on 2026-08-01; a floor just under it catches a
 *  scan pointed at nothing without going red because one component was deleted. */
const EXPECTED_MIN_FILES = 230;
/** ...and the resolver must still turn utilities into hexes, or "0 violations" would only
 *  mean the regex stopped matching. 69 literals still resolve AFTER the sweep (the ones
 *  that already clear AA, plus the frozen set); a floor of 60 keeps that witness alive.
 *  The exact-count assertion on the frozen set below is the second, stronger witness. */
const EXPECTED_MIN_RESOLVED = 60;

/** WCAG 2.1 AA for body text. */
const AA = 4.5;
/** The lightest surface a cockpit foreground can land on: a card under "Clair". */
const LIGHT_CARD = "#ffffff";

/**
 * Occurrences whose dark background comes from an ANCESTOR, which a per-literal scan
 * cannot see. TWO-SIDED — the count must match exactly — so it can only SHRINK.
 *
 * · `alert-ribbon` paints its own opaque `bg-[#1f0e16]` / `bg-[#1d1606]` / `bg-[#0e1f17]`
 *   band, dark under every theme, and its children inherit it.
 * · the Credit Aurore product/collections decor carries a navy header that is navy under
 *   every cockpit theme; it never consumed the `--tessera-*` surface tokens.
 */
const FROZEN_ANCESTOR_BACKED: ReadonlyMap<string, number> = new Map([
  ["components/cockpit/alert-ribbon.tsx", 10],
  ["components/recouvrement/recouvrement-product-experience.tsx", 4],
  ["components/product/chat-widget.tsx", 2],
  ["components/product/mes-comptes-host.tsx", 1],
  ["components/recouvrement/recouvrement-logo.tsx", 1],
]);

/** The pale end of the Tailwind palette — the shades ever used as a foreground here. */
const PALETTE: Readonly<Record<string, readonly [string, string, string]>> = {
  slate: ["#f1f5f9", "#e2e8f0", "#cbd5e1"],
  gray: ["#f3f4f6", "#e5e7eb", "#d1d5db"],
  zinc: ["#f4f4f5", "#e4e4e7", "#d4d4d8"],
  neutral: ["#f5f5f5", "#e5e5e5", "#d4d4d4"],
  stone: ["#f5f5f4", "#e7e5e4", "#d6d3d1"],
  red: ["#fee2e2", "#fecaca", "#fca5a5"],
  orange: ["#ffedd5", "#fed7aa", "#fdba74"],
  amber: ["#fef3c7", "#fde68a", "#fcd34d"],
  yellow: ["#fef9c3", "#fef08a", "#fde047"],
  lime: ["#ecfccb", "#d9f99d", "#bef264"],
  green: ["#dcfce7", "#bbf7d0", "#86efac"],
  emerald: ["#d1fae5", "#a7f3d0", "#6ee7b7"],
  teal: ["#ccfbf1", "#99f6e4", "#5eead4"],
  cyan: ["#cffafe", "#a5f3fc", "#67e8f9"],
  sky: ["#e0f2fe", "#bae6fd", "#7dd3fc"],
  blue: ["#dbeafe", "#bfdbfe", "#93c5fd"],
  indigo: ["#e0e7ff", "#c7d2fe", "#a5b4fc"],
  violet: ["#ede9fe", "#ddd6fe", "#c4b5fd"],
  purple: ["#f3e8ff", "#e9d5ff", "#d8b4fe"],
  fuchsia: ["#fae8ff", "#f5d0fe", "#f0abfc"],
  pink: ["#fce7f3", "#fbcfe8", "#f9a8d4"],
  rose: ["#ffe4e6", "#fecdd3", "#fda4af"],
};

const FOREGROUND =
  /(?<![\w:-])(?:group-hover:|hover:|focus:|focus-visible:|active:)?text-(?:\[#([0-9a-fA-F]{6})\]|([a-z]+)-(100|200|300)|(white))(?![\w/-])/g;

const OPAQUE_BACKGROUND =
  /bg-(?:blue|red|amber|emerald|green|sky|violet|rose|orange|cyan|indigo|fuchsia|slate|zinc|neutral|gray|navy|danger|success|warning|info)-\d{2,3}(?!\/)|bg-\[#[0-9a-fA-F]{6}\](?!\/)|bg-\[linear-gradient|bg-gradient-to|bg-\[var\(--tessera-danger|bg-black/;

const STRING_LITERAL = /"[^"\n]*"|`[^`]*`|'[^'\n]*'/g;

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
    for (const match of body.matchAll(FOREGROUND)) {
      const [utility, hex, family, shade, white] = match;
      const colour = white
        ? "#ffffff"
        : hex
          ? `#${hex}`
          : (PALETTE[family ?? ""]?.[["100", "200", "300"].indexOf(shade ?? "")] ?? "");
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

function walkTsx(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walkTsx(full, acc);
    else if (entry.name.endsWith(".tsx") && !entry.name.includes(".test.")) acc.push(full);
  }
  return acc;
}

function scanTree(): { failing: Finding[]; resolved: number; files: number } {
  const root = process.cwd();
  const failing: Finding[] = [];
  let resolved = 0;
  let files = 0;
  for (const dir of SCANNED_DIRS) {
    for (const absolute of walkTsx(path.join(root, dir))) {
      files += 1;
      const found = scanSource(path.relative(root, absolute), readFileSync(absolute, "utf8"));
      failing.push(...found.failing);
      resolved += found.resolved;
    }
  }
  return { failing, resolved, files };
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

  it("has teeth: a token passes, because a token is not a literal", () => {
    const tokenised = scanSource("x.tsx", '"text-xs text-[var(--tessera-fg-success)]"');
    expect(tokenised.failing).toEqual([]);
  });
});
