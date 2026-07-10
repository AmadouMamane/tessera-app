import { type Page, expect, test } from "@playwright/test";

// Covers the "A faire" queue backed by the real operator backlog: the table
// lists real items, the rail search filters them, a row click drives the detail
// drawer, and "Prendre en charge" persists the durable workflow status.
//
// Repaired 2026-07-10 against the contract `8f3447d9` ("per-agent scope
// end-to-end + ADR 0015 telemetry spine") actually shipped: that commit
// paginated the table at ten rows and turned the inline detail `<section>` into
// a `<dialog aria-modal>` drawer. The specs still asserted the pre-refonte UI —
// more than ten rows, and a `section` filtered on "Detail selectionne" that
// matches nothing, which is why two of them hung for their full 30 s rather
// than failing on the thing they meant to check. The button labels
// ("Prendre en charge", "Marquer resolu") and the mutation route
// (`/observability/agent-a-faire/item-state`) were never touched.

const PAGE = "/fr/a-faire";

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
  // Ten is the page size (`agent-a-faire.tsx`, `useState(10)`), not the backlog size. The
  // backlog's real size is what the summary reports; asserting "more than one page" keeps
  // the claim true as the seeded corpus grows or shrinks.
  expect(await page.locator("table tbody tr").count()).toBe(10);

  const summary = page.getByText(/Afficher 1 - 10 sur \d+/);
  await expect(summary).toBeVisible();
  const total = Number(((await summary.textContent()) ?? "").match(/sur (\d+)/)?.[1]);
  expect(total).toBeGreaterThan(10);
});

test("rail search filters the task list", async ({ page }) => {
  const before = await page.locator("table tbody tr").count();
  await page.getByPlaceholder(/Rechercher dans la liste/).fill("IBAN");
  const after = await page.locator("table tbody tr").count();
  expect(after).toBeLessThan(before);
});

test("row click drives the detail drawer", async ({ page }) => {
  const secondRow = page.locator("table tbody tr").nth(1);
  const title = (await secondRow.locator("td").nth(2).textContent())?.trim() ?? "";
  await secondRow.click();
  const detail = page.getByRole("dialog");
  await expect(detail.getByText(title, { exact: false }).first()).toBeVisible();
});

test("'Prendre en charge' persists the workflow status", async ({ page }) => {
  // Select the first row, then take charge.
  await page.locator("table tbody tr").first().click();
  const detail = page.getByRole("dialog");
  await detail.getByRole("button", { name: "Prendre en charge" }).click();
  // The detail's status reads "En cours" after the mutation.
  await expect(detail.getByText("En cours").first()).toBeVisible();

  // Reload: the durable status survives (first row badge shows En cours).
  await page.reload();
  await expect(page.locator("table tbody tr").first()).toContainText("En cours");

  // Restore: mark resolved is also durable; leave a known clean-ish state.
  await page.locator("table tbody tr").first().click();
  const reopened = page.getByRole("dialog");
  await reopened.getByRole("button", { name: "Marquer resolu" }).click();
  await expect(reopened.getByText("Resolu").first()).toBeVisible();
});
