import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { type Page, expect, test } from "@playwright/test";

// ADR 0030 — the governed serving-model panel on /configurer/modeles: the closed
// registry (org + one row per fleet agent), superadmin-only set/revert with a
// mandatory reason, visible provenance (author, date, reason, base), and the
// Paramètres page attributing the override to its real author.
//
// SAFETY: every override this suite writes uses THE BASE VALUE ITSELF, so the
// shared Postgres behind the preview AND reference backends never serves a
// different model because of a test — the observable is the provenance, not a
// behaviour flip. Each test reverts what it set; per Insight 173 a red assert
// can still leave the (base-valued) override stored — the panel keeps it
// visible and revertable, and serving is unaffected.

const PAGE = "/fr/configurer/modeles";

test.use({ viewport: { width: 1672, height: 1000 } });

/** The superadmin account exists only when this env var is set — read it from the
 *  same file the dev server loads, so the spec and the server cannot disagree. */
function superadminPassword(): string {
  const env = readFileSync(resolve(__dirname, "..", ".env.local"), "utf8");
  const password = env.match(/^TESSERA_AUTH_SUPERADMIN_PASSWORD=(.+)$/m)?.[1]?.trim();
  if (!password) {
    throw new Error("TESSERA_AUTH_SUPERADMIN_PASSWORD missing from webapp/frontend/.env.local");
  }
  return password;
}

async function login(page: Page, username: string, password: string) {
  await page.goto("/fr/login");
  await page.fill("#login-username", username);
  await page.fill("#login-password", password);
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 15_000 });
}

const panel = (page: Page) => page.locator('[data-testid="serving-models"]');
const row = (page: Page, label: string | RegExp) =>
  panel(page).locator("li").filter({ hasText: label });

test("the registry panel renders org + per-agent rows; non-superadmin gets honest disabled controls", async ({
  page,
}) => {
  await login(page, "admin", "tessera-admin");
  await page.goto(PAGE);
  await expect(panel(page)).toBeVisible({ timeout: 20_000 });
  // The org knob and at least one per-agent knob, enumerated server-side.
  const orgRow = row(page, "Organisation (défaut flotte)");
  await expect(orgRow).toHaveCount(1);
  await expect(row(page, "recouvrement")).toHaveCount(1);
  // An admin is not a superadmin: the affordance is disabled and says why.
  const change = orgRow.getByRole("button", { name: "Modifier" });
  await expect(change).toBeDisabled();
  await expect(change.locator("xpath=ancestor-or-self::*[@title]").first()).toHaveAttribute(
    "title",
    "Réservé au superadmin",
  );
});

test("superadmin sets the org override (base-valued): provenance + journal author, then reverts", async ({
  page,
}) => {
  await login(page, "superadmin", superadminPassword());
  await page.goto(PAGE);
  const orgRow = row(page, "Organisation (défaut flotte)");
  await expect(orgRow).toBeVisible({ timeout: 20_000 });

  // Set: keep the preselected value (= the current effective = the base), so the
  // shared runtime never serves differently; the reason is mandatory.
  await orgRow.getByRole("button", { name: "Modifier" }).click();
  const apply = orgRow.getByRole("button", { name: "Appliquer" });
  await expect(apply).toBeDisabled(); // blank reason ⇒ nothing to submit
  await orgRow.getByLabel("Raison").fill("e2e ADR 0030 — dérogation org (valeur = base)");
  await apply.click();
  await expect(orgRow.getByText("dérogation", { exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(orgRow.getByText(/par superadmin/)).toBeVisible();
  await expect(orgRow.getByText(/base :/)).toBeVisible();

  // The Paramètres page attributes the override to its real author — the only
  // rows on that page with a person, not "config (git)".
  await page.goto("/fr/configurer/parametres");
  const paramRow = page.locator("tbody tr").filter({ hasText: "llm.chat_model" }).first();
  await expect(paramRow).toBeVisible({ timeout: 20_000 });
  await expect(paramRow).toContainText("superadmin");
  await expect(paramRow).toContainText("Dérogation");

  // Revert: a governed act too — reason mandatory, base serves again.
  await page.goto(PAGE);
  const orgRow2 = row(page, "Organisation (défaut flotte)");
  await orgRow2.getByRole("button", { name: "Revenir à la base" }).click({ timeout: 15_000 });
  await orgRow2.getByLabel("Raison").fill("e2e ADR 0030 — retour à la base");
  await orgRow2.getByRole("button", { name: "Confirmer le retour" }).click();
  await expect(orgRow2.getByText("dérogation", { exact: true })).toHaveCount(0, {
    timeout: 15_000,
  });
  await expect(orgRow2.getByText(/par superadmin/)).toHaveCount(0);
});

test("superadmin sets and reverts a per-agent override (recouvrement, base-valued)", async ({
  page,
}) => {
  await login(page, "superadmin", superadminPassword());
  await page.goto(PAGE);
  const agentRow = row(page, "recouvrement");
  await expect(agentRow).toBeVisible({ timeout: 20_000 });

  await agentRow.getByRole("button", { name: "Modifier" }).click();
  await agentRow.getByLabel("Raison").fill("e2e ADR 0030 — dérogation agent (valeur = base)");
  await agentRow.getByRole("button", { name: "Appliquer" }).click();
  await expect(agentRow.getByText("dérogation", { exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(agentRow.getByText(/par superadmin/)).toBeVisible();

  await agentRow.getByRole("button", { name: "Revenir à la base" }).click();
  await agentRow.getByLabel("Raison").fill("e2e ADR 0030 — retour à la base");
  await agentRow.getByRole("button", { name: "Confirmer le retour" }).click();
  await expect(agentRow.getByText("dérogation", { exact: true })).toHaveCount(0, {
    timeout: 15_000,
  });
});

test("the budget knobs are real: honest bases, governed set+revert, closed overrun select (ADR 0034)", async ({
  page,
}) => {
  await login(page, "superadmin", superadminPassword());
  await page.goto(PAGE);
  const budgetRow = row(page, "Plafond budget (€/jour)");
  await expect(budgetRow).toBeVisible({ timeout: 20_000 });
  // The catalogue KPIs carry the day's real spend and the ceiling state.
  await expect(page.getByText("Dépense du jour")).toBeVisible();
  await expect(page.getByText("Plafond quotidien")).toBeVisible();

  // SAFETY: a huge ceiling is behaviour-neutral on this stack — the dev base
  // model is zero-cost and the breaker gates PAID models only (ADR 0034); the
  // observable is the provenance, and the revert restores "no ceiling".
  await budgetRow.getByRole("button", { name: "Modifier" }).click();
  await budgetRow.getByLabel("Plafond budget (€/jour)").fill("9999.5");
  await budgetRow
    .getByLabel("Raison")
    .fill("e2e ADR 0034 — plafond neutre (base gratuite jamais gatée)");
  await budgetRow.getByRole("button", { name: "Appliquer" }).click();
  await expect(budgetRow.getByText("dérogation", { exact: true })).toBeVisible({
    timeout: 15_000,
  });
  await expect(budgetRow.getByText(/par superadmin/)).toBeVisible();

  await budgetRow.getByRole("button", { name: "Revenir à la base" }).click();
  await budgetRow.getByLabel("Raison").fill("e2e ADR 0034 — retrait du plafond");
  await budgetRow.getByRole("button", { name: "Confirmer le retour" }).click();
  await expect(budgetRow.getByText("dérogation", { exact: true })).toHaveCount(0, {
    timeout: 15_000,
  });

  // The overrun knob edits through a CLOSED select of the declared behaviours —
  // never free text.
  const overrunRow = row(page, "Dépassement budget (comportement)");
  await expect(overrunRow).toBeVisible();
  await overrunRow.getByRole("button", { name: "Modifier" }).click();
  const select = overrunRow.getByLabel("Dépassement budget (comportement)");
  await expect(select.locator("option")).toHaveCount(2);
  await overrunRow.getByRole("button", { name: "Annuler" }).click();
});
