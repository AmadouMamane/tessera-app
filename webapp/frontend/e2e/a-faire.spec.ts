import { type Page, expect, test } from "@playwright/test";

// Covers the "A faire" queue backed by the real operator backlog: the table
// lists real items, the rail search filters them, a row click drives the detail
// band, and "Prendre en charge" persists the durable workflow status.

const PAGE = "/fr/agent/a-faire";

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

test("rail search filters the task list", async ({ page }) => {
  const before = await page.locator("table tbody tr").count();
  await page.getByPlaceholder(/Rechercher dans la liste/).fill("IBAN");
  const after = await page.locator("table tbody tr").count();
  expect(after).toBeLessThan(before);
});

test("row click drives the detail band", async ({ page }) => {
  const detail = page.locator("section", { hasText: "Detail selectionne" });
  const secondRow = page.locator("table tbody tr").nth(1);
  const title = (await secondRow.locator("td").nth(2).textContent())?.trim() ?? "";
  await secondRow.click();
  await expect(detail.getByText(title, { exact: false }).first()).toBeVisible();
});

test("'Prendre en charge' persists the workflow status", async ({ page }) => {
  const detail = page.locator("section", { hasText: "Detail selectionne" });
  // Select the first row, then take charge.
  await page.locator("table tbody tr").first().click();
  await detail.getByRole("button", { name: "Prendre en charge" }).click();
  // The detail's status reads "En cours" after the mutation.
  await expect(detail.getByText("En cours").first()).toBeVisible();

  // Reload: the durable status survives (first row badge shows En cours).
  await page.reload();
  await expect(page.locator("table tbody tr").first()).toContainText("En cours");

  // Restore: mark resolved is also durable; leave a known clean-ish state.
  await page.locator("table tbody tr").first().click();
  await detail.getByRole("button", { name: "Marquer resolu" }).click();
  await expect(detail.getByText("Resolu").first()).toBeVisible();
});
