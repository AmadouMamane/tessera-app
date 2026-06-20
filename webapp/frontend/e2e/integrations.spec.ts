import { type Page, expect, test } from "@playwright/test";

// Covers the Integrations page (configurer/integrations): the tool catalogue
// built from the real agent tools + guard policy + audit log, controlled search,
// the Type <select> filter, sortable headers, row-click selection driving the
// tab-gated detail (guardrail contract), close, and the manage-policy link.
// Read-only by design (tools + policy are code/PR-owned), so no mutation.

const PAGE = "/fr/configurer/integrations";

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
  await expect(page.getByTestId("integrations-table").locator("tbody tr").first()).toBeVisible();
});

test("lists the real agent tools", async ({ page }) => {
  const rows = page.getByTestId("integrations-table").locator("tbody tr");
  await expect(rows).toHaveCount(5);
  await expect(rows.getByText("Solde de compte")).toBeVisible();
  await expect(rows.getByText("Escalade ticket")).toBeVisible();
});

test("search filters the tools client-side", async ({ page }) => {
  const rows = page.getByTestId("integrations-table").locator("tbody tr");
  await page.getByPlaceholder(/Rechercher un outil/).fill("solde");
  await expect(rows).toHaveCount(1);
  await expect(rows.getByText("Solde de compte")).toBeVisible();
});

test("the Type select filters by category", async ({ page }) => {
  const rows = page.getByTestId("integrations-table").locator("tbody tr");
  // lecture == account_balance + transaction_search.
  await page.getByLabel("Type").selectOption("lecture");
  await expect(rows).toHaveCount(2);
});

test("row click opens the tab-gated guardrail contract", async ({ page }) => {
  const detail = page.getByTestId("integration-detail");
  await expect(detail.getByText("Sélectionnez un outil")).toBeVisible();
  await page
    .getByTestId("integrations-table")
    .getByRole("button", { name: "Solde de compte" })
    .click();
  await expect(detail.getByText("Solde de compte")).toBeVisible();
  await detail.getByRole("button", { name: "Garde-fou" }).click();
  await expect(detail.getByText("Système cible")).toBeVisible();
  await expect(detail.getByText("Core banking")).toBeVisible();
});

test("the close button clears the selection", async ({ page }) => {
  const detail = page.getByTestId("integration-detail");
  await page
    .getByTestId("integrations-table")
    .getByRole("button", { name: "Solde de compte" })
    .click();
  await expect(detail.getByText("Sélectionnez un outil")).toHaveCount(0);
  await detail.getByRole("button", { name: "Fermer" }).click();
  await expect(detail.getByText("Sélectionnez un outil")).toBeVisible();
});

test("sortable calls header reorders the table", async ({ page }) => {
  const rows = page.getByTestId("integrations-table").locator("tbody tr");
  await page
    .getByTestId("integrations-table")
    .getByRole("button", { name: /Appels/ })
    .click();
  // ascending: a zero-call tool floats to the top.
  await expect(rows.first().getByText("0")).toBeVisible();
});

test("the manage-policy action links to the guardrails page", async ({ page }) => {
  await page.getByRole("link", { name: "Gérer la politique" }).click();
  await page.waitForURL(/\/configurer\/garde-fous/, { timeout: 15_000 });
  expect(page.url()).toContain("/configurer/garde-fous");
});
