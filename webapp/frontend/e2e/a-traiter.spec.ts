import { type Page, expect, test } from "@playwright/test";

// Covers the "A traiter" inbox backed by the real operator backlog (failed eval
// cases): the table lists real items, search + the priority filter narrow it,
// and clicking a status badge cycles + persists the durable status.

const PAGE = "/fr/a-traiter";

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

test("lists real backlog items", async ({ page }) => {
  expect(await page.locator("table tbody tr").count()).toBeGreaterThan(10);
});

test("search filters the queue client-side", async ({ page }) => {
  const before = await page.locator("table tbody tr").count();
  await page.getByPlaceholder(/Rechercher dans la liste/).fill("IBAN");
  const after = await page.locator("table tbody tr").count();
  expect(after).toBeLessThan(before);
});

test("the priority filter narrows the queue", async ({ page }) => {
  const before = await page.locator("table tbody tr").count();
  await page.getByLabel("Priorité").selectOption("urgent");
  const after = await page.locator("table tbody tr").count();
  expect(after).toBeLessThan(before);
  expect(after).toBeGreaterThan(0);
});

test("clicking a status badge cycles and persists the status", async ({ page }) => {
  const badge = page.locator('button[title="Changer le statut"]').first();
  const before = (await badge.textContent())?.trim();
  await badge.click();
  // The status label changes (todo -> en cours, etc.).
  await expect.poll(async () => (await badge.textContent())?.trim()).not.toBe(before);
  const afterClick = (await badge.textContent())?.trim();

  // Reload: the durable mutation survives.
  await page.reload();
  const reloaded = page.locator('button[title="Changer le statut"]').first();
  await expect(reloaded).toHaveText(afterClick ?? "");
});
