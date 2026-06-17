import { type Page, expect, test } from "@playwright/test";

// Covers the Historique table interactions that must survive refactors: the
// status filter changes the row set, a header click sorts, a row click drives
// the detail panel (with the real question/answer in the Messages tab), and the
// client pagination advances. All sourced from the real llama3.2:3b eval run.

const PAGE = "/fr/agents/support-client/historique";

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
  await expect(page.getByText("Sessions totales").first()).toBeVisible();
});

test("the status filter narrows the table to failures", async ({ page }) => {
  const table = page.locator("table");
  await expect(table.getByText("Réussie").first()).toBeVisible();
  await page.getByRole("button", { name: "Statut Tous" }).click();
  await page.getByRole("menuitem", { name: "Échec", exact: true }).click();
  // After filtering to failures, no "Réussie" badge remains in the page slice.
  await expect(table.getByText("Réussie")).toHaveCount(0);
  await expect(table.getByText("Échec").first()).toBeVisible();
});

test("a row click drives the detail panel and the real Q/A", async ({ page }) => {
  const firstRow = page.locator("tbody tr").first();
  const sid = await firstRow.locator("td").first().innerText();
  await firstRow.click();
  const detail = page.locator("section", { hasText: "Détails de la session" });
  await expect(detail.getByText(sid.trim(), { exact: false }).first()).toBeVisible();
  // The Messages tab shows the real question + the model's answer.
  await detail.getByRole("button", { name: "Messages (2)" }).click();
  await expect(detail.getByText("Question", { exact: true })).toBeVisible();
  await expect(detail.getByText("Réponse de l'agent")).toBeVisible();
});

test("pagination advances to the next page", async ({ page }) => {
  await expect(page.getByText(/1-10 sur \d+ sessions/)).toBeVisible();
  await page.getByRole("button", { name: "Page suivante" }).click();
  await expect(page.getByText(/11-20 sur \d+ sessions/)).toBeVisible();
});

test("a header click sorts the table", async ({ page }) => {
  const header = page.getByRole("button", { name: /^Tokens/ });
  await header.click();
  await expect(page.locator("thead th", { hasText: "Tokens" })).toHaveAttribute(
    "aria-sort",
    "ascending",
  );
  await header.click();
  await expect(page.locator("thead th", { hasText: "Tokens" })).toHaveAttribute(
    "aria-sort",
    "descending",
  );
});
