import { type Page, expect, test } from "@playwright/test";

/**
 * The app-grid menu — the operator→product toggle (headers spec, Addendum borrowing (b)).
 *
 * ADR 0013 permits exactly ONE cross-plane direction: an operator, holding the higher
 * privilege, may step down into a business or customer space. The reverse never exists. This
 * file asserts that asymmetry from both sides, because it is a permission boundary that looks
 * like a convenience menu.
 *
 * Note for whoever reads the ledger: the menu was reported "missing on main" on 2026-07-09.
 * It is not. It ships as `OperatorProductMenu` in `components/layout/app-header.tsx`, rendered
 * only by `CockpitTools` (the `plan === "cockpit"` branch), and the cockpit itself sits behind
 * `CockpitAuthGate`. The earlier grep looked for `app-grid|AppGrid|apps-menu|AppsMenu`. What
 * was genuinely missing is this spec: the gating was structural and unasserted.
 *
 * Selectors are roles and visible text, never CSS classes.
 */

test.use({ viewport: { width: 1672, height: 1000 } });

const MENU = "Espaces métier et client";

async function login(page: Page, user: string, password: string) {
  await page.goto("/fr/login");
  await page.fill("#login-username", user);
  await page.fill("#login-password", password);
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 20_000 });
}

test("an operator sees the menu, and it opens both spaces", async ({ page }) => {
  await login(page, "admin", "tessera-admin");
  await page.goto("/fr/agents");

  const grid = page.getByRole("button", { name: MENU });
  await expect(grid).toBeVisible();
  await grid.click();

  // The two destinations ADR 0013 allows an operator to step down into.
  const business = page.getByRole("menuitem", { name: "Espaces métier" });
  const client = page.getByRole("menuitem", { name: "Espace client" });
  await expect(business).toBeVisible();
  await expect(client).toBeVisible();

  await business.click();
  await page.waitForURL(/\/espaces/, { timeout: 15_000 });
  expect(page.url()).toContain("/espaces");
});

test("the menu is absent from the product plane it leads to — the step down is one-way", async ({
  page,
}) => {
  await login(page, "admin", "tessera-admin");
  // Same operator, product surface: the header there is the `business`/`launcher` plan, which
  // renders no `CockpitTools`. There is no toggle back up hiding in the product chrome.
  await page.goto("/fr/produit");
  await expect(page.getByRole("button", { name: MENU })).toHaveCount(0);
});

test("a business-plane role never sees the menu, and cannot reach the cockpit that carries it", async ({
  page,
}) => {
  // `collections` is the business-plane role: `spaceRedirectForRole` lands it on its own
  // console, and `hasCockpitAccess` refuses it the cockpit outright.
  await login(page, "collections", "tessera-collections");
  await page.goto("/fr/recouvrement");
  await expect(page.getByRole("button", { name: MENU })).toHaveCount(0);

  // And the authority, not merely the routing: asking for a cockpit page bounces to login.
  await page.goto("/fr/agents");
  await page.waitForURL(/\/login/, { timeout: 15_000 });
  await expect(page.getByRole("button", { name: MENU })).toHaveCount(0);
});

test("the menu never speaks the platform's name to the product plane", async ({ page }) => {
  await login(page, "admin", "tessera-admin");
  await page.goto("/fr/agents");
  const grid = page.getByRole("button", { name: MENU });
  await grid.click();
  // Lexicon rule: the labels name the destination, never the platform.
  await expect(page.getByRole("menu")).not.toContainText(/Tessera/i);
});
