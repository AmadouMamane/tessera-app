import { type Page, expect, test } from "@playwright/test";

// Covers the editable agent-profile form: the Save button is gated on a dirty
// edit, a changed select persists across a reload (durable override store), and
// the test restores the default so it leaves the profile clean.

const PAGE = "/fr/agent/configurations";

test.use({ viewport: { width: 1672, height: 1000 } });

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 15_000 });
}

const save = (page: Page) =>
  page.getByRole("button", { name: "Enregistrer les modifications" });

test.beforeEach(async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByLabel("Ton")).toBeVisible();
});

test("save is disabled until an edit makes the form dirty", async ({ page }) => {
  await expect(save(page)).toBeDisabled();
  await page.getByLabel("Ton").selectOption("Amical");
  await expect(save(page)).toBeEnabled();
});

test("a behaviour edit persists across a reload, then restores", async ({ page }) => {
  // Change the tone and persist it.
  await page.getByLabel("Ton").selectOption("Amical");
  await save(page).click();
  await expect(save(page)).toBeDisabled(); // back to clean after success

  // Reload: the durable override is reflected by the backend.
  await page.reload();
  await expect(page.getByLabel("Ton")).toHaveValue("Amical");

  // Restore the default so the test leaves the profile clean.
  await page.getByLabel("Ton").selectOption("Professionnel");
  await save(page).click();
  await expect(save(page)).toBeDisabled();
  await page.reload();
  await expect(page.getByLabel("Ton")).toHaveValue("Professionnel");
});

test("the identity selects (language, owner) are operable and dirty the form", async ({ page }) => {
  const lang = page.getByLabel("Langue par défaut");
  await expect(lang).toBeVisible();
  await lang.selectOption("Anglais");
  await expect(lang).toHaveValue("Anglais");
  await expect(save(page)).toBeEnabled();
  const owner = page.getByLabel("Propriétaire");
  await owner.selectOption("Équipe Produit");
  await expect(owner).toHaveValue("Équipe Produit");
  // Identifiant has a real copy button (not a decorative icon).
  await expect(page.getByRole("button", { name: "Copier l'identifiant" })).toBeVisible();
  await page.getByRole("button", { name: "Annuler" }).click();
});

test("the archive button toggles the durable status badge", async ({ page }) => {
  const status = page.locator("section", { hasText: "Statut de l'agent" });
  await expect(status.getByText("Actif", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Archiver cet agent" }).click();
  await expect(status.getByText("Archivé", { exact: true }).first()).toBeVisible();
  // Persisted: reload still shows archived, then restore so the profile is clean.
  await page.reload();
  await expect(status.getByText("Archivé", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Désarchiver cet agent" }).click();
  await expect(status.getByText("Actif", { exact: true }).first()).toBeVisible();
});

test("the change history is real (file mtimes / console saves, no invented author)", async ({
  page,
}) => {
  const panel = page.locator("section", { hasText: "Historique des modifications" });
  await expect(panel).toBeVisible();
  // Real source events, not the old fabricated "Tessera Ops" author.
  await expect(panel.getByText(/mis à jour/).first()).toBeVisible();
  await expect(panel.getByText("Tessera Ops")).toHaveCount(0);
});

test("the overflow menu offers a real config export", async ({ page }) => {
  await page.getByRole("button", { name: "..." }).click();
  await expect(
    page.getByRole("menuitem", { name: "Exporter la configuration (JSON)" }),
  ).toBeVisible();
  await expect(page.getByRole("menuitem", { name: "Paramètres avancés" })).toBeVisible();
});

test("the parallel-tools toggle flips and enables save", async ({ page }) => {
  const toggle = page.getByRole("switch", { name: "Exécution parallèle d'outils" });
  await expect(toggle).toHaveAttribute("aria-checked", "true");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-checked", "false");
  await expect(save(page)).toBeEnabled();
  // Cancel the pending edit (no persistence) to leave the profile clean.
  await page.getByRole("button", { name: "Annuler" }).click();
  await expect(toggle).toHaveAttribute("aria-checked", "true");
});
