import { type Page, expect, test } from "@playwright/test";

// Incidents & playbooks: the feed is now REAL (guard-deny clusters + the
// low-faithfulness replay cluster); the lifecycle subsystem (playbook engine,
// journal, automations, impact charts, focused tabs) stays flagged. This covers
// the honest split: real zones unflagged, demo zones carrying the compact notice.

const PAGE = "/fr/agir/incidents-playbooks";

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
  await expect(page.getByText("A · État actuel")).toBeVisible({ timeout: 20_000 });
});

test("the real feed renders clusters with honest lifecycle dashes", async ({ page }) => {
  // The dominant real cluster (the red-team injection campaign) is in the queue.
  await expect(page.getByText(/Prompt injection \(\d+\)/).first()).toBeVisible();
  // Lifecycle metrics without a store are dashes, not invented numbers.
  const kpiZone = page.locator("section", { hasText: "A · État actuel" }).first();
  await expect(kpiZone.getByText("—").first()).toBeVisible();
});

test("demo zones carry the compact notice; real zones do not", async ({ page }) => {
  // Execution + impact zones are flagged (playbook engine subsystem).
  const notices = page.getByText(/démonstration/i);
  const count = await notices.count();
  expect(count).toBeGreaterThanOrEqual(2);
  // The triage queue itself (real) does not carry a page-level banner anymore:
  // the first zone above it renders no notice.
  const actualZone = page.locator("section", { hasText: "A · État actuel" }).first();
  await expect(actualZone.getByText(/démonstration/i)).toHaveCount(0);
});

test("focused tabs remain flagged fixture views and switch correctly", async ({ page }) => {
  // The shared TabStrip renders plain buttons here (no role=tab).
  await page.getByRole("button", { name: "Incidents", exact: true }).click();
  await expect(page.getByText(/démonstration/i).first()).toBeVisible();
  // The overview triage zone is dropped on a focused tab (proves switching).
  await expect(page.getByText("B · Diagnostic / triage")).toHaveCount(0);
});
