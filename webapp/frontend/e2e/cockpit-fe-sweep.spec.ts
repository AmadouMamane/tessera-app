import { type Page, expect, test } from "@playwright/test";

// Cockpit-wide FE sweep (lot 1a): previously-dead affordances are now real
// (Links with a target, client exports that download, tab switches, a detail
// panel that closes) or honestly disabled — and the two fabricated values are
// gone (the security "CASE-02xx" refs, the compliance "11/06/2026" date).
// Every test asserts the wired behaviour or the absence of the lie, never
// mere visibility.

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
});

test("configurer/garde-fous: the detail panel really closes, and reopens on row click", async ({
  page,
}) => {
  await page.goto("/fr/configurer/garde-fous");
  const table = page.locator('[data-testid="guardrails-table"]');
  await expect(table.locator("tbody tr").first()).toBeVisible({ timeout: 20_000 });
  const detail = page.locator('[data-testid="guardrail-detail"]');
  await expect(detail).toBeVisible();
  await detail.getByRole("button", { name: "Fermer" }).click();
  await expect(detail).toHaveCount(0);
  await table.locator("tbody tr").first().click();
  await expect(page.locator('[data-testid="guardrail-detail"]')).toBeVisible();
});

test("configurer/garde-fous: status dots derive from the payload status", async ({ page }) => {
  await page.goto("/fr/configurer/garde-fous");
  const rows = page.locator('[data-testid="guardrails-table"] tbody tr');
  await expect(rows.first()).toBeVisible({ timeout: 20_000 });
  // A row whose status label is not the active one must not glow green — the
  // old code hardcoded bg-emerald-400 for every row.
  const n = await rows.count();
  for (let i = 0; i < n; i++) {
    const row = rows.nth(i);
    const text = await row.innerText();
    if (!/Actif|Active/i.test(text)) {
      await expect(row.locator("span.bg-emerald-400")).toHaveCount(0);
    }
  }
});

test("configurer/modeles: the detail panel really closes, and reopens on row click", async ({
  page,
}) => {
  await page.goto("/fr/configurer/modeles");
  const table = page.locator('[data-testid="models-table"]');
  await expect(table.locator("tbody tr").first()).toBeVisible({ timeout: 20_000 });
  const detail = page.locator('[data-testid="model-detail"]');
  await expect(detail).toBeVisible();
  await detail.getByRole("button", { name: "Fermer" }).click();
  await expect(detail).toHaveCount(0);
  await table.locator("tbody tr").first().click();
  await expect(page.locator('[data-testid="model-detail"]')).toBeVisible();
});

test("configurer/parametres: export downloads, no global Save/Import, quick-config switches tabs", async ({
  page,
}) => {
  await page.goto("/fr/configurer/parametres");
  await expect(page.getByRole("tab", { name: "Vue d’ensemble" })).toBeVisible({ timeout: 20_000 });

  // ADR 0030 §5 — this page has no editable field, so the global Save/Import are
  // GONE (not disabled): the governed mutations live where the knobs live
  // (/configurer/modeles). The real export stays.
  await expect(page.getByRole("button", { name: "Enregistrer les modifications" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Importer la configuration" })).toHaveCount(0);

  // Export is a real client-side download of the live payload.
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exporter la configuration" }).click();
  expect((await download).suggestedFilename()).toBe("tessera-parameters.json");

  // "Voir le détail" (config state) jumps to the Système tab.
  await page.getByRole("button", { name: "Voir le détail" }).click();
  await expect(page.locator("#parameters-tabpanel")).toHaveAttribute(
    "aria-labelledby",
    "parameters-tab-system",
  );

  // Back on overview, the per-category "Configurer →" opens that category's tab.
  await page.getByRole("tab", { name: "Vue d’ensemble" }).click();
  await page
    .locator("#parameters-tabpanel")
    .getByRole("button", { name: /Configurer/ })
    .first()
    .click();
  const labelledBy = await page.locator("#parameters-tabpanel").getAttribute("aria-labelledby");
  expect(labelledBy).not.toBe("parameters-tab-overview");
});

test("configurer/politiques: active-policies status dots derive from the payload", async ({
  page,
}) => {
  await page.goto("/fr/configurer/politiques");
  // The dedicated tab renders the active-policies table alone.
  await page.getByRole("tab", { name: "Politiques actives" }).click({ timeout: 20_000 });
  const rows = page.locator("table tbody tr");
  await expect(rows.first()).toBeVisible({ timeout: 20_000 });
  const n = await rows.count();
  for (let i = 0; i < n; i++) {
    const row = rows.nth(i);
    const status = await row.locator("td").last().innerText();
    if (!/Active/i.test(status)) {
      await expect(row.locator("span.bg-emerald-400")).toHaveCount(0);
    }
  }
});

test("surveiller/securite-privacy: no fabricated CASE-02xx, wired rail, honest purge, real export", async ({
  page,
}) => {
  await page.goto("/fr/surveiller/securite-privacy");
  await expect(page.getByRole("tab", { name: "Vue d’ensemble" })).toBeVisible({ timeout: 20_000 });

  // The invented CASE-02xx refs are gone everywhere on the page.
  expect(await page.content()).not.toMatch(/CASE-02\d\d/);

  // Rail quick actions navigate for real…
  await expect(page.getByRole("link", { name: "Ouvrir incident" })).toHaveAttribute(
    "href",
    /\/agir\/incidents-playbooks/,
  );
  await expect(
    page.getByRole("link", { name: "Générer dossier de preuves sécurité" }),
  ).toHaveAttribute("href", /\/prouver\/evidence-store/);
  // …and the one with no endpoint says so instead of pretending.
  await expect(page.getByRole("button", { name: "Purger mémoire GDPR" })).toBeDisabled();

  // The incidents export is a real client-side download.
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exporter les incidents (JSON)" }).click();
  expect((await download).suggestedFilename()).toBe("tessera-security-incidents.json");
});

test("surveiller/conformite: the fabricated date is gone, the report export is real", async ({
  page,
}) => {
  await page.goto("/fr/surveiller/conformite");
  // The conformite TabStrip renders plain buttons (no tab role).
  await expect(page.getByRole("button", { name: /Vue d.ensemble/ }).first()).toBeVisible({
    timeout: 20_000,
  });

  // The hardcoded "11/06/2026" is gone; the card now says the date is not captured.
  expect(await page.content()).not.toContain("11/06/2026");
  await expect(
    page.getByText("Non capturé — le rapport ne porte pas de date d'évaluation"),
  ).toBeVisible();

  await expect(
    page.getByRole("link", { name: "Générer dossier de preuves", exact: true }),
  ).toHaveAttribute("href", /\/prouver\/evidence-store/);
  await expect(page.getByRole("link", { name: "Plan de remédiation" })).toHaveAttribute(
    "href",
    /\/surveiller\/amelioration/,
  );
  // (name-only would collide with the catalogue TAB of the same name — target the
  // disabled rail button via its honest tooltip)
  await expect(page.getByTitle(/aucun registre des traitements/)).toBeDisabled();

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exporter rapport conformité" }).click();
  expect((await download).suggestedFilename()).toBe("tessera-compliance.json");
});

test("surveiller/vue-ensemble: 'view health' is a real link", async ({ page }) => {
  await page.goto("/fr/surveiller/vue-ensemble");
  const link = page.getByRole("link", { name: /Voir les composants santé/ });
  await expect(link).toBeVisible({ timeout: 20_000 });
  await expect(link).toHaveAttribute("href", /\/surveiller\/observabilite/);
});

test("surveiller/qualite-ia (judge): recommended actions link to their homes or are honestly disabled", async ({
  page,
}) => {
  await page.goto("/fr/surveiller/qualite-ia");
  // The quality TabStrip renders plain buttons (no tab role).
  await page
    .getByRole("button", { name: "Calibration juge", exact: true })
    .click({ timeout: 20_000 });
  // The calibration payload loads after the tab switch — give it time.
  await expect(page.getByRole("link", { name: "Ouvrir curation" })).toHaveAttribute(
    "href",
    /\/agir\/curation-eval-set/,
    { timeout: 30_000 },
  );
  await expect(page.getByRole("link", { name: "Lancer la comparaison" })).toHaveAttribute(
    "href",
    /\/agir\/replay-shadow/,
  );
  await expect(page.getByRole("link", { name: "Geler la promotion" })).toHaveAttribute(
    "href",
    /\/agir\/release-control/,
  );
  await expect(page.getByRole("link", { name: "Ouvrir revue" })).toHaveAttribute(
    "href",
    /\/surveiller\/conformite/,
  );
  await expect(page.getByRole("link", { name: "Préparer le pack" })).toHaveAttribute(
    "href",
    /\/prouver\/evidence-store/,
  );
  // Recalibration has no endpoint yet: disabled, with the reason in its tooltip.
  await expect(page.getByRole("button", { name: "Lancer la recalibration" })).toBeDisabled();
});

test("prouver/audit-logs: the decorative Filtres button is gone, real filters remain", async ({
  page,
}) => {
  await page.goto("/fr/prouver/audit-logs");
  await expect(page.getByPlaceholder(/Rechercher/).first()).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Filtres", exact: true })).toHaveCount(0);
});

test("qualite-ia failed board: bulk acts live where their stores live", async ({ page }) => {
  await page.goto("/fr/surveiller/qualite-ia");
  await page
    .getByRole("button", { name: /Cas échoués/ })
    .first()
    .click({ timeout: 20_000 });
  // Real links to the pages that own the acts (per-candidate curation, the
  // operator queue); case creation waits for the real incident store.
  await expect(page.getByRole("link", { name: "Ajouter au dataset" })).toHaveAttribute(
    "href",
    /\/agir\/curation-eval-set/,
    { timeout: 20_000 },
  );
  await expect(page.getByRole("link", { name: "Assigner responsable" })).toHaveAttribute(
    "href",
    /\/a-traiter/,
  );
  const createCase = page.getByRole("button", { name: "Créer case" });
  await expect(createCase).toBeDisabled();
  await expect(createCase.locator("xpath=ancestor-or-self::*[@title]").first()).toHaveAttribute(
    "title",
    /store d'incidents/,
  );
});
