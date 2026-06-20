import { type Page, expect, test } from "@playwright/test";

// Covers the behaviour that must survive refactors on the Roles & access page
// (admin/roles-acces): the role catalogue built from the real RBAC model
// (3 enforced roles), controlled search, the Type <select> filter, sortable
// headers, row-click selection driving the detail panel, the capabilities tab,
// the close button, and the export / view-users actions. The page is read-only
// by design (no fabricated mutation), so there is no toggle to revert.

const PAGE = "/fr/admin/roles-acces";

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
  await expect(page.getByTestId("roles-table").locator("tbody tr").first()).toBeVisible();
});

test("lists the enforced roles from the real RBAC model", async ({ page }) => {
  const rows = page.getByTestId("roles-table").locator("tbody tr");
  await expect(rows).toHaveCount(3);
  await expect(rows.getByText("Administrateur")).toBeVisible();
  await expect(rows.getByText("Auditeur (lecture)")).toBeVisible();
  await expect(rows.getByText("Super-admin")).toBeVisible();
});

test("search filters the roles client-side", async ({ page }) => {
  const rows = page.getByTestId("roles-table").locator("tbody tr");
  await page.getByPlaceholder(/Rechercher un r/).fill("auditeur");
  await expect(rows).toHaveCount(1);
  await expect(rows.getByText("Auditeur (lecture)")).toBeVisible();
});

test("the Type select filters privileged vs read-only", async ({ page }) => {
  const rows = page.getByTestId("roles-table").locator("tbody tr");
  // metier == "Lecture seule" == the auditor role only.
  await page.getByLabel("Type").selectOption("metier");
  await expect(rows).toHaveCount(1);
  await expect(rows.getByText("Auditeur (lecture)")).toBeVisible();
  // systeme == privileged == admin + superadmin.
  await page.getByLabel("Type").selectOption("systeme");
  await expect(rows).toHaveCount(2);
});

test("row click opens the detail panel and the capabilities tab", async ({ page }) => {
  const detail = page.getByTestId("role-detail");
  await expect(detail.getByText("Sélectionnez un rôle")).toBeVisible();
  await page.getByTestId("roles-table").getByRole("button", { name: "Administrateur" }).click();
  await expect(detail.getByText("Administrateur")).toBeVisible();
  await detail.getByRole("button", { name: "Permissions" }).click();
  await expect(detail.getByText("Cockpit", { exact: true })).toBeVisible();
});

test("the close button clears the selection", async ({ page }) => {
  const detail = page.getByTestId("role-detail");
  await page.getByTestId("roles-table").getByRole("button", { name: "Administrateur" }).click();
  await expect(detail.getByText("Sélectionnez un rôle")).toHaveCount(0);
  await detail.getByRole("button", { name: "Fermer" }).click();
  await expect(detail.getByText("Sélectionnez un rôle")).toBeVisible();
});

test("sortable header reorders the table", async ({ page }) => {
  const rows = page.getByTestId("roles-table").locator("tbody tr");
  await page
    .getByTestId("roles-table")
    .getByRole("button", { name: /Permissions/ })
    .click();
  // ascending by capability count: auditor (2) first.
  await expect(rows.first().getByText("Auditeur (lecture)")).toBeVisible();
});

test("the view-users action links to the users page", async ({ page }) => {
  await page.getByRole("link", { name: "Voir les utilisateurs" }).click();
  await page.waitForURL(/\/admin\/utilisateurs/, { timeout: 15_000 });
  expect(page.url()).toContain("/admin/utilisateurs");
});
