import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * A read that FAILED must not render as a result that was EMPTY.
 *
 * `data?.x ?? []` and `?? 0` are the two shapes this repo keeps re-introducing, and the reason
 * they survive review is that they look like defaults. They are not defaults: on a query that
 * can 401, 403, or simply not answer, they turn a fact about the REQUEST into a fact about the
 * WORLD. `/admin/utilisateurs` printing "0/0 utilisateurs" on an RBAC failure is
 * indistinguishable from a tenant with no operators; "0 agents observés" is the most reassuring
 * possible way to report that nothing is being watched. `lib/api/access.ts` states the
 * distinction; this is the ratchet that keeps it.
 *
 * This is a STATIC witness and says so. It reads sources and cannot tell whether a guard is on
 * the right branch — that is what the render tests next door are for (see
 * `components/observability/localization-honesty.test.tsx`, which was itself rewritten from a
 * source grep into a real render for exactly this reason). What a static sweep CAN do, and what
 * no render test does, is refuse to let the class grow back across 246 components.
 *
 * The frozen list may only shrink. Removing an entry means giving that screen a state that says
 * "could not read" — never deleting the fallback, and never widening the exemption.
 *
 * WHAT THIS RATCHET CANNOT SEE, stated because a witness that cannot see must say so (ADR 0026).
 * Its granularity is the FILE: one acknowledgement anywhere clears every fallback in it. That is
 * not a rounding error — `observability-dashboard.tsx` is ~1100 lines with nine of them, and
 * guarding ONE took the file off this list. So read this as what it is: a bound on the class
 * GROWING back across 246 components, not a certificate that any given screen is honest. Per
 * screen, the witness is a render test that mounts the component with a failed query and reads
 * what appears — the shape `localization-honesty.test.tsx` uses.
 */

const ROOT = process.cwd();
const HAS_QUERY = /useQuery\(|useSuspenseQuery\(|await fetch[A-Z]/;
const FALLBACK = /\?\?\s*(\[\]|0\b|\{\})/;
/** Any acknowledgement, anywhere in the file, that a read can fail. */
const GUARDS = ["isError", "isAccessDenied", "unavailable", "available === false", ".error"];

/**
 * Screens that still turn a failed read into an empty one. Each needs a reason, and the reason
 * has to be about THIS screen — "it is only a menu" is an argument, "it is hard" is not.
 */
const FROZEN_NAKED: Record<string, string> = {
  // A navigation aid, not a report. With the fleet unread the palette still offers every
  // static command; what is missing is the per-agent shortcuts, and a search box that finds
  // nothing asserts nothing about how many agents exist. The switcher and the scope filter —
  // which DO present themselves as the list of agents — both say it now.
  "components/layout/command-palette.tsx": "search palette: an absent shortcut claims nothing",
};

/**
 * Strip comments before looking for the pattern.
 *
 * Caught by this ratchet on its first run, on the very commit that wrote it: the comment
 * explaining why `?? 0` had been REMOVED from `signal-command-bar` quotes `?? 0`, so the file
 * was flagged for the sentence describing its own fix. A detector that cannot tell code from
 * prose about code reports the documentation as the defect — and the cheapest way to go green
 * would have been to delete the explanation.
 *
 * Approximate on purpose: a `//` inside a string literal is stripped too. That can only ever
 * cause a MISS (a URL does not contain `?? []`), never a false alarm, and the alternative is a
 * TypeScript parser in a lint test.
 */
function withoutComments(text: string): string {
  return text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
}

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry === ".next" || entry.startsWith(".")) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (entry.endsWith(".tsx") && !entry.includes(".test.")) out.push(full);
  }
  return out;
}

function scan() {
  const scanned: string[] = [];
  const failable: string[] = [];
  const naked: string[] = [];
  for (const dir of ["app", "components"]) {
    for (const file of walk(join(ROOT, dir))) {
      scanned.push(file);
      const text = withoutComments(readFileSync(file, "utf8"));
      if (!HAS_QUERY.test(text)) continue;
      failable.push(file);
      if (!FALLBACK.test(text)) continue;
      if (GUARDS.some((g) => text.includes(g))) continue;
      naked.push(file.slice(ROOT.length + 1));
    }
  }
  return { scanned, failable, naked };
}

describe("a failed read is not an empty result", () => {
  const { scanned, failable, naked } = scan();

  it("can still see — the positive control", () => {
    // Without this, a regex that silently stopped matching (a rename, a new query helper, a
    // moved directory) would report an empty `naked` list and read as a clean sweep. A zero
    // that cannot tell "none" from "did not look" is not a measurement.
    expect(scanned.length).toBeGreaterThan(150);
    expect(failable.length).toBeGreaterThan(30);
  });

  it("flags a naked fallback — the negative control", () => {
    // Proves the detector fires at all, on a string it constructs itself rather than on a file
    // that might be fixed tomorrow.
    const sample = "const { data } = useQuery({}); const rows = data?.rows ?? [];";
    expect(HAS_QUERY.test(sample) && FALLBACK.test(sample)).toBe(true);
    expect(GUARDS.some((g) => sample.includes(g))).toBe(false);
  });

  it("does not flag the same screen once it distinguishes the two", () => {
    const guarded = "const { data, isError } = useQuery({}); const rows = data?.rows ?? [];";
    expect(GUARDS.some((g) => guarded.includes(g))).toBe(true);
  });

  it("does not read a comment about the defect as the defect", () => {
    // The first thing this ratchet ever flagged was the sentence explaining a fix.
    const prose = "// `?? 0` printed a zero here; it returns null now\nconst n = x;";
    expect(FALLBACK.test(withoutComments(prose))).toBe(false);
    // …and it must still see the real thing on the line below a comment.
    expect(FALLBACK.test(withoutComments("// note\nconst rows = data?.rows ?? [];"))).toBe(true);
  });

  it("has no unfrozen offender", () => {
    const unexpected = naked.filter((f) => !(f in FROZEN_NAKED));
    expect(unexpected).toEqual([]);
  });

  it("keeps the frozen list honest — an entry that no longer offends must go", () => {
    // A ratchet whose list outlives its offenders stops being a debt and becomes decoration.
    const stale = Object.keys(FROZEN_NAKED).filter((f) => !naked.includes(f));
    expect(stale).toEqual([]);
  });
});
