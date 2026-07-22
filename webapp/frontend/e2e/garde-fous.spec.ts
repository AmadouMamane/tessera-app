import { type Page, expect, test } from "@playwright/test";

// Covers the behaviour that must survive refactors on the Garde-fous page:
// real rules table, search + tone-based dropdown filtering, the advanced Mode
// popover, row-click selection driving the detail panel, and the enable/disable
// toggle that mutates durable state (reverted at the end of the test).

const PAGE = "/fr/agents/support-client/garde-fous";

// Pin a wide desktop viewport so the filter bar does not wrap (the page lays the
// rule table + detail panel side by side at xl+).
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

test("lists the guard rules from the live policy", async ({ page }) => {
  expect(await page.locator("table tbody tr").count()).toBeGreaterThan(0);
  await expect(page.getByText("Prompt injection - Blocage").first()).toBeVisible();
});

test("search filters the rules client-side", async ({ page }) => {
  const before = await page.locator("table tbody tr").count();
  await page.getByPlaceholder(/Rechercher une r/).fill("Outil");
  const after = await page.locator("table tbody tr").count();
  expect(after).toBeLessThan(before);
  expect(after).toBeGreaterThan(0);
});

test("filters by category via the stable tone key", async ({ page }) => {
  const before = await page.locator("table tbody tr").count();
  await page.getByRole("button", { name: "Catégorie Toutes" }).click();
  await page.getByRole("menuitem", { name: "Outils" }).click();
  const after = await page.locator("table tbody tr").count();
  expect(after).toBeLessThan(before);
  // The active-filter chip appears and clears the filter on demand.
  await page.getByRole("button", { name: "Tout effacer" }).click();
  expect(await page.locator("table tbody tr").count()).toBe(before);
});

test("the advanced Filtres popover exposes a Mode filter", async ({ page }) => {
  await page.getByRole("button", { name: "Filtres" }).click();
  await expect(page.getByRole("menu").getByText("Mode", { exact: true })).toBeVisible();
  const before = await page.locator("table tbody tr").count();
  await page.getByRole("menuitem", { name: "Blocage" }).click();
  expect(await page.locator("table tbody tr").count()).toBeLessThan(before);
});

test("row click drives the detail panel", async ({ page }) => {
  const detail = page.locator("section", { hasText: "Détails du garde-fou" });
  await page.getByRole("button", { name: "Outil - Solde de compte" }).click();
  await expect(detail.getByText("Outil - Solde de compte")).toBeVisible();
  // Tabs gate content: Configuration shows the technical config block.
  await detail.getByRole("button", { name: "Configuration" }).click();
  await expect(detail.getByText("Configuration technique")).toBeVisible();
});

test("the enable/disable toggle flips state and reverts", async ({ page }) => {
  const detail = page.locator("section", { hasText: "Détails du garde-fou" });
  await page.getByRole("button", { name: "Outil - Solde de compte" }).click();
  const toggle = detail.getByRole("switch");
  // The rule state is DURABLE and shared on a dev banc: never presume it starts
  // enabled (a polluted store made this spec red on main). Witness the flip and
  // the revert from whatever state it is actually in, and leave it as found.
  await expect(toggle).toBeVisible();
  const initial = await toggle.getAttribute("aria-checked");
  const flipped = initial === "true" ? "false" : "true";
  await toggle.click();
  // The mutation's response rebuilds the whole garde-fous payload (an OWED
  // full-ledger read) — regularly >5s on a cold banc, with the switch disabled
  // while pending. Wait for the round-trip, don't race it.
  await expect(toggle).toHaveAttribute("aria-checked", flipped, { timeout: 30_000 });
  // Restore the durable state so the test leaves nothing dirty.
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", initial ?? "true", { timeout: 30_000 });
});

test("closes a filter dropdown on outside click", async ({ page }) => {
  await page.getByRole("button", { name: "Catégorie Toutes" }).click();
  await expect(page.getByRole("menu")).toBeVisible();
  await page.getByPlaceholder(/Rechercher une r/).click();
  await expect(page.getByRole("menu")).toHaveCount(0);
});

test("the 'create guardrail' action links to the policy config page", async ({ page }) => {
  await page.getByRole("link", { name: "Créer un garde-fou" }).click();
  await page.waitForURL(/\/configurer\/garde-fous/, { timeout: 15_000 });
  expect(page.url()).toContain("/configurer/garde-fous");
});
