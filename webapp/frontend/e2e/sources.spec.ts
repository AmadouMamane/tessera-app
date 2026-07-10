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
  // Show all rows by default so count-based assertions are page-independent; the
  // dedicated pagination test resets this to verify the default-10 behaviour.
  await page.getByLabel("Lignes par page").selectOption("50");
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

// The detail is a click-to-open drawer, not a persistent panel: no row is selected by
// default (`sources-overview.tsx:151`) and closing unmounts the drawer entirely (`:296`,
// `:303`). Its absence IS the empty state — the "Sélectionnez une source" placeholder is a
// dead message key, rendered nowhere.
test("row click drives the tab-gated detail", async ({ page }) => {
  await expect(page.getByTestId("source-detail")).toHaveCount(0);
  await page
    .getByTestId("sources-table")
    .getByRole("button", { name: "Mémoire long terme" })
    .click();
  const detail = page.getByTestId("source-detail");
  await expect(detail.getByText("Mémoire long terme").first()).toBeVisible();
  await detail.getByRole("button", { name: "Contenu" }).click();
  await expect(detail.getByText("Sujets distincts")).toBeVisible();
  await detail.getByRole("button", { name: "Gouvernance" }).click();
  await expect(detail.getByText("Rétention")).toBeVisible();
});

test("the close button clears the selection", async ({ page }) => {
  await page
    .getByTestId("sources-table")
    .getByRole("button", { name: "Mémoire long terme" })
    .click();
  const detail = page.getByTestId("source-detail");
  await expect(detail).toBeVisible();
  await detail.getByRole("button", { name: "Fermer" }).click();
  await expect(page.getByTestId("source-detail")).toHaveCount(0);
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

test("the used-by column surfaces the consuming products", async ({ page }) => {
  const table = page.getByTestId("sources-table");
  // DORA is bound only by Support Client; the shared memory store is infra (all).
  const dora = table.locator("tbody tr", { hasText: "DORA - Résilience" });
  await expect(dora.getByText("Support Client")).toBeVisible();
  const mem = table.locator("tbody tr", { hasText: "Mémoire long terme" });
  await expect(mem.getByText(/Infra partagée/)).toBeVisible();
});

test("the product scope filter narrows the catalogue", async ({ page }) => {
  const rows = page.getByTestId("sources-table").locator("tbody tr");
  await expect(rows).toHaveCount(17);
  // Select the Onboarding product (global ?agent= scope). The control is labelled
  // "Agents :" (`agent-scope-filter.tsx:73`); it has never been called "Filtre".
  await page.getByRole("button", { name: /Agents/ }).click();
  await page.getByRole("menuitem", { name: "Onboarding" }).click();
  // DORA (Support Client only) drops out; the shared memory store stays (infra).
  await expect(
    page.getByTestId("sources-table").locator("tbody tr", { hasText: "DORA" }),
  ).toHaveCount(0);
  await expect(
    page.getByTestId("sources-table").locator("tbody tr", { hasText: "Mémoire long terme" }),
  ).toHaveCount(1);
  await expect(rows).not.toHaveCount(17);
});

test("the used-by drawer shows consumer verdicts", async ({ page }) => {
  await page
    .getByTestId("sources-table")
    .getByRole("button", { name: "DORA - Résilience opérationnelle" })
    .click();
  const detail = page.getByTestId("source-detail");
  // "Utilisé par" lives behind the governance tab (`sources-overview.tsx:1787`), not on the
  // overview the drawer opens on.
  await detail.getByRole("button", { name: "Gouvernance" }).click();
  await expect(detail.getByText("Utilisé par")).toBeVisible();
  await expect(detail.getByText("Support Client")).toBeVisible();
});

test("the normative tab strip switches to real lens views", async ({ page }) => {
  await expect(page.getByTestId("sources-tabs")).toBeVisible();
  // Indexation tab -> the real embeddings facts (bge-m3 / cosine).
  await page.getByRole("button", { name: /Indexation/ }).click();
  await expect(page.getByText("bge-m3").first()).toBeVisible();
  await expect(page.getByText("cosine").first()).toBeVisible();
  // Memory tab -> the table is scoped to the two shared stores.
  await page.getByRole("button", { name: /^Mémoire$/ }).click();
  await expect(page.getByTestId("sources-table").locator("tbody tr")).toHaveCount(2);
  // Access tab -> the per-product access view.
  await page.getByRole("button", { name: /Accès/ }).click();
  await expect(page.getByText(/Quels produits/)).toBeVisible();
});

test("the detail panel shows real metric tiles and tags", async ({ page }) => {
  const detail = page.getByTestId("source-detail");
  await page
    .getByTestId("sources-table")
    .getByRole("button", { name: "DORA - Résilience opérationnelle" })
    .click();
  await expect(detail.getByText("Chunks").first()).toBeVisible();
  await expect(detail.getByText("Réglementation")).toBeVisible(); // type tag
});

test("the history tab plots real memory growth, corpus stays provenance", async ({ page }) => {
  await page.getByRole("button", { name: /Historique/ }).click();
  // Real per-day growth chart for the two memory stores. The heading is
  // "Croissance / Volume (par jour)" (`sources-overview.tsx:1080`).
  await expect(page.getByText(/Croissance/)).toBeVisible();
  await expect(page.getByText("Mémoire long terme")).toBeVisible();
  // Corpus has no time axis -> shown under a provenance heading with last-indexed.
  await expect(page.getByText(/provenance Git/)).toBeVisible();
  await expect(page.getByText(/snapshots versionnés/)).toBeVisible();
});

test("the overview shows the real activity area chart and citation panel", async ({ page }) => {
  await expect(page.getByRole("heading", { name: /Activité mémoire/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Citation par source" })).toBeVisible();
});

test("the detail panel shows the real citation ring and facts", async ({ page }) => {
  await page
    .getByTestId("sources-table")
    .getByRole("button", { name: "DORA - Résilience opérationnelle" })
    .click();
  const detail = page.getByTestId("source-detail");
  await expect(detail.getByText("DORA - Résilience opérationnelle").first()).toBeVisible();
  await expect(detail.getByText("Citation").first()).toBeVisible(); // ring caption
  await expect(detail.getByText("Requêtes")).toBeVisible(); // hits fact
});

test("the as-of control links to the point-in-time page (no invented Suggestions)", async ({
  page,
}) => {
  // The non-normative "Suggestions" panel must not exist.
  await expect(page.getByRole("heading", { name: "Suggestions" })).toHaveCount(0);
  await page
    .getByRole("link", { name: /Voir à date/ })
    .first()
    .click();
  await page.waitForURL(/\/prouver\/etat-a-date/, { timeout: 15_000 });
  expect(page.url()).toContain("/prouver/etat-a-date");
});

// REMOVED 2026-07-10 — "the footer shows the real source-to-answer lineage and audit chain".
// `319dc566` ("refactor(sources): drop the global lineage footer, link to Prouver instead")
// deleted the LineageFooter outright: the footer now renders only its source line, and
// `data.lineage` / `data.audit` are consumed by nothing. Per-query lineage moved to Prouver
// and the Console. There is no surviving surface to point this test at — a whole-page
// lineage heading, "76 documents", "238 chunks - bge-m3" and "Chaîne d'audit" no longer
// render anywhere on this page. The backend still emits the fields; that is an orphan to
// prune in the payload, not a contract to re-assert here.

test("the table paginates by default", async ({ page }) => {
  const rows = page.getByTestId("sources-table").locator("tbody tr");
  await page.getByLabel("Lignes par page").selectOption("10");
  await expect(rows).toHaveCount(10);
  // "Afficher {start} - {end} sur {total}" — spaces around the dash.
  await expect(page.getByText(/1 - 10 sur 17/)).toBeVisible();
  await page.getByLabel("Suivant").click();
  await expect(rows).toHaveCount(7); // 17 - 10
});

test("the recent-activity feed shows sources & memory lifecycle (not agent turns)", async ({
  page,
}) => {
  await expect(page.getByRole("heading", { name: "Activité récente" })).toBeVisible();
  // Real store-lifecycle events (corpus indexing / memory / transcript writes),
  // not the agent's reasoning turns.
  await expect(
    page.getByText(/Corpus indexé|Souvenir mémorisé|Transcription enrichie/).first(),
  ).toBeVisible();
});

// REMOVED 2026-07-10 — "the detail has Acces rapide and Actions with real links (read-only)".
// `385c7920` ("refactor(sources): drop the generic nav block from the detail drawer") deleted
// the whole block: it rendered the same links for every source, so it said nothing about the
// source you had opened. "Accès rapide", "Actions", the "versionnée dans Git" note and the
// "Gérer les permissions" link render nowhere today, and their message keys are orphaned.

// REMOVED 2026-07-10 — "the knowledge action links to the Connaissances page".
// The drawer link went with the same nav block (`385c7920` deletes
// `KNOWLEDGE_HREF = "/agent/connaissances"` and `t("detail.viewKnowledge")`), and the
// command-bar variant went with `408ea25d` ("refactor(sources): keep only substrate-native
// command-bar actions"). No "Voir les connaissances" link exists on this page. The route it
// pointed at is itself pre-multi-agent: `/agent/connaissances` survives only as a compat
// redirect to `/agents/support-client/connaissances`.
