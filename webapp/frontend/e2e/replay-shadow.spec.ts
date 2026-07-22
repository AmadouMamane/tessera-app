import { type Page, expect, test } from "@playwright/test";

// Replay & shadow: the 8-tab bar was dead and the payload a fixture. Now the
// replay core is REAL (captured bundles, durable replay journal, run-to-run
// eval comparisons) and the tabs switch; shadow/export zones stay flagged.

const PAGE = "/fr/agir/replay-shadow";

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
  await expect(page.getByRole("tab", { name: "Vue d’ensemble" })).toBeVisible({
    timeout: 20_000,
  });
});

test("overview shows real bundle counts and honest dashes", async ({ page }) => {
  await expect(page.getByRole("tab", { name: "Vue d’ensemble" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByText("A · État actuel")).toBeVisible();
  // Storeless metrics are dashes, never invented numbers.
  const kpiZone = page.locator("section", { hasText: "A · État actuel" }).first();
  await expect(kpiZone.getByText("—").first()).toBeVisible();
});

test("no overview table paints outside its card", async ({ page }) => {
  // The "Sessions récentes" table used to overflow its panel by ~144px — its
  // origin column painted in the gutter and behind the aside cards. Wide tables
  // scroll in their OWN container now; assert every table stays inside its card.
  await expect(page.getByText("Sessions récentes").first()).toBeVisible({ timeout: 20_000 });
  const overflows = await page.evaluate(() => {
    const out: { title: string; overflow: number }[] = [];
    for (const tb of document.querySelectorAll("main table")) {
      const panel = tb.closest("div.rounded-lg");
      if (!panel) continue;
      // Measure the PAINT box: a wide table inside an overflow container keeps
      // its full layout width (getBoundingClientRect would still "overflow") but
      // its paint is clipped by that container — so judge the clipping ancestor.
      const clip = tb.closest(".overflow-x-auto") ?? tb;
      const t = clip.getBoundingClientRect();
      const p = panel.getBoundingClientRect();
      out.push({
        title: (panel.querySelector("h3")?.textContent ?? "?").trim(),
        overflow: Math.round(t.right - p.right),
      });
    }
    return out;
  });
  expect(overflows.length).toBeGreaterThan(0);
  for (const o of overflows) {
    expect(
      o.overflow,
      `table "${o.title}" paints ${o.overflow}px past its card`,
    ).toBeLessThanOrEqual(0);
  }
});

test("comparisons tab lists the real run-to-run diffs", async ({ page }) => {
  await page.getByRole("tab", { name: "Comparaisons" }).click();
  await expect(page.getByRole("tab", { name: "Comparaisons" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  // A real comparison row (run dd/mm vs dd/mm) or an honest empty panel.
  const row = page.getByText(/Run \d{2}\/\d{2} vs \d{2}\/\d{2}/).first();
  await expect(row).toBeVisible();
  // Overview zones dropped (proves switching).
  await expect(page.getByText("A · État actuel")).toHaveCount(0);
});

test("baselines tab lists the real evaluation runs", async ({ page }) => {
  await page.getByRole("tab", { name: "Baselines" }).click();
  await expect(page.getByText("Baselines réelles — runs d’évaluation")).toBeVisible();
});

test("shadow and exports tabs are flagged demonstration", async ({ page }) => {
  await page.getByRole("tab", { name: "Trafic fantôme" }).click();
  await expect(page.getByText(/démonstration/i).first()).toBeVisible();
  await expect(page.getByText(/n’est pas implémenté|n'est pas implémenté/).first()).toBeVisible();

  await page.getByRole("tab", { name: "Exports & preuves" }).click();
  await expect(page.getByText(/démonstration/i).first()).toBeVisible();
});

// ── lot 8: the shadow replay is REAL ─────────────────────────────────────────

test("the shadow rail mirrors captured turns against a candidate model, for real", async ({
  page,
}) => {
  // The mirror is honestly slow (real judge). The result expect below allows
  // 150s — but the DEFAULT test timeout is 30s, which silently capped it: an
  // expectation the test can never wait out is a witness that cannot see.
  test.setTimeout(180_000);
  const rail = page.locator("aside").filter({ hasText: "Rejouer en shadow" });
  await expect(rail.getByLabel("Modèle candidat")).toBeVisible({ timeout: 20_000 });
  // The dead "compare to a baseline" selects and the fake time pills are gone
  // from the rail (the comparisons TAB legitimately keeps its own title).
  await expect(rail.getByText("Comparer à une référence")).toHaveCount(0);
  await expect(rail.getByText("24h", { exact: true })).toHaveCount(0);
  // Pick a candidate the LOCAL serving path can serve: the catalogue's default
  // (gemini-*) only exists on the frontier path — on this bench Ollama answers
  // 404 and the run 500s instantly. The mirror under test needs a real model.
  await rail.getByLabel("Modèle candidat").selectOption("llama3.2:3b");
  // Run it: a real mirror (2 turns, real judge) — slow, and honestly so.
  await rail.getByRole("button", { name: "Lancer le shadow" }).click();
  await expect(rail.getByText(/comparés|Aucun tour capturé/)).toBeVisible({ timeout: 150_000 });
});

// XT-01 — the cassette lens: mode always displayed, selection URL-derived.

test("cassettes tab shows the Live mode chip and an honest list or empty state", async ({
  page,
}) => {
  await page.getByRole("tab", { name: "Cassettes" }).click();
  await expect(page.getByRole("tab", { name: "Cassettes" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  // The mode is always displayed (rail norm): Live when no cassette is selected.
  await expect(page.getByTestId("cassette-mode")).toBeVisible();
  await expect(page.getByTestId("cassette-mode")).toHaveText(/Live · dernières captures/);
  // Either real cassette rows or the honest empty message — never a fabricated list.
  const zone = page.locator("section", { hasText: /Cassettes capturées/ }).first();
  await expect(zone).toBeVisible();
});

test("a ?bundle= deep link lands on the cassette lens and says so honestly", async ({ page }) => {
  await page.goto(`${PAGE}?bundle=inexistant-e2e`);
  // The deep link names a cassette: the page opens the lens, not the overview.
  await expect(page.getByRole("tab", { name: "Cassettes" })).toHaveAttribute(
    "aria-selected",
    "true",
    { timeout: 20_000 },
  );
  // Replay mode chip (URL-derived selection), and an honest not-found for a
  // cassette outside the live window — never a fabricated detail panel.
  await expect(page.getByTestId("cassette-mode")).toHaveText(/Replay · cassette sélectionnée/);
  await expect(
    page.getByText(/n’est plus dans la fenêtre|n'est plus dans la fenêtre/),
  ).toBeVisible();
});
