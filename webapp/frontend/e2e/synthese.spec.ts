import { type Page, expect, test } from "@playwright/test";

// Covers the Synthese dashboard behaviour that must survive refactors: the KPI
// strip sourced from the live transcript + eval run, the real recent
// conversations, and the wired CTAs / quick-config links that navigate to the
// other agent pages (a dead button would be a failure).

const PAGE = "/fr/agents/support-client/synthese";

test.use({ viewport: { width: 1672, height: 1050 } });

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 20_000 });
}

test.beforeEach(async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByText("Conversations", { exact: true }).first()).toBeVisible();
});

// Repaired 2026-07-10 against the payload `90ebb257` ("refactor(agent-synthese): align
// Synthèse on the multi-agent normative (operational, events-only)") actually ships. That
// commit rewrote `agent_synthese.py`, deleting every string these five tests asserted:
// "cas réussis", "fragments indexés", "Répartition par langue", the "Configuration rapide"
// card, the "Relire à T" button and the "Configurer l'assistant" CTA. The page is fully
// alive — none of the *behaviours* went away, only the labels — so each test is retargeted
// at the surviving surface rather than deleted.

test("renders the real KPI strip from the live sources", async ({ page }) => {
  // Resolution KPI is computed from the eval run (a percentage with a comma).
  await expect(page.getByText("Taux de résolution").first()).toBeVisible();
  await expect(page.getByText(/\d+,\d+%/).first()).toBeVisible();
  // Operational counters, not eval trivia: the strip is events-only since 90ebb257.
  await expect(page.getByText("Tours traités (24h)").first()).toBeVisible();
  // The indexed-fragment count moved into the profile card ("15 sources / 241 fragments").
  await expect(page.getByText(/\d+ sources \/ \d+ fragments/).first()).toBeVisible();
  // The routing-motive breakdown replaced the old language mix.
  await expect(page.getByText(/Répartition des conversations/).first()).toBeVisible();
});

test("recent conversations come from the transcript", async ({ page }) => {
  const card = page.locator("section", { hasText: "Conversations récentes" });
  await expect(card).toBeVisible();
  // Each row shows a real turn-count label ("N echange(s)").
  await expect(card.getByText(/\d+ échange/).first()).toBeVisible();
});

test("the operational-alerts CTA navigates to the agent's guardrails", async ({ page }) => {
  // The "Configuration rapide" card is gone; the guardrails link survives on the
  // operational-alerts card, and it is per-agent (`opAlerts.ctaHref`).
  await page.getByRole("link", { name: "Voir les garde-fous" }).first().click();
  await page.waitForURL(/\/agents\/support-client\/garde-fous/, { timeout: 15_000 });
  expect(page.url()).toContain("/agents/support-client/garde-fous");
});

test("the period control re-queries the transcript window", async ({ page }) => {
  // The period <select> sits directly in the rail now — there is no "Relire à T" button to
  // reveal it. The contract worth asserting is that changing it re-queries the backend for
  // that window; the totals it returns are data, and pinning one ("2 108") is what rotted.
  const periodSelect = page.locator('select:has(option[value="d30"])');
  await expect(periodSelect).toBeVisible();

  const refetch = page.waitForResponse(
    (r) => r.url().includes("agent-synthese") && r.url().includes("period=d30") && r.ok(),
  );
  await periodSelect.selectOption("d30");
  await refetch;
  await expect(periodSelect).toHaveValue("d30");
});

test("the profile CTA navigates to the configuration page", async ({ page }) => {
  await page.getByRole("link", { name: "Voir la configuration active" }).first().click();
  await page.waitForURL(/\/agents\/support-client\/configurations/, { timeout: 15_000 });
  expect(page.url()).toContain("/agents/support-client/configurations");
});
