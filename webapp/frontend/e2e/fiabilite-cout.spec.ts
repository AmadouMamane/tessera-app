import { type Page, expect, test } from "@playwright/test";

// The Fiabilité & coût dashboard shipped with a dead 7-tab bar (static <span>s,
// no activeTab state) over one always-rendered blob. This covers the real
// behaviour that must survive refactors: the tab bar switches the content, and
// each tab renders its own curated view over the live reliability report.

const PAGE = "/fr/surveiller/fiabilite-cout";

// Wide desktop viewport so the KPI strip + side rail lay out without wrapping.
test.use({ viewport: { width: 1672, height: 1000 } });

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 15_000 });
}

const panel = (page: Page) => page.locator("#reliability-tabpanel");

test.beforeEach(async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByRole("tab", { name: "Vue d'ensemble" })).toBeVisible();
});

test("overview tab is selected by default and shows the KPI strip", async ({ page }) => {
  await expect(page.getByRole("tab", { name: "Vue d'ensemble" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(panel(page).getByText("Disponibilité").first()).toBeVisible();
  await expect(panel(page).getByText("Budget & prévisions")).toBeVisible();
  // Vue d'ensemble is comprehensive (normative 08): the cost-by-model table
  // renders here too. Tab switching is proven by the focused tabs dropping
  // content (see the cost/capacity tests), not by the overview hiding it.
  await expect(panel(page).getByText(/Coût par modèle/)).toBeVisible();
});

test("clicking Coûts switches to the real cost view", async ({ page }) => {
  await page.getByRole("tab", { name: "Coûts & consommation" }).click();
  await expect(page.getByRole("tab", { name: "Coûts & consommation" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(panel(page).getByText(/Coût par modèle/)).toBeVisible();
  await expect(panel(page).getByText(/Top services par coût/)).toBeVisible();
  // The availability KPI is not part of the cost tab.
  await expect(panel(page).getByText("Disponibilité")).toHaveCount(0);
});

test("Incidents and Capacité tabs each reveal their own real panels", async ({ page }) => {
  await page.getByRole("tab", { name: "Erreurs & incidents" }).click();
  await expect(panel(page).getByText(/Incidents récents/)).toBeVisible();

  await page.getByRole("tab", { name: "Capacité & quotas" }).click();
  await expect(panel(page).getByText(/Répartition par fournisseur/)).toBeVisible();
  await expect(panel(page).getByText("Volume par jour")).toBeVisible();
  // Leaving the cost tab means its model table is gone again.
  await expect(panel(page).getByText(/Coût par modèle/)).toHaveCount(0);
});
