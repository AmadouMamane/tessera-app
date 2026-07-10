import { type Page, expect, test } from "@playwright/test";

/**
 * The single application header (`docs/design/header-normative.md` + the premium spec).
 *
 * Three claims the refonte makes, none of which any unit test can see:
 *   1. The composite posture pill is a real popover, not a permanent strip — the strip was
 *      explicitly REFUSED (it regresses rule 2). Its content must be the live system posture.
 *   2. Search is a `⌘K` affordance that opens the command palette, both by click and by chord.
 *   3. Identity lives in the cockpit's side rail, never in its header — the header's right-hand
 *      cluster keeps one fixed order everywhere.
 *
 * Selectors are roles, labels and visible text, never CSS classes.
 */

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
  await page.goto("/fr/agents");
});

test("the posture pill is a popover, and it carries the live system posture", async ({ page }) => {
  const pill = page.getByRole("button", { name: "État système" });
  await expect(pill).toBeVisible();

  // Refused by the spec: a permanent posture strip. The facts must be BEHIND the pill.
  await expect(page.getByText("Posture système")).toHaveCount(0);

  await pill.click();
  await expect(page.getByText("Posture système")).toBeVisible();
  // The four real rows — environment, model, data residence, ledger integrity.
  await expect(page.getByText("Environnement")).toBeVisible();
  await expect(page.getByText("Modèle", { exact: true })).toBeVisible();
  await expect(page.getByText("Résidence", { exact: true })).toBeVisible();
  await expect(page.getByText("Intégrité ledger")).toBeVisible();
});

test("the search affordance advertises ⌘K and opens the command palette", async ({ page }) => {
  const search = page.getByRole("button", { name: /Rechercher agents, dossiers et signaux/ });
  await expect(search).toBeVisible();
  await expect(search).toContainText("Rechercher / Commandes");
  await expect(search).toContainText("⌘K");

  await search.click();
  await expect(page.getByRole("dialog", { name: "Palette de commandes" })).toBeVisible();

  // Escape is bound to the palette's INPUT (`command-palette.tsx` `onKeyDown`), not to the
  // window — so it only closes once focus has landed there. Pressing it on the body, as this
  // spec first did, is a race that passes on a warm machine and fails inside a full suite run.
  // Waiting for focus asserts the real contract instead of the lucky one.
  const input = page.getByPlaceholder("Rechercher agents, pages, actions…");
  await expect(input).toBeFocused();
  await input.press("Escape");
  await expect(page.getByRole("dialog", { name: "Palette de commandes" })).toHaveCount(0);
});

test("the ⌘K chord itself opens the palette", async ({ page }) => {
  await page.keyboard.press("ControlOrMeta+k");
  await expect(page.getByRole("dialog", { name: "Palette de commandes" })).toBeVisible();
});

test("identity is anchored in the cockpit side rail, not in the header", async ({ page }) => {
  // One identity control, and it names the role plus the security fact the spec asked for
  // ("Session active <t>" in the identity block — banking-grade, borrowed item (c)).
  const identity = page.getByRole("button", { name: /Menu utilisateur · / });
  await expect(identity).toBeVisible();
  await expect(identity).toContainText("Session active");

  // It sits in the navigation rail (`<aside>`), not inside the page `<header>`.
  await expect(
    page.locator("aside").getByRole("button", { name: /Menu utilisateur · / }),
  ).toBeVisible();
  await expect(
    page.locator("header").getByRole("button", { name: /Menu utilisateur · / }),
  ).toHaveCount(0);
});
