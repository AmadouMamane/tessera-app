import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { isUnread, readNumber, showNumber, toneFor } from "@/lib/unread-is-not-zero";

/**
 * Two witnesses over one idea: an absent reading is not zero, and it is not a verdict.
 *
 * The unit half checks the door. The static half checks that the governance dashboards walk
 * through it — because the ratchet next door (`failed-read-is-not-an-empty-result`) cannot: it
 * clears a whole FILE once any read-failure guard appears anywhere in it, and says so in its own
 * docstring. `security-dashboard.tsx` had one such guard on line 621 and ten green-on-nothing
 * tiles spread over the next 1300 lines, including `n_leaks`.
 */

const TONES = { bad: "BAD", good: "GOOD", unread: "UNREAD" };

describe("readNumber", () => {
  it("collapses every shape of 'nothing was measured' to null", () => {
    expect(readNumber(undefined)).toBeNull(); // the query never answered
    expect(readNumber(null)).toBeNull(); // the backend could not compute it
    expect(readNumber(Number.NaN)).toBeNull(); // a rate over an empty window
    expect(readNumber(Number.POSITIVE_INFINITY)).toBeNull(); // a division by zero turns
  });

  it("keeps a real zero, which is a measurement", () => {
    expect(readNumber(0)).toBe(0);
    expect(isUnread(0)).toBe(false);
    expect(isUnread(undefined)).toBe(true);
  });
});

describe("toneFor", () => {
  it("gives the third answer rather than the reassuring one", () => {
    // The exact tile: `(crossTenant.data?.n_leaks ?? 0) > 0 ? BAD : GOOD` printed GOOD here.
    expect(toneFor(undefined, (n) => n > 0, TONES)).toBe("UNREAD");
    expect(toneFor(null, (n) => n > 0, TONES)).toBe("UNREAD");
  });

  it("still decides when there IS a reading — including a measured zero", () => {
    expect(toneFor(0, (n) => n > 0, TONES)).toBe("GOOD");
    expect(toneFor(3, (n) => n > 0, TONES)).toBe("BAD");
    expect(toneFor(0.4, (r) => r >= 0.5, TONES)).toBe("GOOD");
    expect(toneFor(0.5, (r) => r >= 0.5, TONES)).toBe("BAD");
  });

  it("never calls the predicate on a non-number", () => {
    // Otherwise every call site would have to null-check inside its own threshold.
    let calls = 0;
    const spy = () => {
      calls += 1;
      return true;
    };
    toneFor(undefined, spy, TONES);
    toneFor(Number.NaN, spy, TONES);
    expect(calls).toBe(0);
    toneFor(1, spy, TONES);
    expect(calls).toBe(1);
  });
});

describe("showNumber", () => {
  it("prints an em dash for an absence and the figure for a reading", () => {
    expect(showNumber(undefined)).toBe("—");
    expect(showNumber(null)).toBe("—");
    expect(showNumber(0)).toBe("0"); // a measured zero is a result and must be shown
    expect(showNumber(12, (v) => `${v} leaks`)).toBe("12 leaks");
  });
});

/* ─────────────────────────── the static half ─────────────────────────── */

const ROOT = process.cwd();

/**
 * The screens whose whole purpose is to publish a verdict. On these, `?? 0` feeding a threshold
 * is the defect; elsewhere in the cockpit it is often a legitimate default over a collection the
 * caller already holds (`items.length ?? 0`, a sparkline's first point, a filter predicate), so
 * this witness deliberately does not sweep the whole tree and says so.
 */
const VERDICT_SCREENS = [
  "components/security/security-dashboard.tsx",
  "components/compliance/compliance-dashboard.tsx",
  "components/reliability/reliability-dashboard.tsx",
  "components/improvement/improvement-dashboard.tsx",
];

/** `?? 0` immediately feeding a comparison — the shape that turns an absence into a verdict. */
const COALESCE_THEN_THRESHOLD = /\?\?\s*0\s*\)\s*(>=|<=|>|<)/;

/**
 * Strip comments first. The security dashboard's header now QUOTES the pattern it removed, and a
 * detector that cannot tell code from prose about code reports the explanation as the defect —
 * making deletion of the explanation the cheapest way to go green. (The sibling ratchet learned
 * this on its own first run; borrowed here on purpose.)
 */
function withoutComments(text: string): string {
  return text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
}

/**
 * A trend arrow is not a verdict. `const up = (delta ?? 0) > 0` picks which way a chevron
 * points; with no delta it points flat, which asserts nothing about the world. Named here so the
 * exemption is a stated argument rather than a silent regex hole.
 */
const NOT_A_VERDICT = /const \w+ = \(delta \?\? 0\) > 0;/;

describe("the verdict screens", () => {
  it("can still see — the positive control", () => {
    for (const rel of VERDICT_SCREENS) {
      const text = readFileSync(join(ROOT, rel), "utf8");
      // A renamed or moved dashboard would otherwise make this suite pass by reading nothing.
      expect(text.length, `${rel} is missing or empty`).toBeGreaterThan(2000);
      expect(text, `${rel} no longer imports the door`).toMatch(/unread-is-not-zero/);
    }
  });

  it("detects the fault it was written for — the negative control", () => {
    expect(COALESCE_THEN_THRESHOLD.test("tone={(d.n_leaks ?? 0) > 0 ? BAD : GOOD}")).toBe(true);
    expect(COALESCE_THEN_THRESHOLD.test("tone={(d.score ?? 0) >= 80 ? GOOD : WARN}")).toBe(true);
    expect(COALESCE_THEN_THRESHOLD.test("toneFor(d.n_leaks, (n) => n > 0, TONE_BAD)")).toBe(false);
  });

  it("turns no absent reading into a green verdict", () => {
    const offences: string[] = [];
    for (const rel of VERDICT_SCREENS) {
      const lines = withoutComments(readFileSync(join(ROOT, rel), "utf8")).split("\n");
      lines.forEach((line, i) => {
        if (!COALESCE_THEN_THRESHOLD.test(line) || NOT_A_VERDICT.test(line)) return;
        offences.push(`${rel}:${i + 1}  ${line.trim()}`);
      });
    }
    // Not frozen. Every one of these is a governance screen reporting "ok" about something it
    // did not read — there is no acceptable instance to keep.
    expect(offences).toEqual([]);
  });
});

/** The scan must actually walk a tree that exists — cheap guard against a moved `components/`. */
describe("the scan's ground", () => {
  it("finds the dashboards where it looks for them", () => {
    const seen: string[] = [];
    const walk = (dir: string) => {
      for (const entry of readdirSync(dir)) {
        if (entry.startsWith(".") || entry === "node_modules") continue;
        const full = join(dir, entry);
        if (statSync(full).isDirectory()) walk(full);
        else if (entry.endsWith("-dashboard.tsx")) seen.push(entry);
      }
    };
    walk(join(ROOT, "components"));
    expect(seen.length).toBeGreaterThan(4);
  });
});
