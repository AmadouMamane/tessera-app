// The RATCHET over hardcoded white foregrounds (docs/ui-style-reference.md §4).
//
// A colour written as a LITERAL cannot flip with the theme; only a token can. The cockpit
// ships three themes (`.light` / `.dark` / `.deep-night`) that re-tone ONE set of
// `--tessera-*` variables, so every surface follows automatically — except wherever a class
// string said `text-white` outright. On 2026-08-01 that was ~120 places, and the "Clair"
// theme was correspondingly unreadable: the sidebar's AGENTS / GOUVERNER / PLATEFORME
// headers were white on a white rail, and every page's biggest number — the KPI value —
// was white on a white card. The fix is `--tessera-text-strong`: pure white on the dark
// themes (so nothing moved there), ink under "Clair".
//
// THE RULE THIS ENFORCES. Inside one class-string literal, `text-white` is legitimate if
// and only if the SAME literal also sets an OPAQUE, non-theme background — a red count
// badge, the violet primary button, a navy gradient. That background is the same colour
// under every theme, so its foreground must not move either. A TRANSLUCENT tint
// (`bg-[#b9a6ff]/15`) is explicitly NOT a background for this purpose: at 15 % over a white
// card the result is white, which is exactly the bug.
//
// WHAT THIS WITNESS CANNOT SEE, said out loud (ADR 0026). It reads one literal at a time,
// so it cannot know that an element's dark background is set by an ANCESTOR. That is the
// whole content of the frozen set below: six literals in the Credit Aurore customer decor,
// each a child of a navy header that stays navy under every cockpit theme. The set is
// two-sided — an exact count per file — so it can only ever shrink, and a NEW bare white
// anywhere else is red.
//
// Mutation contract (each verified red before landing):
//   · restore `text-white` on the sidebar's super-section header  → red;
//   · restore `text-white` on the canonical KPI value             → red;
//   · claim a translucent tint counts as a background             → red;
//   · lower a frozen count without removing the literal           → red;
//   · point the scan at a directory that does not exist           → red (anti-vacuity).
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/** The trees this ratchet governs: the whole rendered surface of both apps. */
const SCANNED_DIRS = ["components", "app"] as const;

/** Anti-vacuity: 238 `.tsx` were scanned on 2026-08-01; a floor just under it catches a
 *  scan pointed at nothing without going red because one component was deleted. */
const EXPECTED_MIN_FILES = 230;
/** ...and must still find the legitimate whites, or "0 violations" would prove nothing. */
const EXPECTED_MIN_LEGITIMATE = 20;

/**
 * Literals whose dark background comes from an ANCESTOR, which a per-literal scan cannot
 * see. Every one is inside the Credit Aurore customer decor, under a navy header that does
 * not re-tone with the cockpit themes.
 *
 * TWO-SIDED and may only SHRINK: the count must match exactly, so neither adding a new bare
 * white to these files nor silently deleting the justification passes.
 */
const FROZEN_ANCESTOR_BACKED: ReadonlyMap<string, number> = new Map([
  ["components/product/chat-widget.tsx", 3],
  ["components/product/mes-comptes-host.tsx", 3],
]);

/** An opaque, non-theme background carried by the same class-string literal. */
const OPAQUE_BACKGROUND =
  /bg-(?:blue|red|amber|emerald|green|sky|violet|rose|orange|cyan|indigo|fuchsia|slate|zinc|neutral|gray|navy|danger|success|warning|info)-\d{2,3}(?!\/)|bg-\[#[0-9a-fA-F]{6}\](?!\/)|bg-\[linear-gradient|bg-gradient-to|bg-\[var\(--tessera-danger|bg-black/;

/** Quoted class strings: double, single, or template. */
const STRING_LITERAL = /"[^"\n]*"|`[^`]*`|'[^'\n]*'/g;

interface Finding {
  readonly file: string;
  readonly line: number;
  readonly literal: string;
}

function walkTsx(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walkTsx(full, acc);
    else if (entry.name.endsWith(".tsx") && !entry.name.includes(".test.")) acc.push(full);
  }
  return acc;
}

/** Split one source into the whites that carry their own background and those that do not. */
function scanSource(file: string, source: string): { bare: Finding[]; legitimate: number } {
  const bare: Finding[] = [];
  let legitimate = 0;
  for (const match of source.matchAll(STRING_LITERAL)) {
    const literal = match[0];
    if (!literal.includes("text-white")) continue;
    if (OPAQUE_BACKGROUND.test(literal)) {
      legitimate += 1;
      continue;
    }
    const index = match.index ?? 0;
    bare.push({
      file,
      line: source.slice(0, index).split("\n").length,
      literal: literal.split(/\s+/).join(" ").slice(0, 120),
    });
  }
  return { bare, legitimate };
}

function scanTree(): { bare: Finding[]; legitimate: number; files: number } {
  const root = process.cwd();
  const bare: Finding[] = [];
  let legitimate = 0;
  let files = 0;
  for (const dir of SCANNED_DIRS) {
    for (const absolute of walkTsx(path.join(root, dir))) {
      files += 1;
      const relative = path.relative(root, absolute);
      const found = scanSource(relative, readFileSync(absolute, "utf8"));
      bare.push(...found.bare);
      legitimate += found.legitimate;
    }
  }
  return { bare, legitimate, files };
}

describe("a hardcoded white never lands on a theme surface", () => {
  const scan = scanTree();

  it("sees the whole rendered surface, and sees the legitimate whites too", () => {
    expect(scan.files).toBeGreaterThanOrEqual(EXPECTED_MIN_FILES);
    expect(scan.legitimate).toBeGreaterThanOrEqual(EXPECTED_MIN_LEGITIMATE);
  });

  it("leaves no bare `text-white` outside the frozen ancestor-backed set", () => {
    const offending = scan.bare.filter((f) => !FROZEN_ANCESTOR_BACKED.has(f.file));
    expect(
      offending.map((f) => `${f.file}:${f.line}  ${f.literal}`),
      "use text-[var(--tessera-text-strong)]; `text-white` needs its OWN opaque background",
    ).toEqual([]);
  });

  it("holds the frozen set at its exact measured size, so it can only shrink", () => {
    const actual = new Map<string, number>();
    for (const finding of scan.bare) {
      if (!FROZEN_ANCESTOR_BACKED.has(finding.file)) continue;
      actual.set(finding.file, (actual.get(finding.file) ?? 0) + 1);
    }
    expect(Object.fromEntries(actual)).toEqual(Object.fromEntries(FROZEN_ANCESTOR_BACKED));
  });

  it("has teeth: the sidebar super-header and the KPI value are rejected if restored", () => {
    const superHeader = scanSource(
      "sidebar.tsx",
      'cn("border-l-2 text-[0.7rem] uppercase tracking-[0.1em] text-white", ACCENT[a])',
    );
    expect(superHeader.bare).toHaveLength(1);

    const kpiValue = scanSource(
      "metric-card.tsx",
      '<p className="text-[1.55rem] font-semibold leading-none text-white">{value}</p>',
    );
    expect(kpiValue.bare).toHaveLength(1);
  });

  it("has teeth: a translucent tint is not a background, an opaque chip is", () => {
    const tinted = scanSource("x.tsx", '"border-[#b9a6ff]/60 bg-[#b9a6ff]/15 text-white"');
    expect(tinted.bare).toHaveLength(1);
    expect(tinted.legitimate).toBe(0);

    const chip = scanSource("x.tsx", '"rounded-full bg-red-500 px-1 text-white"');
    expect(chip.bare).toEqual([]);
    expect(chip.legitimate).toBe(1);
  });
});
