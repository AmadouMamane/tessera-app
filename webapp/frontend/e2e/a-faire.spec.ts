import { type Page, expect, test } from "@playwright/test";

// Covers the "A faire" queue backed by the real operator backlog: the table
// lists real items, the rail search filters them, a row click drives the detail
// drawer, and "Prendre en charge" persists the durable workflow status.
//
// ADR 0038 — this page serves the EVAL/governance half of the backlog only;
// the business half (validations, blocked actions) belongs to /a-traiter.
//
// Repaired 2026-07-10 against the contract `8f3447d9` ("per-agent scope
// end-to-end + ADR 0015 telemetry spine") actually shipped: that commit
// paginated the table at ten rows and turned the inline detail `<section>` into
// a `<dialog aria-modal>` drawer. The specs still asserted the pre-refonte UI —
// more than ten rows, and a `section` filtered on "Detail selectionne" that
// matches nothing, which is why two of them hung for their full 30 s rather
// than failing on the thing they meant to check. The button labels
// ("Prendre en charge", "Marquer resolu") and the mutation route
// (`/observability/agent-a-faire/item-state`) were never touched.

const PAGE = "/fr/a-faire";

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

test("lists real backlog items, one page at a time", async ({ page }) => {
  // Ten is the page size (`agent-a-faire.tsx`, `useState(10)`), not the backlog size. The
  // backlog's real size is what the summary reports; asserting "more than one page" keeps
  // the claim true as the seeded corpus grows or shrinks.
  expect(await page.locator("table tbody tr").count()).toBe(10);

  const summary = page.getByText(/Afficher 1 - 10 sur \d+/);
  await expect(summary).toBeVisible();
  const total = Number(((await summary.textContent()) ?? "").match(/sur (\d+)/)?.[1]);
  expect(total).toBeGreaterThan(10);
});

test("every row is eval-nature — the business half never leaks in (ADR 0038)", async ({ page }) => {
  // Business items all carry source "Métier"; before the partition they sat in
  // this very table (a "Métier" row on page 1 turned this red). An eval row's
  // source is a governance domain (Garde-fous, Confidentialite, RAG, …).
  const rows = page.locator("table tbody tr");
  expect(await rows.count()).toBeGreaterThan(0);
  await expect(rows.filter({ hasText: "Métier" })).toHaveCount(0);
});

test("rail search filters the task list", async ({ page }) => {
  const before = await page.locator("table tbody tr").count();
  await page.getByPlaceholder(/Rechercher dans la liste/).fill("IBAN");
  const after = await page.locator("table tbody tr").count();
  expect(after).toBeLessThan(before);
});

test("row click drives the detail drawer", async ({ page }) => {
  const secondRow = page.locator("table tbody tr").nth(1);
  const title = (await secondRow.locator("td").nth(2).textContent())?.trim() ?? "";
  await secondRow.click();
  const detail = page.getByRole("dialog");
  await expect(detail.getByText(title, { exact: false }).first()).toBeVisible();
});

test("the SLA clock is real: not every row is overdue (ADR 0039)", async ({ page }) => {
  // Pre-0039 the SLA was anchored on the eval-run date (weeks old), so EVERY
  // row read "En retard" — red carried no signal. Anchored on queue-entry, a
  // freshly-seen backlog shows real countdowns. At least one row is not overdue.
  const slaCells = page.locator("table tbody tr td:nth-child(6)");
  const n = await slaCells.count();
  expect(n).toBeGreaterThan(0);
  const texts = await slaCells.allTextContents();
  expect(texts.some((s) => !/retard/i.test(s))).toBe(true);
});

test("the drawer shows the honest dual timestamp: in-queue vs case date (ADR 0039)", async ({
  page,
}) => {
  await page.locator("table tbody tr").first().click();
  const detail = page.getByRole("dialog");
  // Both facts, named and distinct: the SLA clock and the case's own provenance.
  await expect(detail.getByText("En file depuis")).toBeVisible();
  await expect(detail.getByText("Cas date du")).toBeVisible();
  await expect(detail.getByText("Attente en file")).toBeVisible();
});

test("'Prendre en charge' persists the workflow status", async ({ page }) => {
  // Select the first row, then take charge.
  await page.locator("table tbody tr").first().click();
  const detail = page.getByRole("dialog");
  await detail.getByRole("button", { name: "Prendre en charge" }).click();
  // The detail's status reads "En cours" after the mutation.
  await expect(detail.getByText("En cours").first()).toBeVisible();

  // Reload: the durable status survives (first row badge shows En cours).
  await page.reload();
  await expect(page.locator("table tbody tr").first()).toContainText("En cours");

  // Restore: mark resolved is also durable; leave a known clean-ish state.
  // Since WF-01 the selection lives in the URL (?item=), so the reload has
  // ALREADY reopened the drawer on the same case — use it directly.
  const reopened = page.getByRole("dialog");
  await reopened.getByRole("button", { name: "Marquer resolu" }).click();
  await expect(reopened.getByText("Resolu").first()).toBeVisible();
});

// ── lot 2: the FilterStrip really filters, the drawer tabs are real ──────────

test("the priority filter narrows the rows to the picked value, reset restores", async ({
  page,
}) => {
  const total = await page.locator("table tbody tr").count();
  const strip = page.locator("section", {
    has: page.getByPlaceholder(/Rechercher dans la liste/),
  });
  // The strip dropdown, not the sortable column header of the same name.
  await strip.getByRole("button", { name: /^Priorite/ }).click();
  const items = page.getByRole("menuitem");
  const label = ((await items.nth(1).textContent()) ?? "").replace("•", "").trim();
  await items.nth(1).click();
  const rows = page.locator("table tbody tr");
  const n = await rows.count();
  expect(n).toBeGreaterThan(0);
  for (let i = 0; i < n; i++) {
    await expect(rows.nth(i).locator("td").first()).toHaveText(label);
  }
  await page.getByRole("button", { name: "Réinitialiser" }).click();
  expect(await page.locator("table tbody tr").count()).toBe(total);
});

test("saved views apply their preset and expose pressed state", async ({ page }) => {
  const urgent = page.getByRole("button", { name: "Urgents", exact: true });
  await expect(urgent).toHaveAttribute("aria-pressed", "false");
  await urgent.click();
  await expect(urgent).toHaveAttribute("aria-pressed", "true");
  // Urgent is the single-priority preset: every visible badge carries ONE label.
  const badges = await page.locator("table tbody tr td:first-child").allTextContents();
  expect(new Set(badges.map((b) => b.trim())).size).toBeLessThanOrEqual(1);
  const all = page.getByRole("button", { name: "Tous les cas" });
  await all.click();
  await expect(all).toHaveAttribute("aria-pressed", "true");
});

test("the drawer tabs gate real content: history note, evidence link, honest relations", async ({
  page,
}) => {
  await page.locator("table tbody tr").first().click();
  const detail = page.getByRole("dialog");
  await detail.getByRole("button", { name: "Historique" }).click();
  // WF-01: the tab shows the journaled transitions (title always present;
  // rows or the honest per-case empty note below it).
  await expect(detail.getByText("Transitions journalisees")).toBeVisible();
  await detail.getByRole("button", { name: "Preuves" }).click();
  await expect(detail.getByRole("link", { name: /Ouvrir dans les evaluations/ })).toHaveAttribute(
    "href",
    "/fr/surveiller/qualite-ia",
  );
  await detail.getByRole("button", { name: "Relations" }).click();
  await expect(detail.getByText("Aucune relation capturée pour cet élément.")).toBeVisible();
  await detail.getByRole("button", { name: "Contexte" }).click();
  await expect(detail.getByText("Resume")).toBeVisible();
});

test("quick actions: real CSV export, real evaluations link, row-bound actions say so", async ({
  page,
}) => {
  const dl = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exporter la liste" }).click();
  expect((await dl).suggestedFilename()).toBe("tessera-a-faire.csv");
  await expect(page.getByRole("link", { name: "Ouvrir les evaluations" })).toHaveAttribute(
    "href",
    "/fr/surveiller/qualite-ia",
  );
  // With no row selected, per-item actions are disabled and say why.
  const take = page.getByRole("button", { name: "Prendre en charge" });
  await expect(take).toBeDisabled();
  await expect(take.locator("xpath=ancestor-or-self::*[@title]").first()).toHaveAttribute(
    "title",
    /panneau de détail/,
  );
});

test("rail bulk is honestly disabled and the dead timeline CTA is gone", async ({ page }) => {
  const bulk = page.getByRole("button", { name: "Actions groupees" });
  await expect(bulk).toBeDisabled();
  await expect(bulk.locator("xpath=ancestor-or-self::*[@title]").first()).toHaveAttribute(
    "title",
    "Non câblé — cette action arrive dans un lot dédié",
  );
  await expect(page.getByRole("button", { name: "Voir la timeline complete" })).toHaveCount(0);
});

// ── WF-01: the case transitions journal is real, attributed, URL-derived ─────

test("the selected case lives in the URL and deep-links back to its drawer", async ({ page }) => {
  await page.locator("table tbody tr").first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page).toHaveURL(/item=/);
  const url = page.url();
  // A fresh load of the same URL reopens the same case — the selection is the
  // URL's, never a local state's (rail norm).
  await page.goto(url);
  await expect(page.getByRole("dialog")).toBeVisible({ timeout: 20_000 });
});

test("a transition lands in the Historique tab with its author — no more 'not journaled'", async ({
  page,
}) => {
  await page.locator("table tbody tr").first().click();
  const detail = page.getByRole("dialog");
  // Drive both lifecycle buttons: whatever the durable starting status, at
  // least one of the two is an effective transition and must be journaled.
  await detail.getByRole("button", { name: "Prendre en charge" }).click();
  await expect(detail.getByText("En cours").first()).toBeVisible({ timeout: 15_000 });
  await detail.getByRole("button", { name: "Marquer resolu" }).click();
  await expect(detail.getByText("Resolu").first()).toBeVisible({ timeout: 15_000 });
  await detail.getByRole("button", { name: "Historique" }).click();
  // A real journaled row: "<from> -> <to>" naming its verified author.
  await expect(detail.getByText(/-> (En cours|Resolu)/).first()).toBeVisible();
  await expect(detail.getByText("Transitions journalisees")).toBeVisible();
  // The old honest-gap note is gone — transitions ARE journaled now.
  await expect(detail.getByText(/ne sont pas journalisées/)).toHaveCount(0);
});
