import { type Page, expect, test } from "@playwright/test";

// Covers the Sources & memory page (configurer/sources-memoire): the catalogue
// built from the real pgvector corpus + the two memory tables (long_term_memory,
// conversation_messages), controlled search, the Type <select> filter, sortable
// volume header, row-click selection driving the tab-gated detail, close, and the
// knowledge link. Read-only by design (corpus = Git/ingest, memory = agent), so
// no mutation.

const PAGE = "/fr/configurer/sources-memoire";

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
  await expect(page.getByTestId("sources-table").locator("tbody tr").first()).toBeVisible();
});

test("lists the real corpus + memory sources", async ({ page }) => {
  const rows = page.getByTestId("sources-table").locator("tbody tr");
  // 15 corpus categories + long-term memory + transcript = 17.
  await expect(rows).toHaveCount(17);
  await expect(rows.getByText("Mémoire long terme").first()).toBeVisible();
  await expect(rows.getByText("Transcription des conversations").first()).toBeVisible();
});

test("search filters the sources client-side", async ({ page }) => {
  const rows = page.getByTestId("sources-table").locator("tbody tr");
  await page.getByPlaceholder(/Rechercher une source/).fill("mémoire");
  await expect(rows).toHaveCount(1);
  await expect(rows.getByText("Mémoire long terme").first()).toBeVisible();
});

test("the Type select filters by category", async ({ page }) => {
  const rows = page.getByTestId("sources-table").locator("tbody tr");
  // memory == the long-term store only.
  await page.getByLabel("Type").selectOption("memory");
  await expect(rows).toHaveCount(1);
  await page.getByLabel("Type").selectOption("regulation");
  await expect(rows).toHaveCount(4); // dora, gdpr, bafin, cnil
});

test("row click opens the tab-gated detail", async ({ page }) => {
  const detail = page.getByTestId("source-detail");
  await expect(detail.getByText("Sélectionnez une source")).toBeVisible();
  await page
    .getByTestId("sources-table")
    .getByRole("button", { name: "Mémoire long terme" })
    .click();
  await expect(detail.getByText("Mémoire long terme")).toBeVisible();
  await detail.getByRole("button", { name: "Contenu" }).click();
  await expect(detail.getByText("Sujets distincts")).toBeVisible();
  await detail.getByRole("button", { name: "Gouvernance" }).click();
  await expect(detail.getByText("Rétention")).toBeVisible();
});

test("the close button clears the selection", async ({ page }) => {
  const detail = page.getByTestId("source-detail");
  await page
    .getByTestId("sources-table")
    .getByRole("button", { name: "Mémoire long terme" })
    .click();
  await expect(detail.getByText("Sélectionnez une source")).toHaveCount(0);
  await detail.getByRole("button", { name: "Fermer" }).click();
  await expect(detail.getByText("Sélectionnez une source")).toBeVisible();
});

test("sortable volume header reorders the table", async ({ page }) => {
  const rows = page.getByTestId("sources-table").locator("tbody tr");
  await page
    .getByTestId("sources-table")
    .getByRole("button", { name: /Volume/ })
    .click();
  // ascending: the smallest corpus floats to the top (a single-digit chunk count),
  // never the multi-thousand transcript.
  await expect(rows.first().getByText("Transcription des conversations")).toHaveCount(0);
});

test("the knowledge action links to the Connaissances page", async ({ page }) => {
  await page.getByRole("link", { name: "Voir les connaissances" }).click();
  await page.waitForURL(/\/agent\/connaissances/, { timeout: 15_000 });
  expect(page.url()).toContain("/agent/connaissances");
});
