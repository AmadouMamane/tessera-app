/**
 * CLASS I — every component in the tree is classified: mounted, primitive, or owed.
 *
 * The question this file answers is the one that was asked of the audit: **are the orphans
 * omitted features, or features reimplemented somewhere else?** Both, and the difference
 * decides what to do with each, so it is recorded per file rather than as a total.
 *
 * 14 components (2 140 lines) were imported by nothing on 2026-08-01. Two are DEAD DUPLICATES
 * — `language-switcher` and `theme-toggle` were rewritten inline in `user-menu` and
 * `app-header`, so the standalone versions are the only candidates for deletion, and only once
 * someone confirms the inline versions cover them. The rest are features that were written,
 * translated, backed by live routes, and never mounted.
 *
 * `catalogue-consumers` proved the point. Its component existed, its `usedBy.*` namespace was
 * translated into three languages, `/observability/catalogue-consumers` served it, and the
 * `modeles` page already rendered `usedBy.hint` above where the panel belonged. Everything but
 * the one line that mounts it. It is mounted now, on all four catalogue pages.
 *
 * **A frozen list, not a ban.** Deleting unmounted work would answer "is this used?" by making
 * it true, which is the cheapest wrong answer available. The list may only shrink, each entry
 * says WHY it is there, and a NEW orphan is refused outright — the cost of writing a feature
 * nobody mounts should land on the commit that does it, not on the audit two months later.
 */

import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = path.join(__dirname, "..");

/** Why a component is imported by nothing, and what that implies. */
type Verdict =
  | "primitive" // a UI building block, kept for the next screen that needs one
  | "duplicate" // reimplemented inline elsewhere — the only deletion candidates
  | "unmounted"; // written and never rendered: a feature owed a mount

/**
 * The 14, classified. Sorted by what an operator loses while it stays unmounted.
 *
 * `catalogue-consumers` is deliberately ABSENT: it was mounted on 2026-08-01, which is what a
 * shrinking list looks like. It is named here so its removal reads as a fix rather than as a
 * lapse in the record.
 */
const FROZEN_ORPHANS: Readonly<Record<string, Verdict>> = {
  // ── features written and never rendered ────────────────────────────────────────────────
  // 838 lines. Replay a captured turn against the current policy and diff the answers — the
  // demonstrable half of "we can prove what changed". `replay_shadow` is a declared signal.
  "components/observability/replay-panel.tsx": "unmounted",
  // 238 lines. The per-run eval detail the Qualité IA "runs" tab approximates with a table.
  "components/observability/eval-runs.tsx": "unmounted",
  // 244 lines. The recouvrement operator console — the business surface of the second agent.
  "components/recouvrement/recouvrement-console.tsx": "unmounted",
  // 181 lines. A session replayed turn by turn, for demonstrating an incident.
  "components/observability/session-theater.tsx": "unmounted",
  // 94 + 94 lines. The product-preview host and its customer session bar.
  "components/product/apercu-host.tsx": "unmounted",
  "components/product/customer-session-bar.tsx": "unmounted",
  // 52 + 43 lines. Chips naming the model that answered and a generic status pill.
  "components/layout/model-badge.tsx": "unmounted",
  "components/layout/status-badge.tsx": "unmounted",
  // 29 lines. A page scaffold used while building a screen.
  "components/common/scaffold-view.tsx": "unmounted",

  // ── primitives: a component library, not a feature ─────────────────────────────────────
  // shadcn building blocks. "Unused" is their normal state between the screens that need one,
  // and deleting them means re-adding them by hand next time.
  "components/ui/scroll-area.tsx": "primitive",
  "components/ui/separator.tsx": "primitive",

  // ── dead duplicates: reimplemented inline, and the ONLY deletion candidates ────────────
  // Both were rewritten inside `user-menu` / `app-header`. Deleting them is safe only after
  // someone confirms the inline versions cover every case these do — which is a reading, not
  // a grep, and it is not this file's job to assume it was done.
  "components/layout/language-switcher.tsx": "duplicate",
  "components/layout/theme-toggle.tsx": "duplicate",
};

/**
 * Anti-vacuity. 178 components stand in the tree; a floor under it separates "everything is
 * mounted" from "the walk found no files". With the offender list frozen rather than empty,
 * this and the teeth test are what keep the scan honest.
 */
const EXPECTED_MIN_COMPONENTS = 150;

function walk(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules" || entry.name === ".next") continue;
      walk(full, acc);
    } else if (/\.(tsx|ts)$/.test(entry.name)) {
      acc.push(full);
    }
  }
  return acc;
}

/**
 * Is `base` imported from anywhere other than `self`?
 *
 * BOTH the alias form (`@/components/x/y`) and the relative one (`./y`, `../y`). The first
 * version of this scan matched only the alias form and reported `chat-composer.tsx` as an
 * orphan — `chat-room.tsx` imports it with `./chat-composer`, four lines away. A scan that
 * cannot see one import shape reports every user of it as unused.
 */
function importedElsewhere(base: string, self: string, sources: readonly string[]): boolean {
  const escaped = base.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(
    `from\\s+["'][^"']*\\/${escaped}["']|from\\s+["']\\.{1,2}\\/${escaped}["']`,
  );
  return sources.some((file) => file !== self && pattern.test(readFileSync(file, "utf8")));
}

const sources = walk(ROOT).filter((f) => !f.includes(`${path.sep}.next${path.sep}`));
const components = sources.filter(
  (f) =>
    f.includes(`${path.sep}components${path.sep}`) && f.endsWith(".tsx") && !f.includes(".test."),
);
const orphans = components
  .filter((f) => !importedElsewhere(path.basename(f, ".tsx"), f, sources))
  .map((f) => path.relative(ROOT, f).split(path.sep).join("/"));

describe("class I — no component is unmounted by accident", () => {
  it("sees the component tree", () => {
    expect(components.length).toBeGreaterThanOrEqual(EXPECTED_MIN_COMPONENTS);
  });

  it("has teeth: it recognises both import shapes", () => {
    // The positive control — a heavily-imported component must never read as an orphan.
    expect(orphans).not.toContain("components/layout/sidebar.tsx");
    // …and the RELATIVE one, which the first version of this scan missed entirely.
    expect(orphans).not.toContain("components/chat/chat-composer.tsx");
    // The negative control: the list must not be empty, or the two above prove nothing.
    expect(orphans.length).toBeGreaterThan(0);
  });

  it("refuses a NEW orphan", () => {
    const unclassified = orphans.filter((f) => !(f in FROZEN_ORPHANS));
    expect(
      unclassified,
      "a component nothing imports. Mount it, or classify it in FROZEN_ORPHANS with the " +
        "reason — the cost of writing a feature nobody mounts belongs on this commit, not on " +
        "an audit two months from now.",
    ).toEqual([]);
  });

  it("holds the frozen list at its exact size, so it can only shrink", () => {
    expect(
      [...orphans].sort(),
      "mounted one? excellent — delete its line from FROZEN_ORPHANS so the debt goes down on " +
        "the record. `catalogue-consumers` left this list on 2026-08-01.",
    ).toEqual(Object.keys(FROZEN_ORPHANS).sort());
  });

  it("answers the question that was asked: omitted, or reimplemented elsewhere?", () => {
    const byVerdict = Object.values(FROZEN_ORPHANS).reduce<Record<string, number>>((acc, v) => {
      acc[v] = (acc[v] ?? 0) + 1;
      return acc;
    }, {});
    // Nine features owed a mount, two library primitives, two dead duplicates. Only the last
    // pair may ever be deleted, and only after someone READS the inline versions that replaced
    // them — deleting unmounted work would answer "is this used?" by making it true.
    expect(byVerdict).toEqual({ unmounted: 9, primitive: 2, duplicate: 2 });
  });
});
