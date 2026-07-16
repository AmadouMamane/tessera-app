import { type Page, expect, test } from "@playwright/test";

// Covers the Evaluations sub-tabs, which must gate distinct real content (not be
// decorative pills), plus the interactions that must survive refactors: the
// Dimensions type filter narrows rows, a header click sorts, a row click opens a
// drawer, Jeux d'évaluations / Résultats / Versions render their real tables, and
// Exports offers real downloads. All sourced from the real llama3.2:3b run.

const PAGE = "/fr/agents/support-client/evaluations";

test.use({ viewport: { width: 1672, height: 1050 } });

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 20_000 });
}

function subtab(page: Page, name: string) {
  return page.locator("[data-agent-subtabs]").getByRole("button", { name, exact: true });
}

test.beforeEach(async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByText("Score global").first()).toBeVisible();
});

test("the sub-tabs gate distinct real content", async ({ page }) => {
  // Overview shows the release-gate verdict; Jeux shows the set catalogue.
  await expect(page.getByText("Verdict du gate de release")).toBeVisible();
  await subtab(page, "Jeux d'évaluations").click();
  await expect(page.getByText("Verdict du gate de release")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Portée Cet agent + partagés" })).toBeVisible();

  // Exports gates to download cards.
  await subtab(page, "Exports").click();
  await expect(page.getByRole("button", { name: "Télécharger" }).first()).toBeVisible();
});

test("Jeux d'évaluations: default scope hides sets bound to other agents", async ({ page }) => {
  await subtab(page, "Jeux d'évaluations").click();
  // On the support-client page the default scope keeps this agent's set and the
  // shared ones; sets bound to other agents (recouvrement, onboarding) stay out.
  const table = page.locator("table");
  await expect(table.getByText("Support Client — SAV", { exact: false })).toBeVisible();
  await expect(table.getByText("Recouvrement —", { exact: false })).toHaveCount(0);
  // Widening the Portée filter to "Tous" reveals the whole registry.
  await page.getByRole("button", { name: "Portée Cet agent + partagés" }).click();
  await page.getByRole("menuitem", { name: "Tous", exact: true }).click();
  await expect(table.getByText("Recouvrement —", { exact: false }).first()).toBeVisible();
});

test("Dimensions: type filter narrows, header sorts, row opens the detail", async ({ page }) => {
  await subtab(page, "Dimensions").click();
  const before = await page.locator("tbody tr").count();
  await page.getByRole("button", { name: "Type Tous" }).click();
  await page.getByRole("menuitem", { name: "Agent", exact: true }).click();
  expect(await page.locator("tbody tr").count()).toBeLessThan(before);
  await page.getByRole("button", { name: "Réinitialiser" }).click();
  expect(await page.locator("tbody tr").count()).toBe(before);

  const header = page.getByRole("button", { name: /^Tests/ });
  await header.click();
  await expect(page.locator("thead th", { hasText: "Tests" })).toHaveAttribute(
    "aria-sort",
    "ascending",
  );

  const firstRow = page.locator("tbody tr").first();
  const name = (await firstRow.locator("td").first().innerText()).trim();
  await firstRow.click();
  const detail = page.locator("section", { hasText: "Détails de l'évaluation" });
  await expect(detail.getByText(name).first()).toBeVisible();
});

test("Jeux d'évaluations: a set row opens a drawer listing its cases", async ({ page }) => {
  await subtab(page, "Jeux d'évaluations").click();
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await page.locator("tbody tr").first().click();
  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();
  await expect(drawer.getByText("Cas du jeu", { exact: false })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("Résultats: a case row opens a drawer with the test query and answer", async ({ page }) => {
  await subtab(page, "Résultats").click();
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await page.locator("tbody tr").first().click();
  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();
  await expect(drawer.getByText("Requête de test")).toBeVisible();
  await expect(drawer.getByText("Réponse du modèle")).toBeVisible();
});

test("Versions & historique: the run timeline renders real runs", async ({ page }) => {
  await subtab(page, "Versions & historique").click();
  await expect(page.locator("thead th", { hasText: "Verdict" })).toBeVisible();
  await expect(page.locator("tbody tr").first()).toBeVisible();
});

test("the overview quick actions link to real routes", async ({ page }) => {
  const quick = page.locator("section", { hasText: "Actions rapides" });
  await quick.getByRole("link", { name: "Comparer versions" }).click();
  await page.waitForURL(/\/prouver\/etat-a-date/, { timeout: 15_000 });
  expect(page.url()).toContain("/prouver/etat-a-date");
});
