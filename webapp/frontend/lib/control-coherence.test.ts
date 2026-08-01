/**
 * CLASS A — a bar and its state rule are declared ONCE, in `lib/control-registry.ts`.
 *
 * ## What this ratchet is for
 *
 * Auditing page by page answers "is this screen honest about its own endpoint". It cannot
 * answer "does this screen agree with the next one", because that is a property of the pair,
 * not of either member. On 2026-08-01 that blind spot cost six of seven shared controls:
 * `overview-dashboard.tsx`, `observability/signals-table.tsx` and `security/security-dashboard.tsx`
 * each re-declared, independently, the threshold and the state rule of the SAME measurement.
 * Firewall efficacy reached the operator as three different numbers — 24 %, 76 %, 86 % — all
 * three computed from one report, each under a label naming efficacy.
 *
 * So the invariant is structural rather than numeric: **a control row that carries its own bar
 * carries its own opinion**, and a second opinion is a second truth. This scan finds every
 * object literal that declares a bar (`target:` / `threshold:`) next to a state
 * (`tone:` / `status:`) anywhere outside the registry, and holds the current population at its
 * exact measured size so it can only shrink. Lot 2 takes it to zero by wiring the three
 * surfaces onto `readControls()`.
 *
 * The frozen counts are therefore a DEBT, not an exemption: every one of them is scheduled for
 * removal. They are frozen rather than fixed here because a ratchet that goes red on the tree
 * it is added to teaches the next reader to disable it.
 */

import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/** The trees a cockpit control can be rendered from. */
const SCANNED_DIRS = ["components", "app", "lib"] as const;
const SCANNED_EXTENSIONS = [".tsx", ".ts"] as const;

/**
 * The one module allowed to declare a bar. Everything else must read it from here.
 * `lib/overview.ts` holds `controlState`, the shared classifier the registry calls — it
 * declares the *rule*, never a *bar*, so it is not an exception, it is the mechanism.
 */
const REGISTRY = "lib/control-registry.ts";

/**
 * Inline control rows still declaring their own bar + state, by file.
 *
 * **Empty, and it was not empty when this file was written.** It held 23 across three files on
 * 2026-08-01 — `signals-table.tsx` (10 of its 19 rows), `overview-dashboard.tsx` (the seven
 * critical controls), `security-dashboard.tsx` (six more, with a THIRD state rule of its own,
 * `tone(x, crit, warn)`). All three now read `readControls()`, so the map emptied on the way
 * through Lot 2 rather than standing as a permanent exemption.
 *
 * It stays here, empty, on purpose: a new surface that hand-builds a control row lands in it,
 * and an empty map makes that arrival loud instead of merely tolerated.
 */
const FROZEN_INLINE_BARS: ReadonlyMap<string, number> = new Map();

/**
 * Anti-vacuity, and the harder half of this file now that the offender count is zero.
 *
 * "No inline bars anywhere" and "the regex stopped matching" produce the identical green. The
 * first version of this ratchet guarded against that with a floor on the OFFENDER count, which
 * worked exactly as long as offenders existed — a witness whose sight is proven only by the
 * defects it finds goes blind the moment the last one is fixed.
 *
 * So the floor moved onto the registry itself. `lib/control-registry.ts` declares 24 bars in
 * the same syntactic shape the scan hunts; if the scan cannot find them there, it cannot find
 * them anywhere, and the empty offender list means nothing. The teeth test below is the second
 * witness: it shows the scanner a defect and requires it to be caught.
 */
const EXPECTED_MIN_REGISTRY_BARS = 20;

interface InlineBar {
  readonly file: string;
  readonly line: number;
  readonly bar: string;
  /** The state expression found beside it — the second half of a duplicated derivation. */
  readonly state: string;
}

/**
 * A bar as it reaches the screen, in a property position.
 *
 * Restricted to `target:` / `threshold:` on purpose: a comparison operator alone matches
 * prose, JSX and every `<` in the tree. The property name is what makes it a DECLARED bar
 * rather than an incidental string.
 */
const BAR_PROPERTY = /\b(?:target|threshold)\s*:\s*["'`]([^"'`\n]{1,32})["'`]/;

/** A state posed beside the bar: the row's own opinion of what the number means. */
const STATE_PROPERTY = /\b(?:tone|status|state|severity)\s*:\s*(.+)$/;

/**
 * Lines of context between a bar and the state posed beside it.
 *
 * Was 8, and 8 was WRONG — a silent under-report, which is the failure mode this file exists
 * to police, committed by the file itself. `signals-table.tsx` writes several of its statuses
 * as four-level nested ternaries spanning a dozen lines, so the bar and its state sat further
 * apart than the window and the row read as clean. The scan said 10 offenders in a file holding
 * 18 rows; wiring seven of them away dropped it to 5, and the arithmetic did not close. That
 * discrepancy is the only reason this was caught: a detector that under-reports produces a
 * green ratchet over a hole, and nothing about the green says which.
 *
 * 20 covers the longest row in the tree with room to spare. The "no offender outside the frozen
 * set" assertion is what keeps a wider window from being a licence to over-report.
 */
const WINDOW = 20;

/** Full-line comments only — a `//` inside a URL literal must survive. */
function stripComments(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^[ \t]*\/\/.*$/gm, "");
}

/** Find every object literal declaring a bar AND a state — a self-contained control row. */
function scanSource(file: string, source: string): InlineBar[] {
  const found: InlineBar[] = [];
  const lines = stripComments(source).split("\n");
  for (let i = 0; i < lines.length; i += 1) {
    const bar = BAR_PROPERTY.exec(lines[i] ?? "");
    if (!bar) continue;
    const lo = Math.max(0, i - WINDOW);
    const hi = Math.min(lines.length, i + WINDOW + 1);
    let state: string | null = null;
    for (let j = lo; j < hi; j += 1) {
      const m = STATE_PROPERTY.exec(lines[j] ?? "");
      if (m) {
        state = (m[1] ?? "").trim().slice(0, 60);
        break;
      }
    }
    if (state === null) continue;
    found.push({ file, line: i + 1, bar: bar[1] ?? "", state });
  }
  return found;
}

function walkSources(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules" || entry.name === ".next") continue;
      walkSources(full, acc);
    } else if (
      SCANNED_EXTENSIONS.some((ext) => entry.name.endsWith(ext)) &&
      !entry.name.includes(".test.")
    ) {
      acc.push(full);
    }
  }
  return acc;
}

interface TreeScan {
  readonly bars: InlineBar[];
  readonly files: number;
  /** Bars found INSIDE the registry — the proof the scanner can still see one. */
  readonly registryBars: number;
}

function scanTree(): TreeScan {
  const root = path.join(__dirname, "..");
  const bars: InlineBar[] = [];
  let files = 0;
  let registryBars = 0;
  for (const dir of SCANNED_DIRS) {
    for (const full of walkSources(path.join(root, dir))) {
      const rel = path.relative(root, full).split(path.sep).join("/");
      files += 1;
      const source = readFileSync(full, "utf8");
      if (rel === REGISTRY) {
        // The registry declares bars beside `direction`, not beside a state — so the paired
        // scan does not see them. Count the bars alone here: it is the regex that must be
        // proven alive, and the pairing is proven by the teeth test.
        for (const line of stripComments(source).split("\n")) {
          if (/\btext:\s*["'`][^"'`\n]{1,32}["'`]/.test(line)) registryBars += 1;
        }
        continue;
      }
      bars.push(...scanSource(rel, source));
    }
  }
  return { bars, files, registryBars };
}

describe("class A — a control bar is declared once, and its state derives from it", () => {
  const scan = scanTree();

  it("sees the whole cockpit surface, and can still recognise a bar", () => {
    expect(scan.files).toBeGreaterThanOrEqual(230);
    expect(
      scan.registryBars,
      "the scan found no bar even in the registry — an empty offender list proves nothing",
    ).toBeGreaterThanOrEqual(EXPECTED_MIN_REGISTRY_BARS);
  });

  it("leaves no inline bar outside the frozen set", () => {
    const offending = scan.bars.filter((b) => !FROZEN_INLINE_BARS.has(b.file));
    expect(
      offending.map((b) => `${b.file}:${b.line}  bar «${b.bar}»  beside state «${b.state}»`),
      "read the bar from lib/control-registry.ts — a row that carries its own bar carries its own opinion",
    ).toEqual([]);
  });

  it("holds the frozen set at its exact measured size, so the debt can only shrink", () => {
    const actual: Record<string, number> = {};
    for (const bar of scan.bars) {
      if (!FROZEN_INLINE_BARS.has(bar.file)) continue;
      actual[bar.file] = (actual[bar.file] ?? 0) + 1;
    }
    expect(
      actual,
      "wired a surface onto the registry? excellent — lower its number here so the debt shrinks on the record",
    ).toEqual(Object.fromEntries(FROZEN_INLINE_BARS));
  });

  it("has teeth: a fresh inline bar is caught, and a bare threshold string is not", () => {
    // The defect this ratchet exists for — a row declaring its own bar and its own state.
    const reintroduced = scanSource(
      "components/somewhere/new-panel.tsx",
      [
        "const rows = [{",
        '  key: "faithfulness",',
        '  status: rate >= 0.8 ? "ok" : "crit",',
        '  threshold: "≥ 0.80",',
        "}];",
      ].join("\n"),
    );
    expect(reintroduced.map((b) => b.bar)).toEqual(["≥ 0.80"]);

    // ...and the two shapes that are NOT the defect: a bar with no state beside it is a
    // caption, and a commented bar is documentation. Flagging either would make the ratchet
    // noisy enough to be disabled, which is how a witness dies.
    expect(scanSource("x.tsx", 'const caption = { threshold: "≥ 0.80" };')).toEqual([]);
    expect(scanSource("x.tsx", ['// target: "≥ 0.80"', '// status: "ok"'].join("\n"))).toEqual([]);
  });
});
