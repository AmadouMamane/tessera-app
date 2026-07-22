/**
 * The FROZEN page-nature model (2026-07-15) — every zone page declares what its
 * per-agent contextualisation IS, and the declaration is load-bearing, not decorative.
 *
 * The principle (the `is_org_wide` doctrine applied to PAGES): a page carries a per-agent
 * view IFF its question decomposes by agent. Three natures:
 *
 *   - `org-wide`  — the page's question does not decompose by agent; it renders NO
 *     per-agent view (adding one would be noise, and the ratchet makes it a red).
 *   - `lens: <domain>` — the page's question decomposes, and its per-agent view answers
 *     THAT question. Most domains render through `AgentBreakdown` with a lens built by
 *     `loadDeclaredLens` (which derives the domain FROM this registry, so a page cannot
 *     render a lens other than the one it declares). Three domains are bespoke renders:
 *     `monitoring` (the AgentBreakdown default columns — legitimate where monitoring IS
 *     the page's own question), `release` (ReleaseControlView cards) and `access`
 *     (RbacAgentMatrix).
 *   - `redirect` — the file only forwards to another route; nothing renders.
 *
 * Every column behind a breakdown domain was MEASURED before being written
 * (`?agent=<id>&signals=…` answering `honoured: ["agent"]` for all six fleet agents);
 * a domain whose facts the spine holds only org-wide gets no column and no lens — the
 * page stays `org-wide` or keeps the explicit `monitoring` declaration until a substrate
 * exists (never a column before its substrate).
 *
 * `lib/page-nature.test.ts` is the ratchet: it discovers every zone page on disk, fails
 * on an undeclared page (no silent default), on a lens page not wiring ITS declared
 * domain, and on an org-wide page rendering any per-agent view. Frozen exceptions: ZERO.
 * Changing an entry here is a product decision — the test pins the whole table.
 */

/** Domains rendered through `AgentBreakdown` with a lens loaded by `loadDeclaredLens`. */
export type AgentBreakdownDomain =
  | "quality"
  | "security"
  | "compliance"
  | "reliability"
  | "improvement"
  | "observability"
  | "proof";

/** Domains with a bespoke per-agent render (not an AgentBreakdown lens load). */
export type BespokeLensDomain = "monitoring" | "release" | "access";

export type LensPageDomain = AgentBreakdownDomain | BespokeLensDomain;

export type PageNature =
  | { kind: "org-wide" }
  | { kind: "redirect" }
  | { kind: "lens"; domain: LensPageDomain };

/**
 * The matrix, page → nature. Product decisions (Amadou, 2026-07-15, HALT resolved): the
 * four AGIR pages (incidents, automations, replay-shadow, curation) have NO per-agent
 * substrate in their own domain (measured) — a card titled "Vue par agent" on them would
 * suggest a decomposition of the domain that does not exist, so the generic view is
 * REMOVED and they are org-wide (pas de vue > fausse décomposition). Replay is the one
 * that deserves a REAL lens someday: `_RunDiff` in replay_shadow.py is already keyed by
 * agent_id (OWED, small future lot). Never a column before its substrate.
 */
export const PAGE_NATURE = {
  // ── SURVEILLER ────────────────────────────────────────────────────────────────────────
  "/surveiller": { kind: "redirect" },
  "/surveiller/vue-ensemble": { kind: "lens", domain: "monitoring" },
  "/surveiller/qualite-ia": { kind: "lens", domain: "quality" },
  "/surveiller/securite-privacy": { kind: "lens", domain: "security" },
  "/surveiller/conformite": { kind: "lens", domain: "compliance" },
  "/surveiller/fiabilite-cout": { kind: "lens", domain: "reliability" },
  "/surveiller/amelioration": { kind: "lens", domain: "improvement" },
  "/surveiller/observabilite": { kind: "lens", domain: "observability" },
  // ── AGIR ──────────────────────────────────────────────────────────────────────────────
  "/agir/release-control": { kind: "lens", domain: "release" },
  "/agir/incidents-playbooks": { kind: "org-wide" },
  "/agir/automations": { kind: "org-wide" },
  "/agir/replay-shadow": { kind: "org-wide" },
  "/agir/curation-eval-set": { kind: "org-wide" },
  // ── PROUVER ───────────────────────────────────────────────────────────────────────────
  "/prouver": { kind: "redirect" },
  "/prouver/audit-logs": { kind: "lens", domain: "proof" },
  "/prouver/etat-a-date": { kind: "org-wide" },
  "/prouver/evidence-store": { kind: "org-wide" },
  // ── CONFIGURER ────────────────────────────────────────────────────────────────────────
  "/configurer/signal-catalog": { kind: "org-wide" },
  "/configurer/garde-fous": { kind: "org-wide" },
  "/configurer/modeles": { kind: "org-wide" },
  "/configurer/connecteurs": { kind: "org-wide" },
  "/configurer/politiques": { kind: "org-wide" },
  "/configurer/sources-memoire": { kind: "org-wide" },
  "/configurer/parametres": { kind: "org-wide" },
  "/configurer/integrations": { kind: "org-wide" },
  // ── ADMIN ─────────────────────────────────────────────────────────────────────────────
  "/admin/utilisateurs": { kind: "org-wide" },
  "/admin/roles-acces": { kind: "lens", domain: "access" },
  "/admin/profil-systeme": { kind: "org-wide" },
} as const satisfies Record<string, PageNature>;

export type ZonePageRoute = keyof typeof PAGE_NATURE;

/**
 * Routes whose declared nature is an AgentBreakdown lens — the ONLY routes
 * `loadDeclaredLens` accepts. Passing an org-wide, redirect, monitoring or bespoke route
 * is a COMPILE error, not a runtime fallback: the incoherent page cannot be written.
 */
export type DeclaredLensRoute = {
  [R in ZonePageRoute]: (typeof PAGE_NATURE)[R] extends { kind: "lens"; domain: infer D }
    ? D extends AgentBreakdownDomain
      ? R
      : never
    : never;
}[ZonePageRoute];

/** The declared nature of a zone page. */
export function pageNature(route: ZonePageRoute): PageNature {
  return PAGE_NATURE[route];
}
