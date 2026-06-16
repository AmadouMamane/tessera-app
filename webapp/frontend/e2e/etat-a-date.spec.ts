import { type Page, expect, test } from "@playwright/test";

// Covers "Etat a date": the live reconstruction from pgvector + the audit log,
// the real Reconstituer windowing, and the mandatory main-table treatment -
// working Type filter, row-click drawer, and a durable saved snapshot.

const PAGE = "/fr/prouver/etat-a-date";

test.use({ viewport: { width: 1672, height: 1000 } });

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
  await expect(page.getByText("Sources actives").first()).toBeVisible();
  await expect(page.locator("table tbody tr").first()).toBeVisible();
});

test("renders the live reconstruction from pgvector + the audit log", async ({ page }) => {
  await expect(page.getByText("Documents accessibles").first()).toBeVisible();
  await expect(page.getByText("Sources accessibles a l'instant T").first()).toBeVisible();
  await expect(page.getByText("Garde-fous").first()).toBeVisible();
});

test("the Type filter actually narrows the table", async ({ page }) => {
  const before = await page.locator("table tbody tr").count();
  // The filter trigger's accessible name is "Type Tous" (label + current value);
  // the sortable header button is just "Type" - target the trigger.
  await page.getByRole("button", { name: "Type Tous" }).click();
  await page.getByRole("menuitem", { name: "Reglementation" }).click();
  const after = await page.locator("table tbody tr").count();
  expect(after).toBeLessThan(before);
  expect(after).toBeGreaterThan(0);
});

test("clicking a table row opens the detail drawer", async ({ page }) => {
  await expect(page.locator("dialog")).toHaveCount(0);
  await page.locator("table tbody tr").first().click();
  const drawer = page.locator("dialog");
  await expect(drawer).toBeVisible();
  await expect(drawer.getByText("Détail de la source")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator("dialog")).toHaveCount(0);
});

test("Reconstituer at an early T re-queries the audit window", async ({ page }) => {
  await page.locator('input[type="datetime-local"]').fill("2026-06-01T00:00");
  await page.getByRole("button", { name: "Reconstituer" }).click();
  const decisionsTile = page
    .locator("div")
    .filter({ has: page.getByText("Decisions du guard", { exact: true }) })
    .last();
  await expect(decisionsTile.getByText("0", { exact: true })).toBeVisible({ timeout: 15_000 });
});

test("saving a snapshot persists it durably", async ({ page }) => {
  await page.getByRole("button", { name: "Enregistrer ce snapshot" }).click();
  // The snapshot appears in the durable list with its reference code.
  await expect(page.getByText(/^RES-/).first()).toBeVisible({ timeout: 15_000 });
  // It survives a reload (durable store, not in-memory).
  await page.reload();
  await expect(page.getByText("Snapshots enregistres")).toBeVisible();
  await expect(page.getByText(/^RES-/).first()).toBeVisible();
});
