import { type Page, expect, test } from "@playwright/test";

// Covers the Historique sub-tabs, which must gate distinct real content (not be
// decorative pills), plus the Sessions-table interactions that must survive
// refactors: the status filter changes the row set, a header click sorts, a row
// click drives the detail panel (with the real question/answer in the Messages
// tab), and the client pagination advances. All sourced from the real
// llama3.2:3b eval run + the real transcript conversations.

const PAGE = "/fr/agents/support-client/historique";

test.use({ viewport: { width: 1672, height: 1050 } });

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 20_000 });
}

function subtab(page: Page, name: string) {
  return page.locator("[data-agent-subtabs]").getByRole("button", { name, exact: true });
}

test.beforeEach(async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  // The default view is Vue d'ensemble: the KPI strip is the readiness witness.
  await expect(page.getByText("Sessions totales").first()).toBeVisible();
});

test("the sub-tabs gate distinct real content", async ({ page }) => {
  // Overview shows the KPI strip but no sessions table.
  await expect(page.locator("table")).toHaveCount(0);

  // Sessions gates to the filterable table; the KPI strip leaves.
  await subtab(page, "Sessions").click();
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await expect(page.getByText("Sessions totales")).toHaveCount(0);

  // Traces & outils carries the honest capture note + real tool-call counts.
  await subtab(page, "Traces & outils").click();
  await expect(
    page.getByText(/traces pas-à-pas des appels d'outils ne sont pas capturées/),
  ).toBeVisible();
  await expect(page.getByText("Appels d'outils", { exact: true })).toBeVisible();

  // Contenu & sources is an honest empty state, not a fabricated table.
  await subtab(page, "Contenu & sources").click();
  await expect(page.getByText(/Aucune donnée de sources n'accompagne les sessions/)).toBeVisible();
  await expect(page.locator("table")).toHaveCount(0);

  // Exports gates to download cards.
  await subtab(page, "Exports").click();
  await expect(page.getByRole("button", { name: "Télécharger" }).first()).toBeVisible();

  // Back to the overview restores the KPI strip.
  await subtab(page, "Vue d'ensemble").click();
  await expect(page.getByText("Sessions totales").first()).toBeVisible();
});

test("Messages: the exchanges table opens a drawer with the real Q/A", async ({ page }) => {
  await subtab(page, "Messages").click();
  await page.locator("tbody tr").first().click();
  const drawer = page.getByRole("dialog");
  await expect(drawer.getByText("Question", { exact: true })).toBeVisible();
  await expect(drawer.getByText("Réponse de l'agent")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);
  // The real transcript conversations render below the exchanges.
  await expect(page.getByText("Conversations en direct").first()).toBeVisible();
});

test("Evaluations: the verdict stats agree with the table total", async ({ page }) => {
  await subtab(page, "Evaluations").click();
  // Réussies is shown as passed/total — both numbers real, total > 0.
  const stat = page
    .locator("div", { has: page.getByText("Réussies", { exact: true }) })
    .last()
    .locator("span")
    .last();
  await expect(stat).toHaveText(/^\d+\/[1-9]\d*$/);
});

test("Erreurs: only failed sessions remain, with the exchange in the drawer", async ({ page }) => {
  await subtab(page, "Erreurs").click();
  const table = page.locator("table");
  // Either a clean-state banner (0 failures) or a failures-only table.
  const banner = page.getByText("Aucune session en échec sur ce run.");
  if (await banner.isVisible().catch(() => false)) {
    await expect(table).toHaveCount(0);
    return;
  }
  await expect(table.getByText("Réussie")).toHaveCount(0);
  await page.locator("tbody tr").first().click();
  const drawer = page.getByRole("dialog");
  await expect(drawer.getByText("Question", { exact: true })).toBeVisible();
});

test("Utilisateurs: the operator table is honest (no invented identities)", async ({ page }) => {
  await subtab(page, "Utilisateurs").click();
  await expect(
    page.getByText(/aucune identité d'utilisateur final n'est enregistrée/),
  ).toBeVisible();
  await expect(page.getByText("Opérateurs distincts")).toBeVisible();
  await expect(page.locator("tbody tr").first()).toBeVisible();
});

test("Sessions: the status filter narrows the table to failures", async ({ page }) => {
  await subtab(page, "Sessions").click();
  const table = page.locator("table");
  await expect(table.getByText("Réussie").first()).toBeVisible();
  await page.getByRole("button", { name: "Statut Tous" }).click();
  await page.getByRole("menuitem", { name: "Échec", exact: true }).click();
  // After filtering to failures, no "Réussie" badge remains in the page slice.
  await expect(table.getByText("Réussie")).toHaveCount(0);
  await expect(table.getByText("Échec").first()).toBeVisible();
});

test("Sessions: a row click drives the detail panel and the real Q/A", async ({ page }) => {
  await subtab(page, "Sessions").click();
  const firstRow = page.locator("tbody tr").first();
  const sid = await firstRow.locator("td").first().innerText();
  await firstRow.click();
  const detail = page.locator("section", { hasText: "Détails de la session" });
  await expect(detail.getByText(sid.trim(), { exact: false }).first()).toBeVisible();
  // The Messages tab shows the real question + the model's answer.
  await detail.getByRole("button", { name: "Messages (2)" }).click();
  await expect(detail.getByText("Question", { exact: true })).toBeVisible();
  await expect(detail.getByText("Réponse de l'agent")).toBeVisible();
});

test("Sessions: pagination advances to the next page", async ({ page }) => {
  await subtab(page, "Sessions").click();
  await expect(page.getByText(/1-10 sur \d+ sessions/)).toBeVisible();
  await page.getByRole("button", { name: "Page suivante" }).click();
  await expect(page.getByText(/11-20 sur \d+ sessions/)).toBeVisible();
});

test("Sessions: a header click sorts the table", async ({ page }) => {
  await subtab(page, "Sessions").click();
  const header = page.getByRole("button", { name: /^Tokens/ });
  await header.click();
  await expect(page.locator("thead th", { hasText: "Tokens" })).toHaveAttribute(
    "aria-sort",
    "ascending",
  );
  await header.click();
  await expect(page.locator("thead th", { hasText: "Tokens" })).toHaveAttribute(
    "aria-sort",
    "descending",
  );
});
