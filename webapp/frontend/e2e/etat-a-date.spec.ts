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
  await expect(page.getByText("État reconstitué à T").first()).toBeVisible();
  await expect(page.locator("table tbody tr").first()).toBeVisible();
});

test("reconstructs a real original response + governance cards", async ({ page }) => {
  await expect(page.getByText("Réponse d'origine").first()).toBeVisible();
  await expect(page.getByText("Garde-fous actifs à T").first()).toBeVisible();
  await expect(page.getByText("Prompt & modèle à T").first()).toBeVisible();
  // Each governance card shows a real "Diff vs etat actuel" section.
  await expect(page.getByText("Diff vs état actuel").first()).toBeVisible();
  await expect(page.getByText("Sources accessibles à l'instant T").first()).toBeVisible();
});

test("the Type filter actually narrows the table", async ({ page }) => {
  const before = await page.locator("table tbody tr").count();
  await page.getByRole("button", { name: "Type Tous" }).click();
  await page.getByRole("menuitem", { name: "Réglementation" }).click();
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
  // Reconstruct at an instant before the audit log starts (via a reference code):
  // 0 decisions are logged by T, so the guardrails diff reports them all "apres T".
  await page.getByPlaceholder(/ID de réponse/).fill("RES-2026-06-01-0000");
  await page.getByRole("button", { name: "Reconstituer" }).click();
  await expect(page.getByText(/décisions du guard journalisées après T/i).first()).toBeVisible({
    timeout: 15_000,
  });
});

test("the premium calendar opens and selects a day", async ({ page }) => {
  await page
    .getByRole("button", { name: /^Maintenant/ })
    .first()
    .click();
  // The homemade popover (month grid + time input) is shown.
  await expect(page.locator('input[type="time"]')).toBeVisible();
  await page.getByRole("button", { name: "20", exact: true }).click();
  // The trigger now reads the selected date instead of "Maintenant".
  await expect(page.getByRole("button", { name: /20.*2026/ }).first()).toBeVisible();
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
  await expect(page.getByText("Snapshots enregistrés")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/^RES-/).first()).toBeVisible();
  await page.reload();
  await expect(page.getByText("Snapshots enregistrés")).toBeVisible();
  await expect(page.getByText(/^RES-/).first()).toBeVisible();
});

test("the sealed (opposable) badge marks the verified reconstruction", async ({ page }) => {
  await expect(page.getByText("Scellé", { exact: true })).toBeVisible();
});

test("downloading the report opens a printable opposable evidence document", async ({ page }) => {
  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: "Télécharger le rapport" }).click();
  const popup = await popupPromise;
  await expect(popup.getByRole("heading", { name: /Rapport d'etat opposable/ })).toBeVisible();
  await popup.close();
});
