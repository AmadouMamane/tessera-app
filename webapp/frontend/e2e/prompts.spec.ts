import { type Page, expect, test } from "@playwright/test";

// Covers the behaviour that must survive refactors on the Prompts page: the real
// YAML-backed inventory, search + category/variables dropdown filtering,
// row-click selection driving the detail panel, the Content tab that shows the
// actual prompt text, and the sub-tabs (Vue d'ensemble / Variables / Couverture
// i18n) which must gate distinct real views — not be decorative pills.

const PAGE = "/fr/agents/support-client/prompts";

test.use({ viewport: { width: 1672, height: 1000 } });

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 15_000 });
}

function subtab(page: Page, name: string) {
  return page.locator("[data-agent-subtabs]").getByRole("button", { name, exact: true });
}

test.beforeEach(async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.locator("table tbody tr").first()).toBeVisible();
});

test("lists the prompts from the live YAML", async ({ page }) => {
  expect(await page.locator("table tbody tr").count()).toBeGreaterThan(0);
  await expect(page.getByText("Assistant - Système").first()).toBeVisible();
});

test("search filters the prompts client-side", async ({ page }) => {
  const before = await page.locator("table tbody tr").count();
  await page.getByPlaceholder(/Rechercher un prompt/).fill("Memoire");
  const after = await page.locator("table tbody tr").count();
  expect(after).toBeLessThan(before);
  expect(after).toBeGreaterThan(0);
});

test("the Variables filter narrows to prompts with variables", async ({ page }) => {
  const before = await page.locator("table tbody tr").count();
  await page.getByRole("button", { name: "Variables Toutes" }).click();
  await page.getByRole("menuitem", { name: "Avec variables" }).click();
  const after = await page.locator("table tbody tr").count();
  expect(after).toBeLessThan(before);
  await page.getByRole("button", { name: "Tout effacer" }).click();
  expect(await page.locator("table tbody tr").count()).toBe(before);
});

test("row click drives the detail and the Content tab shows real text", async ({ page }) => {
  const detail = page.locator("section", { hasText: "Détails du prompt" });
  await page.getByRole("button", { name: "Assistant - Système" }).click();
  await expect(detail.getByText("Assistant - Système")).toBeVisible();
  await detail.getByRole("button", { name: "Contenu" }).click();
  // The actual system prompt text is rendered in a <pre> block.
  await expect(detail.locator("pre").first()).toBeVisible();
  expect((await detail.locator("pre").first().textContent())?.length ?? 0).toBeGreaterThan(50);
});

test("closes a filter dropdown on outside click", async ({ page }) => {
  await page.getByRole("button", { name: "Catégorie Toutes" }).click();
  await expect(page.getByRole("menu")).toBeVisible();
  await page.getByPlaceholder(/Rechercher un prompt/).click();
  await expect(page.getByRole("menu")).toHaveCount(0);
});

test("the sub-tabs gate distinct real content", async ({ page }) => {
  // Overview shows the prompts inventory table; Variables replaces it with the
  // aggregated template-variable table extracted from the real prompt text.
  await expect(page.getByText("Détails du prompt")).toBeVisible();
  await subtab(page, "Variables").click();
  await expect(page.getByText("Détails du prompt")).toHaveCount(0);
  await expect(page.getByText("Variables uniques")).toBeVisible();
  const varCells = page.locator("table tbody td").filter({ hasText: /^\{\w+\}$/ });
  expect(await varCells.count()).toBeGreaterThan(0);

  // Couverture i18n gates to the per-language length table.
  await subtab(page, "Couverture i18n").click();
  await expect(page.getByText("Variables uniques")).toHaveCount(0);
  await expect(page.getByText("Trilingues")).toBeVisible();

  // Back to the overview restores the inventory.
  await subtab(page, "Vue d'ensemble").click();
  await expect(page.getByText("Détails du prompt")).toBeVisible();
});

test("Variables: row click opens the drawer listing the prompts using it", async ({ page }) => {
  await subtab(page, "Variables").click();
  const firstRow = page.locator("table tbody tr").first();
  const varName = (await firstRow.locator("td").first().textContent())?.trim() ?? "";
  expect(varName).toMatch(/^\{\w+\}$/);
  await firstRow.click();
  const drawer = page.getByRole("dialog");
  await expect(drawer.getByText(varName, { exact: true })).toBeVisible();
  expect(await drawer.locator("li").count()).toBeGreaterThan(0);
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);
});

test("Couverture i18n: real per-language lengths and the drawer previews", async ({ page }) => {
  await subtab(page, "Couverture i18n").click();
  expect(await page.locator("table tbody tr").count()).toBeGreaterThan(0);
  // Every prompt in the live YAML is trilingual — the Trilingues stat must be n/n.
  const trilingual = page
    .locator("div", { has: page.getByText("Trilingues", { exact: true }) })
    .last()
    .locator("span")
    .last();
  await expect(trilingual).toHaveText(/^(\d+)\/\1$/);
  await page.locator("table tbody tr").first().click();
  const drawer = page.getByRole("dialog");
  await expect(drawer.getByText("FR", { exact: true })).toBeVisible();
  await expect(drawer.getByText("DE", { exact: true })).toBeVisible();
  await expect(drawer.getByText("EN", { exact: true })).toBeVisible();
});
