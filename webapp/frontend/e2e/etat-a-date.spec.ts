import { type Page, expect, test } from "@playwright/test";

// Covers the "Etat a date" point-in-time reconstruction: the live state, the
// sources-accessible table from pgvector, and the real Reconstituer interaction
// that re-queries the guard audit log at an earlier instant T (fewer decisions).

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
});

test("renders the live reconstruction from pgvector + the audit log", async ({ page }) => {
  // Knowledge sources accessible now (single ingest -> all 15) and the table.
  await expect(page.getByText("Documents accessibles").first()).toBeVisible();
  await expect(page.getByText("Sources accessibles a l'instant T").first()).toBeVisible();
  await expect(page.getByText("Accessible").first()).toBeVisible();
  // Policies in force are sourced from the guard policy.
  await expect(page.getByText("Garde-fous").first()).toBeVisible();
});

test("Reconstituer at an early T re-queries the audit window", async ({ page }) => {
  // The audit log starts ~10 June 15:46 UTC; reconstructing before that must
  // show zero guard decisions (the knowledge sources stay accessible).
  await page.locator('input[type="datetime-local"]').fill("2026-06-01T00:00");
  await page.getByRole("button", { name: "Reconstituer" }).click();

  // "Decisions du guard" tile -> 0 at this early instant.
  const decisionsTile = page
    .locator("div")
    .filter({ has: page.getByText("Decisions du guard", { exact: true }) })
    .last();
  await expect(decisionsTile.getByText("0", { exact: true })).toBeVisible({ timeout: 15_000 });
});
