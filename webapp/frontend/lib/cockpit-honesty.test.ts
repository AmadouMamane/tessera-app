/**
 * CLASS C — a displayed count is derived from what it counts.
 * CLASS D — an unavailable signal names WHY it is unavailable.
 *
 * Both are the same failure wearing two faces: a screen states something it did not measure.
 *
 * ## Class C — the counter that counts nothing
 *
 * `observability-dashboard.tsx` renders "42 of the 200-signal catalogue" from two `const`
 * declarations. Neither is read from anything. On 2026-08-01 the page declared **44** signals,
 * the catalogue held **202**, and only **18** had a reader in code — so the header was wrong on
 * all three of its numbers, and had been for as long as it existed. The comment beside it is
 * candid ("a coverage framing, not a live count"), which is precisely the problem: the screen
 * says nothing of the sort, and an operator has no access to the comment.
 *
 * A constant that configures the UI is fine — `PAGE_SIZE`, `MAX_PAGE_BUTTONS`, `COLS`. A
 * constant that *is a count of measured things* is a claim, and a claim must be derived. The
 * detector separates them by the noun in the name, which is the only mechanical signal
 * available and the one that happens to be exactly right here.
 *
 * ## Class D — "Indisponible" that will not say why
 *
 * `signals-table.tsx` poses the `na` status from sixteen places, for at least two genuinely
 * different reasons — the sample was empty (`n_turns === 0`), or the source could not be read
 * (`!available`) — and the row cannot tell them apart, because `SignalRow` has nowhere to put
 * the reason. The operator sees one word covering "nothing happened yet", "this signal has no
 * reader at all", "the read failed" and "planned, never implemented". Those demand four
 * different actions and get one.
 *
 * ADR 0026's corollary is the whole of it: a witness that cannot see reports a blind spot, it
 * does not report "ok". `na` is the cockpit reporting a blind spot without saying where.
 *
 * Both populations are frozen at their exact measured size so they can only shrink. Lot 5 of
 * `docs/status/coherence-mesuree-run.md` takes them to zero.
 */

import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SCANNED_DIRS = ["components", "app", "lib"] as const;
const SCANNED_EXTENSIONS = [".tsx", ".ts"] as const;

/* ------------------------------------------------------------------------------------ */
/* Class C                                                                               */
/* ------------------------------------------------------------------------------------ */

/**
 * Nouns that make a constant a CLAIM about the system rather than a UI setting.
 *
 * Deliberately explicit, short, and **plural**. A wider list (`SIZE`, `MAX`, `WINDOW`) would
 * sweep in the pagination constants, which are configuration and not claims — and a ratchet
 * that cries at `PAGE_SIZE = 9` gets silenced, taking the real finding with it. The plural
 * requirement is what separates `CASES` (a count) from `CASE_AMOUNT` (one case's figure).
 *
 * Matched SEGMENT-WISE, not with `\b`: the boundary assertion does not fire on `_`, so
 * `/\bSIGNALS\b/` does not match `QUALITY_SIGNALS`. That mistake made the first run of this
 * ratchet report zero offenders on a tree holding two, and only the teeth test caught it —
 * which is the entire reason the teeth test exists.
 */
const COUNTED_NOUNS = new Set([
  "SIGNALS",
  "CATALOGUE",
  "AGENTS",
  "RUNS",
  "CASES",
  "CHECKS",
  "POLICIES",
  "FAILURES",
  "CONTROLS",
  "TESTS",
  "SOURCES",
  "INCIDENTS",
]);

/** True when any underscore-separated segment of the name is a counted noun. */
const isCountedName = (name: string): boolean => name.split("_").some((s) => COUNTED_NOUNS.has(s));

/** `const QUALITY_SIGNALS = 42;` — an upper-snake constant bound to a bare number. */
const NUMERIC_CONSTANT = /^\s*const\s+([A-Z][A-Z0-9_]{2,})\s*(?::\s*number\s*)?=\s*(\d+)\s*;/;

interface Counter {
  readonly file: string;
  readonly line: number;
  readonly name: string;
  readonly value: string;
}

function scanCounters(file: string, source: string): Counter[] {
  const found: Counter[] = [];
  const lines = source.split("\n");
  for (let i = 0; i < lines.length; i += 1) {
    const m = NUMERIC_CONSTANT.exec(lines[i] ?? "");
    if (!m) continue;
    const name = m[1] ?? "";
    if (!isCountedName(name)) continue;
    found.push({ file, line: i + 1, name, value: m[2] ?? "" });
  }
  return found;
}

/**
 * Counters asserted rather than derived, at their exact size on 2026-08-01.
 *
 * · `observability-dashboard.tsx` holds both halves of "42 of 200", and both are wrong.
 *
 * Lot 5 replaces them with counts read from the catalogue and from the reader registry, at
 * which point this map empties.
 */
const FROZEN_ASSERTED_COUNTERS: ReadonlyMap<string, number> = new Map([
  ["components/observability/observability-dashboard.tsx", 2],
]);

/* ------------------------------------------------------------------------------------ */
/* Class D                                                                               */
/* ------------------------------------------------------------------------------------ */

/** A row posing the "no data" status. */
const NA_PRODUCTION = /\?\s*"na"|status:\s*"na"/;
/** …and the field that would say WHY. Nothing carries it yet; that is the finding. */
const REASON_FIELD = /\b(?:reason|unavailability|unavailable|because|cause)\s*:/;
/** The declaration, the legend and the sort orders are not productions. */
const NA_DECLARATION = /export type|SignalStatus\[\]|key:\s*"na"/;

const REASON_WINDOW = 10;

interface Unexplained {
  readonly file: string;
  readonly line: number;
  readonly snippet: string;
}

function scanUnexplainedNa(file: string, source: string): Unexplained[] {
  const found: Unexplained[] = [];
  const lines = source.split("\n");
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i] ?? "";
    if (!NA_PRODUCTION.test(line) || NA_DECLARATION.test(line)) continue;
    const lo = Math.max(0, i - REASON_WINDOW);
    const hi = Math.min(lines.length, i + REASON_WINDOW + 1);
    let explained = false;
    for (let j = lo; j < hi; j += 1) {
      if (REASON_FIELD.test(lines[j] ?? "")) {
        explained = true;
        break;
      }
    }
    if (explained) continue;
    found.push({ file, line: i + 1, snippet: line.trim().slice(0, 90) });
  }
  return found;
}

/**
 * `na` posed without a reason, at its exact size on 2026-08-01.
 *
 * All sixteen are in the quality signals registry, and they already carry at least two
 * distinct causes in their conditions — `n === 0` (empty sample) and `!available` (the source
 * could not be read). The condition knows; the row does not. Lot 5 gives `SignalRow` a
 * `reason` and this map empties.
 */
const FROZEN_UNEXPLAINED_NA: ReadonlyMap<string, number> = new Map([
  ["components/observability/signals-table.tsx", 17],
]);

/* ------------------------------------------------------------------------------------ */

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
  readonly counters: Counter[];
  readonly unexplained: Unexplained[];
  readonly files: number;
  /** Every upper-snake numeric constant, counted or not — the anti-vacuity witness. */
  readonly allConstants: number;
}

function scanTree(): TreeScan {
  const root = path.join(__dirname, "..");
  const counters: Counter[] = [];
  const unexplained: Unexplained[] = [];
  let files = 0;
  let allConstants = 0;
  for (const dir of SCANNED_DIRS) {
    for (const full of walkSources(path.join(root, dir))) {
      const rel = path.relative(root, full).split(path.sep).join("/");
      const source = readFileSync(full, "utf8");
      files += 1;
      for (const line of source.split("\n")) if (NUMERIC_CONSTANT.test(line)) allConstants += 1;
      counters.push(...scanCounters(rel, source));
      unexplained.push(...scanUnexplainedNa(rel, source));
    }
  }
  return { counters, unexplained, files, allConstants };
}

const scan = scanTree();

describe("class C — a displayed count is derived from what it counts", () => {
  it("sees the tree, and distinguishes claims from configuration", () => {
    expect(scan.files).toBeGreaterThanOrEqual(230);
    // 15 upper-snake numeric constants stand on the tree; only 2 are claims about the system.
    // If this floor is ever met by the *counted* set instead, the noun list has gone wrong.
    expect(scan.allConstants).toBeGreaterThanOrEqual(12);
  });

  it("leaves no asserted counter outside the frozen set", () => {
    const offending = scan.counters.filter((c) => !FROZEN_ASSERTED_COUNTERS.has(c.file));
    expect(
      offending.map((c) => `${c.file}:${c.line}  ${c.name} = ${c.value}`),
      "derive it from the collection it counts — a constant is a claim the operator cannot check",
    ).toEqual([]);
  });

  it("holds the frozen counters at their exact size, so the debt can only shrink", () => {
    const actual: Record<string, number> = {};
    for (const c of scan.counters) {
      if (!FROZEN_ASSERTED_COUNTERS.has(c.file)) continue;
      actual[c.file] = (actual[c.file] ?? 0) + 1;
    }
    expect(actual).toEqual(Object.fromEntries(FROZEN_ASSERTED_COUNTERS));
  });

  it("has teeth: a new asserted count is caught, a pagination constant is not", () => {
    expect(scanCounters("x.tsx", "const ACTIVE_AGENTS = 12;").map((c) => c.name)).toEqual([
      "ACTIVE_AGENTS",
    ]);
    expect(scanCounters("x.tsx", "const PAGE_SIZE = 9;")).toEqual([]);
    expect(scanCounters("x.tsx", "const MAX_PAGE_BUTTONS = 5;")).toEqual([]);
    // A count DERIVED from a collection is the fix, and must not be flagged.
    expect(scanCounters("x.tsx", "const signalCount = catalogue.signals.length;")).toEqual([]);
  });
});

describe("class D — an unavailable signal names why it is unavailable", () => {
  it("leaves no unexplained `na` outside the frozen set", () => {
    const offending = scan.unexplained.filter((u) => !FROZEN_UNEXPLAINED_NA.has(u.file));
    expect(
      offending.map((u) => `${u.file}:${u.line}  ${u.snippet}`),
      "carry the reason: no-sample / no-reader / read-failed / planned demand four different actions",
    ).toEqual([]);
  });

  it("holds the frozen `na` set at its exact size, so the debt can only shrink", () => {
    const actual: Record<string, number> = {};
    for (const u of scan.unexplained) {
      if (!FROZEN_UNEXPLAINED_NA.has(u.file)) continue;
      actual[u.file] = (actual[u.file] ?? 0) + 1;
    }
    expect(actual).toEqual(Object.fromEntries(FROZEN_UNEXPLAINED_NA));
  });

  it("has teeth: a bare `na` is caught, one carrying its reason is not", () => {
    const bare = scanUnexplainedNa("x.tsx", 'rows.push({ status: n === 0 ? "na" : "ok" });');
    expect(bare.length).toBe(1);

    const explained = scanUnexplainedNa(
      "x.tsx",
      [
        "rows.push({",
        '  status: n === 0 ? "na" : "ok",',
        '  reason: n === 0 ? "no-sample" : null,',
        "});",
      ].join("\n"),
    );
    expect(explained).toEqual([]);

    // The type declaration and the legend entry are not productions.
    expect(
      scanUnexplainedNa("x.tsx", 'export type SignalStatus = "ok" | "warn" | "crit" | "na";'),
    ).toEqual([]);
    expect(scanUnexplainedNa("x.tsx", 'const legend = { key: "na", status: "na" };')).toEqual([]);
  });
});
