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
 * Inline control rows still declaring their own bar + state, by file, at their exact measured
 * size on 2026-08-01. Each entry is scheduled for zero in Lot 2 of
 * `docs/status/coherence-mesuree-run.md`; the map exists so the debt shrinks ON THE RECORD
 * rather than being re-discovered by the next audit.
 *
 * · `signals-table.tsx` — the 18-row quality registry, every row hand-built.
 * · `overview-dashboard.tsx` — `buildControls()`, the seven critical controls.
 * · `security-dashboard.tsx` — six more, with a THIRD state rule (`tone(x, warn, crit)`).
 */
const FROZEN_INLINE_BARS: ReadonlyMap<string, number> = new Map([
  ["components/observability/signals-table.tsx", 10],
  ["components/overview/overview-dashboard.tsx", 7],
  ["components/security/security-dashboard.tsx", 6],
]);

/**
 * Anti-vacuity. 23 inline bars stand on the tree today. A floor just under it is what
 * separates "the sweep found nothing" from "the regex stopped matching" — the failure mode
 * ADR 0026 names, and the one that let three guard-rails report success over a hole.
 */
const EXPECTED_MIN_BARS = 20;

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

/** Lines of context: an object literal's bar and state sit within a few lines of each other. */
const WINDOW = 8;

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
}

function scanTree(): TreeScan {
  const root = path.join(__dirname, "..");
  const bars: InlineBar[] = [];
  let files = 0;
  for (const dir of SCANNED_DIRS) {
    for (const full of walkSources(path.join(root, dir))) {
      const rel = path.relative(root, full).split(path.sep).join("/");
      files += 1;
      if (rel === REGISTRY) continue;
      bars.push(...scanSource(rel, readFileSync(full, "utf8")));
    }
  }
  return { bars, files };
}

describe("class A — a control bar is declared once, and its state derives from it", () => {
  const scan = scanTree();

  it("sees the whole cockpit surface", () => {
    expect(scan.files).toBeGreaterThanOrEqual(230);
    expect(scan.bars.length).toBeGreaterThanOrEqual(EXPECTED_MIN_BARS);
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
