import { type Page, expect, test } from "@playwright/test";

// Covers the behaviour that survives localization: tone-based filtering, index
// sorting, the detail drawer, popover dismissal, and URL-synced filter state.

const PAGE = "/fr/agents/support-client/connaissances";

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
  // Widen the freshness window first. The default period is "30 derniers jours" and only one
  // source is fresher than that, so the table is already down to a single row before any type
  // filter runs — `after < before` could never hold, whatever the type filter did. The type
  // filter was never the broken thing here.
  await page.getByRole("button", { name: /^Période/ }).click();
  await page.getByRole("menuitem", { name: "Tout", exact: true }).click();
  const before = await page.locator("table tbody tr").count();
  expect(before, "the freshness window still hides the catalogue").toBeGreaterThan(1);

  await page.getByRole("button", { name: "Statut Tous" }).waitFor();
  await page.getByRole("button", { name: "Type Tous" }).click();
  await page.getByRole("menuitem", { name: "Réglementation" }).click();
  await expect(page).toHaveURL(/type=reg/);
  const after = await page.locator("table tbody tr").count();
  expect(after).toBeLessThan(before);
  expect(after).toBeGreaterThan(0);
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

test("an active toggle is journalled S1 with its author on the source sheet", async ({ page }) => {
  // The governed act (activate/deactivate) must land on the sheet's per-source
  // journal, attributed to the verified operator — the OT-01 substrate. The S1
  // append is spooled and drained asynchronously, so the journal is re-read
  // until the act appears. The toggle is flipped and restored so the suite
  // leaves the state as it found it.
  await page.locator("table tbody tr").first().click();
  const drawer = page.locator("dialog[aria-modal=true]");
  await expect(drawer).toBeVisible();

  const toggle = drawer.locator("button[aria-pressed]");
  const wasOn = (await toggle.getAttribute("aria-pressed")) === "true";
  const firstAct = drawer.getByTestId("source-journal").locator("li").first();
  // Earlier governed acts may already sit in the trace with the same label, so
  // the witness is "the NEWEST act changed and is this one", never a bare match.
  const before = (await firstAct.count()) ? await firstAct.innerText() : "";

  await toggle.click();
  // The aria-pressed flip is the mutation-complete barrier: acting again before
  // it lands would re-send the same state and be refused as a silent no-op.
  await expect(toggle).toHaveAttribute("aria-pressed", String(!wasOn));
  await expect(firstAct).not.toHaveText(before, { timeout: 45_000 });
  await expect(firstAct).toContainText(wasOn ? "Désactivée" : "Activée");
  await expect(firstAct).toContainText("admin");

  const mid = await firstAct.innerText();
  await toggle.click(); // restore
  await expect(toggle).toHaveAttribute("aria-pressed", String(wasOn));
  await expect(firstAct).not.toHaveText(mid, { timeout: 45_000 });
  await expect(firstAct).toContainText(wasOn ? "Activée" : "Désactivée");
});
