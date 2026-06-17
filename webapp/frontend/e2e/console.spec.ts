import { type Page, expect, test } from "@playwright/test";

// Covers the Console (Debug) interactions that must survive refactors: the live
// status bar with its real period select + reset, and the wired footer actions
// (compare navigates to the as-of page, export/close are real buttons). The
// chat stream + thumbs feedback need the live LLM, so they are exercised
// separately; here we assert the deterministic, non-LLM controls are alive.

const PAGE = "/fr/agents/support-client/console";

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
  await expect(page.getByText("Session active").first()).toBeVisible();
});

test("the status bar exposes a real temporal-window select", async ({ page }) => {
  const select = page.getByLabel("Fenetre temporelle");
  await expect(select).toBeVisible();
  await select.selectOption("d30");
  await expect(select).toHaveValue("d30");
  await select.selectOption("h24");
  await expect(select).toHaveValue("h24");
});

test("the footer 'compare' action navigates to the as-of page", async ({ page }) => {
  await page.getByRole("link", { name: "Comparer à la version actuelle" }).click();
  await page.waitForURL(/\/prouver\/etat-a-date/, { timeout: 15_000 });
  expect(page.url()).toContain("/prouver/etat-a-date");
});

test("the export and new-session controls are live buttons", async ({ page }) => {
  await expect(page.getByRole("button", { name: "Exporter la session" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Nouvelle session" }).first()).toBeEnabled();
  // The KPI rail links to the incident timeline (a real route, not a dead button).
  await expect(page.getByRole("link", { name: "Timeline incidents" })).toBeVisible();
});
