import { type Page, expect, test } from "@playwright/test";

// Covers the behaviour that survives localization: tone-based filtering, index
// sorting, the detail drawer, popover dismissal, and URL-synced filter state.

const PAGE = "/fr/agent/connaissances";

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 15_000 });
}

async function coverageCells(page: Page): Promise<number[]> {
  return page.$$eval("table tbody tr td:nth-child(4)", (cells) =>
    cells.map((c) => Number.parseInt(c.textContent ?? "0", 10) || 0),
  );
}

test.beforeEach(async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.locator("table tbody tr").first()).toBeVisible();
});

test("lists sources with a Volume column", async ({ page }) => {
  await expect(page.getByRole("button", { name: "Volume", exact: true })).toBeVisible();
  expect(await page.locator("table tbody tr").count()).toBeGreaterThan(0);
});

test("filters by type via the stable tone key and syncs the URL", async ({ page }) => {
  const before = await page.locator("table tbody tr").count();
  await page.getByRole("button", { name: "Statut Tous" }).waitFor();
  await page.getByRole("button", { name: "Type Tous" }).click();
  await page.getByRole("menuitem", { name: "Réglementation" }).click();
  await expect(page).toHaveURL(/type=reg/);
  const after = await page.locator("table tbody tr").count();
  expect(after).toBeLessThan(before);
});

test("sorts by Volume ascending via the column header", async ({ page }) => {
  await page.getByRole("button", { name: "Volume", exact: true }).click();
  const asc = await coverageCells(page);
  const sorted = [...asc].sort((a, b) => a - b);
  expect(asc).toEqual(sorted);
});

test("opens the detail drawer on a row and closes it with Escape", async ({ page }) => {
  await page.locator("table tbody tr").first().click();
  const drawer = page.locator("dialog[aria-modal=true]");
  await expect(drawer).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);
});

test("closes a filter dropdown on outside click", async ({ page }) => {
  await page.getByRole("button", { name: "Statut Tous" }).click();
  await expect(page.getByRole("menu")).toBeVisible();
  await page.getByPlaceholder(/Rechercher/).click(); // a neutral element outside the menu
  await expect(page.getByRole("menu")).toHaveCount(0);
});
