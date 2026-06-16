import { type Page, expect, test } from "@playwright/test";

// Covers the Synthese dashboard behaviour that must survive refactors: the KPI
// strip sourced from the live transcript + eval run, the real recent
// conversations, and the wired CTAs / quick-config links that navigate to the
// other agent pages (a dead button would be a failure).

const PAGE = "/fr/agent/synthese";

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

test("renders the real KPI strip from the live sources", async ({ page }) => {
  // Resolution KPI is computed from the eval run (a percentage with a comma).
  await expect(page.getByText("Taux de resolution").first()).toBeVisible();
  await expect(page.getByText(/cas reussis/).first()).toBeVisible();
  // Knowledge sources KPI mentions the real indexed-fragment count.
  await expect(page.getByText(/fragments indexes/).first()).toBeVisible();
  // Language mix panel replaces the old fabricated "channels".
  await expect(page.getByText(/Repartition par langue/).first()).toBeVisible();
});

test("recent conversations come from the transcript", async ({ page }) => {
  const card = page.locator("section", { hasText: "Conversations recentes" });
  await expect(card).toBeVisible();
  // Each row shows a real turn-count label ("N echange(s)").
  await expect(card.getByText(/\d+ echange/).first()).toBeVisible();
});

test("quick-config links navigate to the real agent pages", async ({ page }) => {
  const card = page.locator("section", { hasText: "Configuration rapide" });
  await card.getByRole("link", { name: "Garde-fous", exact: true }).click();
  await page.waitForURL(/\/agent\/garde-fous/, { timeout: 15_000 });
  expect(page.url()).toContain("/agent/garde-fous");
});

test("the Configurer CTA navigates to the configuration page", async ({ page }) => {
  await page.getByRole("link", { name: /Configurer l'assistant/ }).click();
  await page.waitForURL(/\/agent\/configurations/, { timeout: 15_000 });
  expect(page.url()).toContain("/agent/configurations");
});
