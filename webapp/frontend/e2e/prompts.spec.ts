import { type Page, expect, test } from "@playwright/test";

// Covers the behaviour that must survive refactors on the Prompts page: the real
// YAML-backed inventory, search + category/variables dropdown filtering,
// row-click selection driving the detail panel and the Content tab that shows
// the actual prompt text.

const PAGE = "/fr/agents/support-client/prompts";

test.use({ viewport: { width: 1672, height: 1000 } });

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 15_000 });
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
