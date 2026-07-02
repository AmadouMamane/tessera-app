import { type Page, expect, test } from "@playwright/test";

// The Curation page shipped with a dead 6-tab bar (static buttons, no activeTab
// state) over one always-rendered overview. This covers the real behaviour: the
// tab bar switches the content, the curate tab works over the FULL real candidate
// queue (curation_store), and a decision taken there lands in the history tab.

const PAGE = "/fr/agir/curation-eval-set";

test.use({ viewport: { width: 1672, height: 1000 } });

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 15_000 });
}

const panel = (page: Page) => page.locator("#curation-tabpanel");

test.beforeEach(async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByRole("tab", { name: "Vue d’ensemble" })).toBeVisible();
});

test("overview is selected by default and is comprehensive", async ({ page }) => {
  await expect(page.getByRole("tab", { name: "Vue d’ensemble" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  // Overview keeps the KPI zone + the priority lots panel.
  await expect(page.getByText("A · État actuel")).toBeVisible();
  await expect(page.getByText("C · Gaps & couverture")).toBeVisible();
});

test("the curate tab lists the full real queue and search filters it", async ({ page }) => {
  await page.getByRole("tab", { name: "À curer" }).click();
  await expect(page.getByRole("tab", { name: "À curer" })).toHaveAttribute("aria-selected", "true");
  // Focused tab drops the overview zones (this proves switching).
  await expect(page.getByText("A · État actuel")).toHaveCount(0);
  const rows = panel(page).locator("tbody tr");
  const total = await rows.count();
  const search = panel(page).getByPlaceholder("Rechercher un cas, un agent…");
  await expect(search).toBeVisible();
  if (total > 0) {
    const firstId = (await rows.first().locator("td").first().innerText()).trim();
    await search.fill(firstId.split(" ")[0] ?? firstId);
    await expect(panel(page).locator("tbody tr").first()).toBeVisible();
    const filtered = await panel(page).locator("tbody tr").count();
    expect(filtered).toBeLessThanOrEqual(total);
    await search.fill("zzz-aucun-candidat-zzz");
    await expect(panel(page).getByText("Aucun candidat dans cet état.")).toBeVisible();
    await search.fill("");
  }
});

test("a decision taken on the curate tab lands in promotions and history", async ({ page }) => {
  // Pick the first real candidate from the API (same order as the curate table),
  // so the durable state can be restored precisely at the end.
  const payload = (await (
    await page.request.get("/api/observability/curation?lang=fr")
  ).json()) as {
    candidate_lots?: { candidate_id: string; id: string; decision: string }[];
  };
  const first = payload.candidate_lots?.[0];
  test.skip(!first, "no real candidates in this environment");
  if (!first) return;
  const caseLabel = first.id.split(" ")[0] ?? first.id;

  try {
    await page.getByRole("tab", { name: "À curer" }).click();
    const firstRow = panel(page).locator("tbody tr").first();
    await firstRow.getByRole("button", { name: "Promouvoir" }).click();
    // The mutation returns the fresh payload; the row badge flips to Promouvoir.
    await expect(firstRow.getByText("Promouvoir").first()).toBeVisible();

    await page.getByRole("tab", { name: "Promotions" }).click();
    await expect(panel(page).locator("tbody tr", { hasText: caseLabel }).first()).toBeVisible();

    await page.getByRole("tab", { name: "Historique" }).click();
    await expect(panel(page).getByText("Historique des décisions")).toBeVisible();
    await expect(panel(page).locator("tbody tr", { hasText: caseLabel }).first()).toBeVisible();
  } finally {
    // Leave the durable store as found.
    await page.request.post("/api/observability/curation/decision", {
      data: { candidate_id: first.candidate_id, decision: first.decision, lang: "fr" },
    });
  }
});

test("coverage tab shows the distribution donut only", async ({ page }) => {
  await page.getByRole("tab", { name: "Couverture & gaps" }).click();
  await expect(panel(page).getByText("C · Gaps & couverture")).toBeVisible();
  // The curate queue and the governance zone are not rendered on this tab.
  await expect(page.getByText("D · Actions & gouvernance")).toHaveCount(0);
});
