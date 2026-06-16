import { type Page, expect, test } from "@playwright/test";

// Covers the Evaluations table interactions that must survive refactors: the
// type filter narrows the rows, a header click sorts, and a row click drives the
// detail panel (with the per-tab content). All sourced from the real
// llama3.2:3b failure-catalogue run.

const PAGE = "/fr/agent/evaluations";

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
  await expect(page.getByText("Score global").first()).toBeVisible();
});

test("the type filter narrows the evaluation sets", async ({ page }) => {
  const before = await page.locator("tbody tr").count();
  await page.getByRole("button", { name: "Type Tous" }).click();
  await page.getByRole("menuitem", { name: "Agent", exact: true }).click();
  const after = await page.locator("tbody tr").count();
  expect(after).toBeLessThan(before);
  await page.getByRole("button", { name: "Réinitialiser" }).click();
  expect(await page.locator("tbody tr").count()).toBe(before);
});

test("a header click sorts the table", async ({ page }) => {
  const header = page.getByRole("button", { name: /^Tests/ });
  await header.click();
  await expect(page.locator("thead th", { hasText: "Tests" })).toHaveAttribute(
    "aria-sort",
    "ascending",
  );
});

test("a row click drives the detail panel and its tabs", async ({ page }) => {
  const firstRow = page.locator("tbody tr").first();
  const name = (await firstRow.locator("td").first().innerText()).trim();
  await firstRow.click();
  const detail = page.locator("section", { hasText: "Détails de l'évaluation" });
  await expect(detail.getByText(name).first()).toBeVisible();
  await detail.getByRole("button", { name: "Configuration" }).click();
  await expect(detail.getByText("Accès RBAC")).toBeVisible();
  await detail.getByRole("button", { name: "Résultats", exact: true }).click();
  await expect(detail.getByText("Cas réussis")).toBeVisible();
});

test("the quick actions link to real routes", async ({ page }) => {
  const quick = page.locator("section", { hasText: "Actions rapides" });
  await quick.getByRole("link", { name: "Comparer versions" }).click();
  await page.waitForURL(/\/prouver\/etat-a-date/, { timeout: 15_000 });
  expect(page.url()).toContain("/prouver/etat-a-date");
});
