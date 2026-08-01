// The RATCHET over corner radius.
//
// Three rules, because there are three ways the corner of a Tessera card can stop
// obeying the design system, and a witness that watched only one of them would
// report green over the other two. The third was added the same afternoon, after
// the first two were BOTH green while the cockpit still showed two different
// corners on the page Amadou opens first.
//
// WHY THIS EXISTS. On 2026-08-01 Amadou said the cockpit read "pas premium" next
// to Vercel and Cloudflare, and named the corners. He was right, and the reason
// was structural rather than a matter of taste: Tessera's radius scale sat one
// full step ABOVE Tailwind stock at every rung, so a dense control plane shipped
// 16px cards where Vercel uses 12, Linear and Stripe 8, Cloudflare 6-8. The scale
// came down one notch. That moved 1364 usages at once — and left 77 behind,
// because they had been written as arbitrary values (`rounded-[5px]`,
// `rounded-[7px]`, `rounded-[14px]`) which no token can reach. Exactly the disease
// the colour literals had (see `theme-contrast.test.ts`): a value that names itself
// does not follow the system. All 77 were swept onto the scale; these rules keep
// them there.
//
// FIRST RULE — NO CORNER NAMES ITS OWN LENGTH. Any `rounded-[…px]`, `[…rem]`, `[…em]`
// or bare number in the governed trees is red, named by file and line. Held at ZERO,
// two-sided: there is no frozen set, because after the sweep there is genuinely
// nothing left to exempt. If a future corner truly cannot sit on the scale, the
// honest move is to add a rung to `@theme`, not to write the number on the element.
//
// An ABSOLUTE LENGTH is the whole rule, and the narrowing is principled rather than
// convenient — the first draft of this file was broader and caught three things that
// are not the defect. `rounded-[50%]` is a circle: a shape, not a point on a length
// scale, and it stays a circle at every rung. `rounded-[inherit]` defers to whatever
// its parent already got from a token, which is obedience written differently.
// `rounded-[var(--radius-lg)]` literally reads the token — those two occurrences were
// rewritten as `rounded-lg` rather than exempted, because the long spelling was only
// ever a detour to the same place. What remains of that population is bounded below,
// two-sided, so it can shrink but never quietly absorb a value that IS a length.
//
// SECOND RULE — THE SCALE MAY TIGHTEN, NEVER LOOSEN. The first rule alone would be
// satisfied by a scale that quietly drifted back to 16px cards: every usage would
// still be a token, and every corner would still be wrong. So the rungs are bounded
// at the values Amadou chose, one-sided. Making a corner tighter stays green;
// making it rounder than the decision is red, and the failure says which rung moved.
//
// WHAT THIS WITNESS CANNOT SEE, said out loud (ADR 0026). It reads class strings and
// one CSS file. It therefore cannot see a radius that arrives any other way. That
// population was MEASURED on 2026-08-01 rather than assumed, and it is three things:
// zero inline `style={{ borderRadius }}` in the whole frontend; one
// `border-radius: 999px` on the scrollbar thumb, which is a pill by intent and has
// no business on a 3-to-20px scale; and two SVG `rx=` attributes on sparkline bars,
// which are chart geometry, not chrome. Nothing in that list is a corner of a card.
// Should any of them grow, this file will still say green — that is the admission,
// and the anti-vacuity floors below are what stop the green from being empty.
//
// Mutation contract (each verified red before landing):
//   · write `rounded-[5px]` back on any component        → red, named by line;
//   · widen `--radius-xl` back to 1rem                   → red, names the rung;
//   · delete a rung from `@theme`                        → red (the bound is unmet);
//   · point the file scan at nothing                     → red (anti-vacuity);
//   · make the radius regex stop matching                → red (anti-vacuity);
//   · pass `rounded-lg` to a <Card>                       → red, named by line.
import { type Dirent, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/** The trees that render a corner. `lib` is in because a class map is not always in
 *  a component — the lesson `theme-contrast.test.ts` learned the hard way. */
const SCANNED_DIRS = ["components", "app", "lib"] as const;
const SCANNED_EXTENSIONS = [".tsx", ".ts"] as const;

/** Anti-vacuity: a scan pointed at an empty tree reports "no violations" too. */
const EXPECTED_MIN_FILES = 230;
/** ...and the regex must still match SOMETHING, or "zero arbitrary radii" would only
 *  mean the pattern rotted. 1364 token radii were counted on 2026-08-01; a floor well
 *  under it survives ordinary deletions without going blind. */
const EXPECTED_MIN_TOKEN_RADII = 1200;

/**
 * The scale, in rem, as decided on 2026-08-01. A rung may be SMALLER than its bound
 * (tightening further is a design choice nobody needs a ratchet's permission for);
 * larger is the drift this rule exists to catch.
 */
const MAX_RADIUS_REM: ReadonlyMap<string, number> = new Map([
  ["--radius-xs", 0.1875], // 3px
  ["--radius-sm", 0.25], // 4px
  ["--radius-md", 0.375], // 6px  — buttons, chips
  ["--radius-lg", 0.5], // 8px
  ["--radius-xl", 0.75], // 12px — THE CARDS. The number Amadou chose, and the one
  //                                 that makes the cockpit read like Vercel's.
  ["--radius-2xl", 1], // 16px
  ["--radius-3xl", 1.25], // 20px — decorative app tiles on the login page
]);

const SIDE = "(?:-(?:t|b|l|r|tl|tr|bl|br|s|e|ss|se|es|ee))?";
/** A corner that names an ABSOLUTE LENGTH — the only spelling that bypasses the scale.
 *  `rounded-[6px]`, `rounded-t-[1.25rem]`, `rounded-[14]`. */
const ARBITRARY_LENGTH_RADIUS = new RegExp(`\\brounded${SIDE}-\\[[0-9.]+(?:px|rem|em)?\\]`, "g");
/** Every other arbitrary spelling: `[50%]` (a circle), `[inherit]` (defers to a token).
 *  Bounded two-sided below so this population cannot grow into a length by another name. */
const NON_LENGTH_RADIUS = new RegExp(
  `\\brounded${SIDE}-\\[(?![0-9.]+(?:px|rem|em)?\\])[^\\]]+\\]`,
  "g",
);
/** Measured 2026-08-01, after the sweep: four `[50%]` circles (two decorative discs on
 *  `/comprendre`, two on the login illustration) and one `[inherit]` on the scroll-area
 *  viewport. Exact, so a sixth has to be argued for rather than merely added. */
const NON_LENGTH_EXPECTED = 5;
/** `rounded-xl`, `rounded-t-md`, `rounded-full` — a radius that OBEYS the system. */
const TOKEN_RADIUS =
  /\brounded(?:-(?:t|b|l|r|tl|tr|bl|br|s|e|ss|se|es|ee))?-(?:none|xs|sm|md|lg|xl|2xl|3xl|full)\b/g;

const ROOT = path.resolve(__dirname, "..", "..");

function walk(dir: string, out: string[] = []): string[] {
  let entries: Dirent[];
  try {
    entries = readdirSync(dir, { withFileTypes: true });
  } catch {
    return out;
  }
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules" || entry.name === ".next") continue;
      walk(full, out);
    } else if (SCANNED_EXTENSIONS.some((ext) => entry.name.endsWith(ext))) {
      out.push(full);
    }
  }
  return out;
}

/** The witness is not a surface. This file quotes `rounded-[5px]` in its own prose and
 *  in its own regexes; policing that would make it fail for describing what it forbids.
 *  Exactly one path is skipped, and it is this one — a narrow, self-limiting exclusion,
 *  not a general escape hatch (a ratchet with an escape hatch polices nothing). */
const WITNESS = path.join(ROOT, "components", "layout", "radius-tokens.test.ts");
const FILES = SCANNED_DIRS.flatMap((dir) => walk(path.join(ROOT, dir))).filter(
  (f) => f !== WITNESS,
);

describe("radius ratchet — the corner obeys the scale", () => {
  it("scans a real tree (anti-vacuity)", () => {
    expect(FILES.length).toBeGreaterThanOrEqual(EXPECTED_MIN_FILES);
  });

  it("still recognises a radius when it sees one (anti-vacuity)", () => {
    let seen = 0;
    for (const file of FILES) {
      seen += (readFileSync(file, "utf8").match(TOKEN_RADIUS) ?? []).length;
    }
    expect(seen).toBeGreaterThanOrEqual(EXPECTED_MIN_TOKEN_RADII);
  });

  it("no corner names its own length", () => {
    const offenders: string[] = [];
    for (const file of FILES) {
      const lines = readFileSync(file, "utf8").split("\n");
      lines.forEach((line, i) => {
        for (const hit of line.match(ARBITRARY_LENGTH_RADIUS) ?? []) {
          offenders.push(`${path.relative(ROOT, file)}:${i + 1}  ${hit}`);
        }
      });
    }
    expect(
      offenders,
      `arbitrary radii must sit on the scale instead:\n${offenders.join("\n")}`,
    ).toHaveLength(0);
  });

  it("the shape-and-inherit population has not grown", () => {
    const found: string[] = [];
    for (const file of FILES) {
      const lines = readFileSync(file, "utf8").split("\n");
      lines.forEach((line, i) => {
        for (const hit of line.match(NON_LENGTH_RADIUS) ?? []) {
          found.push(`${path.relative(ROOT, file)}:${i + 1}  ${hit}`);
        }
      });
    }
    expect(found, `circles and inherits, held exact:\n${found.join("\n")}`).toHaveLength(
      NON_LENGTH_EXPECTED,
    );
  });

  it("no <Card> overrides the corner the card component gives it", () => {
    // THIRD RULE, and it exists because the first two were BOTH green while the
    // cockpit still showed two different corners on one page. Every radius was a
    // token and the scale was correctly tightened — and thirteen `<Card>` call
    // sites passed `rounded-lg` in their own className, which tailwind-merge
    // resolves by DROPPING the component's `rounded-xl`. Result: six KPI tiles at
    // 8px beside thirteen panels at 12px, on the page Amadou opens first. A card
    // that argues with its own component about its corner is the defect; the rung
    // it argues for is beside the point.
    const offenders: string[] = [];
    for (const file of FILES) {
      if (!file.endsWith(".tsx")) continue;
      const src = readFileSync(file, "utf8");
      // `<Card` … up to the end of its opening tag, with a radius class inside a
      // string literal in that span.
      for (const m of src.matchAll(/<Card\b[^>]*?>/gs)) {
        const [tag] = m;
        const hit =
          /"[^"]*\b(rounded(?:-(?:t|b|l|r|tl|tr|bl|br))?-(?:xs|sm|md|lg|xl|2xl|3xl))\b[^"]*"/.exec(
            tag,
          );
        if (hit) {
          const line = src.slice(0, m.index).split("\n").length;
          offenders.push(`${path.relative(ROOT, file)}:${line}  <Card … ${hit[1]}>`);
        }
      }
    }
    expect(
      offenders,
      `a Card takes its corner from the Card component:\n${offenders.join("\n")}`,
    ).toHaveLength(0);
  });

  it("the scale has not loosened", () => {
    const css = readFileSync(path.join(ROOT, "app", "globals.css"), "utf8");
    const tooRound: string[] = [];
    for (const [token, maxRem] of MAX_RADIUS_REM) {
      const declared = new RegExp(`${token}:\\s*([0-9.]+)rem`).exec(css);
      if (declared === null) {
        tooRound.push(`${token} is not declared in @theme at all`);
        continue;
      }
      const value = Number(declared[1]);
      if (value > maxRem) {
        tooRound.push(
          `${token} is ${value}rem (${value * 16}px), above the ${maxRem}rem (${maxRem * 16}px) decided on 2026-08-01`,
        );
      }
    }
    expect(tooRound, tooRound.join("\n")).toHaveLength(0);
  });
});
