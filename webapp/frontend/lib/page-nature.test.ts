// The RATCHET over the frozen page-nature model (lib/page-nature.ts).
//
// It walks every zone page ON DISK (the glob may find MORE pages, never fewer) and fails:
//   · a zone page with no declaration — the silent default is forbidden;
//   · a page declared `lens:<X>` that does not wire ITS OWN declared lens. The single door
//     is `loadDeclaredLens("<its-route>", …)`, reached one of two ways, both carrying the
//     page's own route literally: INLINE (the page calls it + passes `lens={…}` to the view)
//     or STREAMED (the page hands `route="<its-route>"` to a streamed breakdown —
//     `<StreamedAgentBreakdown` / `<GovScopeSection` — which calls it on the page's behalf so
//     the fan-out streams behind Suspense). A direct `loadDomainLens` call could load a
//     neighbour's domain, so it is banned in pages either way;
//   · a page declared `org-wide` that renders ANY per-agent view;
//   · a dead registry entry (route with no file) — the freeze must tighten.
//
// Frozen exceptions: ZERO, two-sided, may only shrink. The full PAGE_NATURE table is
// pinned literally: re-classifying a page is a deliberate, reviewable edit — this is the
// non-regression for the five contextualised pages and Vue d'ensemble too.
//
// Mutation contract (each verified red before landing):
//   · drop a lens:security page's lens wiring (strip `lens={…}` from an inline page, or the
//     `route="…"` from a streamed one) → "passes no lens" / "does not wire" → red;
//   · swap its own route for a neighbour's (inline OR streamed) → "own route" check → red;
//   · flip its registry entry to org-wide → "renders a per-agent view" → red;
//   · add a zone page.tsx without declaring it → completeness → red.
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import {
  type AgentBreakdownDomain,
  PAGE_NATURE,
  type PageNature,
  type ZonePageRoute,
} from "@/lib/page-nature";

/** The zone directories the frozen model governs. `agents/[agentId]/*` is per-agent by
 * construction and belongs to another workstream; peripheral surfaces (login, produit,
 * espaces…) are outside the governance cockpit. */
const ZONES = ["surveiller", "agir", "prouver", "configurer", "admin"] as const;

const APP_DIR = path.join(process.cwd(), "app", "[locale]");

/** Anti-vacuity: the discovery must SEE at least the pages known on 2026-07-15. */
const EXPECTED_MIN_PAGES = 27;

/** This set may only SHRINK. Keyed by route. */
const FROZEN_EXCEPTIONS: ReadonlySet<string> = new Set();

// ── Discovery ─────────────────────────────────────────────────────────────────────────────

function walkPages(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walkPages(full, acc);
    else if (entry.name === "page.tsx") acc.push(full);
  }
  return acc;
}

/** route ("/surveiller/qualite-ia") → absolute page.tsx path, for every zone page on disk. */
function discoverZonePages(): Map<string, string> {
  const pages = new Map<string, string>();
  for (const zone of ZONES) {
    for (const file of walkPages(path.join(APP_DIR, zone))) {
      const rel = path.relative(APP_DIR, file);
      const route = `/${path.dirname(rel).split(path.sep).join("/")}`.replace(/\/\.$/, "");
      pages.set(route === "/." ? "/" : route, file);
    }
  }
  return pages;
}

// ── The checker (pure — the "bites" tests feed it synthetic sources) ──────────────────────

/** Source markers that render or load a per-agent view. A scope FILTER (AgentScopeFilter)
 * is deliberately NOT one: narrowing an org-wide stream is an affordance, not a view. */
const PER_AGENT_MARKERS = [
  "<AgentBreakdown",
  "<StreamedAgentBreakdown",
  "<GovScopeSection",
  "initialFleet={fleet}",
  "ReleaseControlView",
  "RbacAgentMatrix",
  "loadDeclaredLens(",
  "loadDomainLens(",
  "loadBreakdownLens(",
] as const;

const BREAKDOWN_DOMAINS: readonly AgentBreakdownDomain[] = [
  "quality",
  "security",
  "compliance",
  "reliability",
  "improvement",
  "observability",
  "proof",
];

function pageViolations(route: string, nature: PageNature, source: string): string[] {
  const violations: string[] = [];
  const present = PER_AGENT_MARKERS.filter((m) => source.includes(m));

  if (nature.kind === "org-wide" || nature.kind === "redirect") {
    if (present.length > 0) {
      violations.push(
        `${route}: declared ${nature.kind} but renders a per-agent view (${present.join(", ")})`,
      );
    }
    if (nature.kind === "redirect" && !source.includes("redirect(")) {
      violations.push(`${route}: declared redirect but does not redirect`);
    }
    return violations;
  }

  // nature.kind === "lens"
  if (nature.domain === "monitoring") {
    // The explicit generic view: AgentBreakdown's default columns (server-rendered,
    // or handed to the overview's temporal client island), and NOTHING loaded — a
    // monitoring page calling a lens loader is drift toward an undeclared domain.
    if (
      !source.includes("<AgentBreakdown") &&
      !source.includes("<GovScopeSection") &&
      !source.includes("initialFleet={fleet}")
    ) {
      violations.push(`${route}: declared lens:monitoring but renders no breakdown`);
    }
    for (const loader of ["loadDeclaredLens(", "loadDomainLens(", "loadBreakdownLens("]) {
      if (source.includes(loader)) {
        violations.push(`${route}: declared lens:monitoring but calls ${loader}…)`);
      }
    }
    if (source.includes("lens={")) {
      violations.push(`${route}: declared lens:monitoring but passes a lens`);
    }
    return violations;
  }

  if (nature.domain === "release") {
    if (!source.includes("ReleaseControlView")) {
      violations.push(`${route}: declared lens:release but does not render ReleaseControlView`);
    }
    return violations;
  }

  if (nature.domain === "access") {
    if (!source.includes("RbacAgentMatrix")) {
      violations.push(`${route}: declared lens:access but does not render RbacAgentMatrix`);
    }
    return violations;
  }

  // An AgentBreakdown domain: the page must go through the single door, with ITS OWN route.
  // Two equivalent wirings are accepted, both carrying the page's own route literally:
  //   · INLINE      — `loadDeclaredLens("<route>", …)` in the page + `lens={…}` to the view;
  //   · STREAMED    — `route="<route>"` on a streamed breakdown (`<StreamedAgentBreakdown` /
  //                   `<GovScopeSection`), which calls `loadDeclaredLens(route, …)` on the
  //                   page's behalf so the fan-out streams behind Suspense.
  // Both forbid a neighbour's route (the own-route literal is required) and a direct
  // domain/breakdown loader in the page (registry bypass).
  const inlineOwnRoute = source.includes(`loadDeclaredLens("${route}"`);
  const streamedBreakdown =
    source.includes("<StreamedAgentBreakdown") || source.includes("<GovScopeSection");
  const streamedOwnRoute = streamedBreakdown && source.includes(`route="${route}"`);
  if (!inlineOwnRoute && !streamedOwnRoute) {
    violations.push(
      `${route}: declared lens:${nature.domain} but does not wire loadDeclaredLens("${route}", …) — ` +
        `inline, or route="${route}" on a streamed breakdown`,
    );
  }
  if (source.includes("loadDomainLens(") || source.includes("loadBreakdownLens(")) {
    violations.push(
      `${route}: declared lens:${nature.domain} but bypasses the registry (direct loader call)`,
    );
  }
  // The lens must actually reach a view: inline via `lens={…}`, or the streamed breakdown that
  // loads and renders it from its own `route="…"`.
  if (!source.includes("lens={") && !streamedBreakdown) {
    violations.push(`${route}: declared lens:${nature.domain} but passes no lens to the view`);
  }
  return violations;
}

// ── The ratchet ───────────────────────────────────────────────────────────────────────────

describe("every zone page declares its nature — no silent default", () => {
  const discovered = discoverZonePages();

  it(`the discovery sees the pages it polices (≥ ${EXPECTED_MIN_PAGES})`, () => {
    expect(discovered.size).toBeGreaterThanOrEqual(EXPECTED_MIN_PAGES);
  });

  it("every page on disk is declared, and every declaration names a page on disk", () => {
    const onDisk = new Set(discovered.keys());
    const declared = new Set(Object.keys(PAGE_NATURE));
    const undeclared = [...onDisk].filter((r) => !declared.has(r) && !FROZEN_EXCEPTIONS.has(r));
    const dead = [...declared].filter((r) => !onDisk.has(r));
    expect(undeclared, `zone pages with NO declared nature: ${undeclared.join(", ")}`).toEqual([]);
    expect(dead, `declared routes with no page on disk: ${dead.join(", ")}`).toEqual([]);
  });

  it("the freeze carries no dead entries — it may only shrink", () => {
    const onDisk = new Set(discovered.keys());
    const deadFrozen = [...FROZEN_EXCEPTIONS].filter((r) => !onDisk.has(r));
    expect(deadFrozen).toEqual([]);
    expect(FROZEN_EXCEPTIONS.size).toBe(0);
  });

  it("every page renders WHAT IT DECLARES — lens pages their lens, org-wide pages no per-agent view", () => {
    const violations: string[] = [];
    for (const [route, file] of discovered) {
      const nature = (PAGE_NATURE as Record<string, PageNature>)[route];
      if (!nature) continue; // named by the completeness test above
      violations.push(...pageViolations(route, nature, readFileSync(file, "utf8")));
    }
    expect(violations, violations.join("\n")).toEqual([]);
  });

  it("pins the frozen model — re-classifying a page is a deliberate edit (non-regression: the five contextualised pages + Vue d'ensemble)", () => {
    expect(PAGE_NATURE).toEqual({
      "/surveiller": { kind: "redirect" },
      "/surveiller/vue-ensemble": { kind: "lens", domain: "monitoring" },
      "/surveiller/qualite-ia": { kind: "lens", domain: "quality" },
      "/surveiller/securite-privacy": { kind: "lens", domain: "security" },
      "/surveiller/conformite": { kind: "lens", domain: "compliance" },
      "/surveiller/fiabilite-cout": { kind: "lens", domain: "reliability" },
      "/surveiller/amelioration": { kind: "lens", domain: "improvement" },
      "/surveiller/observabilite": { kind: "lens", domain: "observability" },
      "/agir/release-control": { kind: "lens", domain: "release" },
      // Product decision 2026-07-15 (HALT resolved): generic views removed — org-wide.
      "/agir/incidents-playbooks": { kind: "org-wide" },
      "/agir/automations": { kind: "org-wide" },
      "/agir/replay-shadow": { kind: "org-wide" },
      "/agir/curation-eval-set": { kind: "org-wide" },
      "/prouver": { kind: "redirect" },
      "/prouver/audit-logs": { kind: "lens", domain: "proof" },
      "/prouver/etat-a-date": { kind: "org-wide" },
      "/prouver/evidence-store": { kind: "org-wide" },
      "/configurer/signal-catalog": { kind: "org-wide" },
      "/configurer/garde-fous": { kind: "org-wide" },
      "/configurer/modeles": { kind: "org-wide" },
      "/configurer/connecteurs": { kind: "org-wide" },
      "/configurer/politiques": { kind: "org-wide" },
      "/configurer/sources-memoire": { kind: "org-wide" },
      "/configurer/parametres": { kind: "org-wide" },
      "/configurer/integrations": { kind: "org-wide" },
      "/admin/utilisateurs": { kind: "org-wide" },
      "/admin/roles-acces": { kind: "lens", domain: "access" },
      "/admin/profil-systeme": { kind: "org-wide" },
    });
  });

  it("every declared breakdown domain is servable — the loader union covers the registry", () => {
    // Compile-time in loadDeclaredLens/DOMAIN_SIGNALS; restated here so the invariant has
    // a named runtime witness too.
    for (const nature of Object.values(PAGE_NATURE)) {
      if (nature.kind !== "lens") continue;
      const bespoke = ["monitoring", "release", "access"].includes(nature.domain);
      const breakdown = (BREAKDOWN_DOMAINS as readonly string[]).includes(nature.domain);
      expect(bespoke || breakdown, `unknown lens domain ${nature.domain}`).toBe(true);
    }
  });
});

describe("the checker actually bites (synthetic sources through the REAL path)", () => {
  const LENS: PageNature = { kind: "lens", domain: "security" };

  it("a lens page rendering a breakdown NOT wired to its own route is named (inline)", () => {
    // Renders the breakdown but wires no lens for it — the inline drop: no own-route load,
    // no lens prop. Under the streamed contract this is a `<GovScopeSection>` with no `route`.
    const source = "<GovScopeSection fleet={fleet} />";
    const v = pageViolations("/x", LENS, source);
    expect(v.some((m) => m.includes("does not wire"))).toBe(true);
  });

  it("a lens page wired to a NEIGHBOUR'S route is named — its own route or nothing (inline)", () => {
    const source = `const lens = await loadDeclaredLens("/surveiller/conformite", fleet);\n<GovScopeSection lens={lens} />`;
    const v = pageViolations("/surveiller/securite-privacy", LENS, source);
    expect(v.some((m) => m.includes('loadDeclaredLens("/surveiller/securite-privacy"'))).toBe(true);
  });

  it("a lens page STREAMED to a NEIGHBOUR'S route is named — the route literal must be its own", () => {
    // The streamed door is `route="…"`; a neighbour's route there loads the neighbour's
    // domain just as an inline neighbour call would, so it must red the same way.
    const source = `<StreamedAgentBreakdown route="/surveiller/conformite" scope={s} locale={l} />`;
    const v = pageViolations("/surveiller/securite-privacy", LENS, source);
    expect(v.some((m) => m.includes('loadDeclaredLens("/surveiller/securite-privacy"'))).toBe(true);
  });

  it("a lens page bypassing the registry with a direct loader call is named", () => {
    const source = `const lens = await loadDeclaredLens("/x", fleet); await loadDomainLens(fleet, "compliance");\n<GovScopeSection lens={lens} />`;
    expect(pageViolations("/x", LENS, source).some((m) => m.includes("bypasses"))).toBe(true);
  });

  it("an org-wide page rendering ANY per-agent view is named, marker by marker", () => {
    for (const marker of [
      "<AgentBreakdown",
      "<StreamedAgentBreakdown",
      "<GovScopeSection",
      "initialFleet={fleet}",
      "RbacAgentMatrix",
    ]) {
      const v = pageViolations("/x", { kind: "org-wide" }, `${marker} whatever`);
      expect(v.some((m) => m.includes(marker))).toBe(true);
    }
  });

  it("a clean page of each nature passes", () => {
    expect(pageViolations("/x", { kind: "org-wide" }, "<StaticCatalogue />")).toEqual([]);
    // Inline wiring (own-route load + lens prop) — still a valid shape.
    expect(
      pageViolations(
        "/x",
        LENS,
        `const lens = await loadDeclaredLens("/x", fleet);\n<GovScopeSection lens={lens} />`,
      ),
    ).toEqual([]);
    // Streamed wiring (own route handed to a streamed breakdown) — the shape the pages use now.
    expect(pageViolations("/x", LENS, `<GovScopeSection route="/x" searchParams={sp} />`)).toEqual(
      [],
    );
    expect(
      pageViolations("/x", LENS, `<StreamedAgentBreakdown route="/x" scope={s} locale={l} />`),
    ).toEqual([]);
    expect(
      pageViolations("/x", { kind: "lens", domain: "monitoring" }, "<GovScopeSection fleet />"),
    ).toEqual([]);
    expect(
      pageViolations(
        "/x",
        { kind: "lens", domain: "monitoring" },
        "<OverviewDashboard initialFleet={fleet} />",
      ),
    ).toEqual([]);
    expect(
      pageViolations("/x", { kind: "lens", domain: "release" }, "<ReleaseControlView data />"),
    ).toEqual([]);
  });

  it("a monitoring page drifting into a loader call is named", () => {
    const v = pageViolations(
      "/x",
      { kind: "lens", domain: "monitoring" },
      `const lens = await loadDomainLens(fleet, "security");\n<GovScopeSection lens={lens} />`,
    );
    expect(v.some((m) => m.includes("calls loadDomainLens"))).toBe(true);
    expect(v.some((m) => m.includes("passes a lens"))).toBe(true);
  });
});

// The registry type is consumed here so a drifting key type shows up in THIS file too.
const _routeType: ZonePageRoute = "/surveiller/qualite-ia";
void _routeType;
