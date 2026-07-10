import { type Page, expect, test } from "@playwright/test";

// Covers the "A traiter" inbox backed by the real operator backlog (failed eval
// cases): the table lists real items, search + the priority filter narrow it,
// and cycling an item's status from its drawer persists durably.
//
// Repaired 2026-07-10 against the contract `8f3447d9` ("per-agent scope
// end-to-end + ADR 0015 telemetry spine") actually shipped: that commit
// paginated the table at ten rows and moved the status control out of the row —
// the in-table badge is a non-interactive `<span>` now, and the only
// "Changer le statut" button lives inside the row's `<dialog>` drawer. The specs
// still asserted the pre-refonte UI: more than ten rows, and a
// `button[title="Changer le statut"]` that no longer exists.

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

test("lists real backlog items, one page at a time", async ({ page }) => {
  // The page size is ten (`inbox-overview.tsx`, `useState(10)`), so the row count is a
  // property of the paginator, not of the backlog. The backlog's real size is what the
  // summary reports — asserted as "more than one page", never as a seeded constant.
  expect(await page.locator("table tbody tr").count()).toBe(10);

  const summary = page.getByText(/Afficher 1 - 10 sur \d+/);
  await expect(summary).toBeVisible();
  const total = Number(((await summary.textContent()) ?? "").match(/sur (\d+)/)?.[1]);
  expect(total).toBeGreaterThan(10);
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

const STATUS = /^(À faire|En cours|En attente|Résolu)$/;

const rowStatusCell = (page: Page) =>
  page.locator("table tbody tr").first().locator("td").filter({ hasText: STATUS }).first();

test("cycling the status from the row drawer persists it", async ({ page }) => {
  await page.locator("table tbody tr").first().click();
  const drawer = page.getByRole("dialog");
  const drawerStatus = drawer.getByText(STATUS).first();
  const before = (await drawerStatus.textContent())?.trim();

  // Wait for the durable write, not just for the label to flip: reloading on the optimistic
  // render races the POST, and the row would read back its old status.
  const written = page.waitForResponse(
    (r) => r.url().includes("/inbox/item-state") && r.request().method() === "POST" && r.ok(),
  );
  await drawer.getByRole("button", { name: "Changer le statut" }).click();
  await written;

  await expect.poll(async () => (await drawerStatus.textContent())?.trim()).not.toBe(before);
  const after = (await drawerStatus.textContent())?.trim();
  expect(after).toMatch(STATUS);

  // The table behind the drawer is server-rendered and does not re-fetch on the mutation;
  // a reload is what proves the store, and that is the claim this test makes.
  await page.reload();
  await expect(page.locator("table tbody tr").first()).toBeVisible();
  await expect(rowStatusCell(page)).toHaveText(after ?? "");
});
