import { type Page, expect, test } from "@playwright/test";

// Covers "Etat a date": the response-centric reconstruction (original Q&A from
// the transcript, governance cards with real diffs), the real Reconstituer
// windowing, and the mandatory main-table treatment - working Type filter,
// row-click drawer, and a durable saved snapshot.

const PAGE = "/fr/prouver/etat-a-date";

test.use({ viewport: { width: 1672, height: 1100 } });

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
  await expect(page.getByText("Etat reconstruit a T").first()).toBeVisible();
  await expect(page.locator("table tbody tr").first()).toBeVisible();
});

test("reconstructs a real original response + governance cards", async ({ page }) => {
  await expect(page.getByText("Reponse d'origine").first()).toBeVisible();
  await expect(page.getByText("Garde-fous actifs a T").first()).toBeVisible();
  await expect(page.getByText("Prompt & modele a T").first()).toBeVisible();
  // Each governance card shows a real "Diff vs etat actuel" section.
  await expect(page.getByText("Diff vs état actuel").first()).toBeVisible();
  await expect(page.getByText("Sources accessibles a l'instant T").first()).toBeVisible();
});

test("the Type filter actually narrows the table", async ({ page }) => {
  const before = await page.locator("table tbody tr").count();
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

test("Reconstituer at an early T re-queries the audit-derived diff", async ({ page }) => {
  await page.locator('input[type="datetime-local"]').fill("2026-06-01T00:00");
  await page.getByRole("button", { name: "Reconstituer" }).click();
  // Before the audit log starts, 0 decisions are logged by T -> the guardrails
  // diff reports every decision as logged "apres T".
  await expect(page.getByText(/decisions du guard journalisees apres T/i).first()).toBeVisible({
    timeout: 15_000,
  });
});

test("the Reference field reconstructs at the encoded instant", async ({ page }) => {
  // Live by default -> the snapshot id is SNAP-LIVE.
  await expect(page.getByText("SNAP-LIVE").first()).toBeVisible();
  await page.getByPlaceholder(/ID de réponse/).fill("RES-2026-06-10-1620");
  await page.getByRole("button", { name: "Reconstituer" }).click();
  // The reference resolves to 10 June 2026 -> the reconstruction is dated then.
  await expect(page.getByText(/SNAP-2026-06-10/).first()).toBeVisible({ timeout: 15_000 });
});

test("saving a snapshot persists it durably", async ({ page }) => {
  await page.getByRole("button", { name: "Enregistrer ce snapshot" }).click();
  await expect(page.getByText("Snapshots enregistres")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/^RES-/).first()).toBeVisible();
  await page.reload();
  await expect(page.getByText("Snapshots enregistres")).toBeVisible();
  await expect(page.getByText(/^RES-/).first()).toBeVisible();
});
