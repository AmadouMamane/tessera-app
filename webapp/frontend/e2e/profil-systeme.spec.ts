import { type Page, expect, test } from "@playwright/test";

// Covers the System profile page (admin/profil-systeme): the real runtime
// (Python / platform / installed dependency versions), the honest health checks
// probing the on-disk artifacts, the runtime/audit panel, and the wired
// Refresh button + "view audit log" link. Read-only by design (a status surface),
// so the functional axis is refresh + nav, not a mutation.

const PAGE = "/fr/admin/profil-systeme";

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
  await expect(page.getByText("Versions & dépendances")).toBeVisible();
});

test("reports the real runtime and installed dependencies", async ({ page }) => {
  // The versions panel lists real installed dependencies.
  await expect(page.getByText("FastAPI").first()).toBeVisible();
  // mcp-firewall is the pinned dependency that defends the reuse positioning.
  await expect(page.getByText("mcp-firewall").first()).toBeVisible();
});

test("shows the honest health checks", async ({ page }) => {
  await expect(page.getByText("Politique garde-fous")).toBeVisible();
  await expect(page.getByText("Corpus réglementaire")).toBeVisible();
});

test("the refresh button is wired", async ({ page }) => {
  const refresh = page.getByRole("button", { name: "Actualiser" });
  await expect(refresh).toBeVisible();
  await refresh.click();
  await expect(page.getByText("Versions & dépendances")).toBeVisible();
});

test("the view-audit link navigates to the audit log", async ({ page }) => {
  await page
    .getByRole("link", { name: /Voir le journal|Voir toutes les vérifications/ })
    .first()
    .click();
  await page.waitForURL(/\/prouver\/audit-logs/, { timeout: 15_000 });
  expect(page.url()).toContain("/prouver/audit-logs");
});
