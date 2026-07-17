import { type Page, expect, test } from "@playwright/test";

// Cockpit FE sweep, lot 1b (agir + a-traiter): dead rail/zone buttons become
// Links with a real target, in-page tab switches, or client exports that
// download — and what has no target yet is honestly disabled (title
// common.notWired) or simply absent. Tests assert the wired behaviour or the
// absence of the dead affordance, never mere visibility.

const NOT_WIRED = "Non câblé — cette action arrive dans un lot dédié";

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

test("agir/automations: the rail's viewApprovals quick action switches to the approvals tab", async ({
  page,
}) => {
  await page.goto("/fr/agir/automations");
  await expect(page.getByRole("tab", { name: "Vue d’ensemble" })).toBeVisible({ timeout: 20_000 });
  await page.getByRole("button", { name: "Voir approbations" }).click();
  await expect(page.getByRole("tab", { name: "Approbations" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  // The queue is real since lot 4: honest empty state OR actionable rows.
  const approve = page.locator("#automations-tabpanel").getByRole("button", { name: "Approuver" });
  if ((await approve.count()) === 0) {
    await expect(page.getByText(/Aucune approbation en attente/).first()).toBeVisible();
  } else {
    await expect(approve.first()).toBeEnabled();
  }
});

test("agir/automations: journal quick action is a real link, activate/suspend are real bulk acts", async ({
  page,
}) => {
  await page.goto("/fr/agir/automations");
  await expect(page.getByRole("tab", { name: "Vue d’ensemble" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("link", { name: "Ouvrir journal" })).toHaveAttribute(
    "href",
    "/fr/prouver/audit-logs",
  );
  // Lot 4 wired them to the governed rules-state endpoint: enabled, real buttons
  // (the bulk round-trip itself is covered by automations.spec.ts).
  for (const name of ["Activer toutes les règles", "Suspendre toutes les règles"]) {
    await expect(page.getByRole("button", { name, exact: true }).first()).toBeEnabled();
  }
});

test("agir/curation: view-alls link to their real targets and activities switches to history", async ({
  page,
}) => {
  await page.goto("/fr/agir/curation-eval-set");
  await expect(page.getByRole("tab", { name: "Vue d’ensemble" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("link", { name: "Voir tous les candidats" })).toHaveAttribute(
    "href",
    "/fr/surveiller/qualite-ia",
  );
  const packLinks = page.getByRole("link", { name: "Générer dossier de preuves" });
  await expect(packLinks.first()).toHaveAttribute("href", "/fr/prouver/evidence-store");
  for (const name of ["Filtrer par sensibilité", "Ouvrir catalogue de signaux"]) {
    await expect(page.getByRole("button", { name, exact: true }).first()).toBeDisabled();
  }
  await page.getByRole("button", { name: "Voir toutes les activités" }).click();
  await expect(page.getByRole("tab", { name: "Historique" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
});

test("agir/incidents: the export button downloads the live payload as JSON", async ({ page }) => {
  await page.goto("/fr/agir/incidents-playbooks");
  const exportBtn = page.getByRole("button", { name: "Exporter les incidents (JSON)" });
  await expect(exportBtn).toBeVisible({ timeout: 20_000 });
  const dl = page.waitForEvent("download");
  await exportBtn.click();
  expect((await dl).suggestedFilename()).toBe("tessera-incidents.json");
});

test("agir/incidents: catalogue view-all switches tab; create/launch honestly disabled", async ({
  page,
}) => {
  await page.goto("/fr/agir/incidents-playbooks");
  await expect(page.getByRole("button", { name: "Voir tout le catalogue" })).toBeVisible({
    timeout: 20_000,
  });
  for (const name of ["Créer ticket", "Lancer procédure"]) {
    await expect(page.getByRole("button", { name, exact: true }).first()).toBeDisabled();
  }
  const triage = page.getByRole("link", { name: "Voir tout", exact: true });
  await expect(triage.first()).toHaveAttribute("href", "/fr/a-traiter");
  await page.getByRole("button", { name: "Voir tout le catalogue" }).click();
  // Non-overview incident tabs are flagged demonstration fixtures.
  await expect(page.getByText(/démonstration/i).first()).toBeVisible();
});

test("agir/replay: overview view-alls switch to their tab, which then carries none", async ({
  page,
}) => {
  await page.goto("/fr/agir/replay-shadow");
  await expect(page.getByRole("tab", { name: "Vue d’ensemble" })).toBeVisible({ timeout: 20_000 });
  await page.getByRole("button", { name: "Voir tout", exact: true }).click();
  await expect(page.getByRole("tab", { name: "Sessions rejouées" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  // On the sessions tab the panel has no view-all target — the helper renders nothing.
  await expect(
    page.locator("#replay-tabpanel").getByRole("button", { name: "Voir tout", exact: true }),
  ).toHaveCount(0);
});

test("agir/replay: quick actions — real export, real journal link, the rest honestly disabled", async ({
  page,
}) => {
  await page.goto("/fr/agir/replay-shadow");
  await expect(page.getByRole("tab", { name: "Vue d’ensemble" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("link", { name: "Voir le journal de rejeu" })).toHaveAttribute(
    "href",
    "/fr/prouver/audit-logs",
  );
  for (const name of ["Rejouer une session", "Créer une référence", "Programmer un rejeu"]) {
    const btn = page.getByRole("button", { name, exact: true });
    await expect(btn).toBeDisabled();
    await expect(btn.locator("xpath=ancestor-or-self::*[@title]").first()).toHaveAttribute(
      "title",
      NOT_WIRED,
    );
  }
  const dl = page.waitForEvent("download");
  await page.getByRole("button", { name: "Exporter les résultats", exact: true }).click();
  expect((await dl).suggestedFilename()).toBe("tessera-replay.json");
});

test("agir/replay: the compare rail is honestly disabled until the replay run lands", async ({
  page,
}) => {
  await page.goto("/fr/agir/replay-shadow");
  await expect(page.getByRole("tab", { name: "Vue d’ensemble" })).toBeVisible({ timeout: 20_000 });
  const rail = page.locator("aside").filter({ hasText: "Comparer à une référence" });
  for (const sel of await rail.locator("select").all()) {
    await expect(sel).toBeDisabled();
  }
  await expect(rail.getByRole("button", { name: "Relire maintenant" })).toBeDisabled();
  await expect(rail.getByRole("link", { name: "Voir tout le journal" })).toHaveAttribute(
    "href",
    "/fr/prouver/audit-logs",
  );
});

test("a-traiter: replay/bulk rail actions honestly disabled, panel view-alls gone", async ({
  page,
}) => {
  await page.goto("/fr/a-traiter");
  await expect(page.locator("table tbody tr").first()).toBeVisible({ timeout: 20_000 });
  for (const name of ["Relire file à T", "Actions groupées"]) {
    const btn = page.getByRole("button", { name, exact: true });
    await expect(btn).toBeDisabled();
    await expect(btn.locator("xpath=ancestor-or-self::*[@title]").first()).toHaveAttribute(
      "title",
      NOT_WIRED,
    );
  }
  // ByType/Sla view-alls had no target anywhere — they must be absent, not dead.
  for (const name of ["Voir le détail", "Voir les SLA"]) {
    await expect(page.getByRole("button", { name, exact: true })).toHaveCount(0);
  }
});
