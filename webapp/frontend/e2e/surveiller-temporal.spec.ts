import { type Page, expect, test } from "@playwright/test";

// SR-01 · the SURVEILLER temporal command bar (Vue d'ensemble). Covers the four
// human readings (Maintenant / À un instant sans & avec date / Historique), the
// honest empty state, the single "Revenir au direct", the removal of the video-
// player transport, and the URL deep-link contract. The reading is deep-linked
// (?lecture=…&expanded=1) so each state renders deterministically; the as-of date
// is set via the URL and drives only UI state (badges/banner), independent of data.

const PAGE = "/fr/surveiller/vue-ensemble";
const ASOF = "2026-06-26T12:00:00Z";

test.use({ viewport: { width: 1536, height: 1100 } });

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 20_000 });
}

/** The single SR-01 command-bar section (the one carrying "Comparer à"). */
function bar(page: Page) {
  return page.locator("section").filter({ hasText: "Comparer à" }).first();
}

async function open(page: Page, query: string) {
  await page.goto(`${PAGE}${query}`);
  await expect(bar(page)).toBeVisible();
  await expect(page.getByText("Fenêtre d’observation").first()).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await login(page);
});

test("page header carries the export actions, the bar does not", async ({ page }) => {
  await open(page, "?expanded=1");
  // Export / evidence live in the page header (registre §2) — not in the temporal bar.
  await expect(page.getByRole("button", { name: "Exporter rapport" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Générer le dossier de preuves" })).toBeVisible();
  await expect(bar(page).getByText("Exporter rapport")).toHaveCount(0);
  await expect(bar(page).getByText("Générer le dossier de preuves")).toHaveCount(0);
});

test("no technical title and no permanent pedagogical line", async ({ page }) => {
  await open(page, "?expanded=1");
  await expect(page.getByText("Navigation temporelle des signaux")).toHaveCount(0);
  // The mode definitions live in the Lecture menu, not a permanent rail line.
  await expect(page.getByText("État à un instant T ·")).toHaveCount(0);
});

test("Maintenant: real-time header, no return button, no player transport", async ({ page }) => {
  await open(page, "?expanded=1");
  await expect(bar(page).getByText("Données en temps réel").first()).toBeVisible();
  await expect(page.getByText("Revenir au direct")).toHaveCount(0);
  await expect(page.getByText("Revenir au présent")).toHaveCount(0);
  // The video-player cassette is gone (start / play / latest); only event nav remains.
  await expect(page.locator('[aria-label="Début"]')).toHaveCount(0);
  await expect(page.locator('[aria-label="Le plus récent"]')).toHaveCount(0);
  await expect(page.locator('[aria-label="Événement précédent"]').first()).toBeVisible();
  await expect(page.locator('[aria-label="Événement suivant"]').first()).toBeVisible();
});

test("À un instant without a date: honest empty state, no score, no PROUVER", async ({ page }) => {
  await open(page, "?lecture=asOf&expanded=1");
  await expect(bar(page).getByText("Instant non sélectionné").first()).toBeVisible();
  await expect(
    page.getByText("Choisissez un instant pour reconstituer les signaux observés.").first(),
  ).toBeVisible();
  await expect(bar(page).getByText("État live")).toHaveCount(0);
  await expect(bar(page).getByText("État à l’instant")).toHaveCount(0);
  await expect(bar(page).getByText("vs référence")).toHaveCount(0);
  await expect(page.getByText("Ouvrir dans PROUVER · État à date")).toHaveCount(0);
  await expect(page.getByText("Revenir au direct")).toHaveCount(0);
  // No instant yet → "Aller à un instant" (never the stale "Modifier l'instant").
  await expect(page.getByText("Aller à un instant").first()).toBeVisible();
  await expect(page.getByText("Modifier l’instant")).toHaveCount(0);
});

test("À un instant without a date: 'Comparer à' is disabled, never a phantom default", async ({
  page,
}) => {
  await open(page, "?lecture=asOf&expanded=1");
  // No interactive "Comparer à" select while awaiting an instant.
  await expect(bar(page).locator("select")).toHaveCount(0);
});

test("À un instant with a date: present-actions banner, PROUVER link, one return", async ({
  page,
}) => {
  await open(page, `?lecture=asOf&asof=${encodeURIComponent(ASOF)}&compare=now&expanded=1`);
  await expect(bar(page).getByText("À un instant").first()).toBeVisible();
  await expect(page.getByText("Les actions restent appliquées au présent.").first()).toBeVisible();
  // PROUVER in caps, matching the nav plane.
  await expect(page.getByText("Ouvrir dans PROUVER · État à date")).toBeVisible();
  await expect(page.getByText("Revenir au direct")).toHaveCount(1);
  await expect(page.getByText("Revenir au présent")).toHaveCount(0);
  // "Comparer à" defaults to "Maintenant" with an instant, never "Aucun".
  await expect(
    bar(page)
      .getByText(/Comparer à[\s\S]{0,40}Maintenant/)
      .first(),
  ).toBeVisible();
  // The date control reads "Modifier l'instant" once an instant is set.
  await expect(page.getByText("Modifier l’instant").first()).toBeVisible();
  await expect(page.getByText("Aller à un instant")).toHaveCount(0);
  // The selected instant is labelled on the timeline (case-insensitive: uppercased
  // via CSS) so it is obvious which marker is the active T.
  await expect(
    bar(page)
      .getByText(/instant sélectionné/i)
      .first(),
  ).toBeVisible();
});

test("Historique: period framing, never a live snapshot, no player", async ({ page }) => {
  await open(page, "?lecture=history&expanded=1");
  await expect(bar(page).getByText("Historique").first()).toBeVisible();
  await expect(bar(page).getByText("État live")).toHaveCount(0);
  await expect(bar(page).getByText("Sur la période").first()).toBeVisible();
  await expect(page.getByText("Revenir au présent")).toHaveCount(0);
  await expect(page.locator('[aria-label="Le plus récent"]')).toHaveCount(0);
});

test("deep-link reconstructs the reading and keeps its params", async ({ page }) => {
  await open(page, `?lecture=asOf&asof=${encodeURIComponent(ASOF)}&compare=now&expanded=1`);
  // The reading is reconstructed from the URL and the URL keeps the as-of instant.
  await expect(bar(page).getByText("À un instant").first()).toBeVisible();
  expect(page.url()).toContain("asof=");
  await page.reload();
  await page.waitForLoadState("networkidle").catch(() => {});
  // The reading re-hydrates from the URL after a one-frame "live" flash, so allow
  // a longer settle here than the default expect timeout.
  await expect(bar(page).getByText("À un instant").first()).toBeVisible({ timeout: 15_000 });
  expect(page.url()).toContain("asof=");
});

test("no 'As-of' façade label anywhere in the bar", async ({ page }) => {
  await open(page, `?lecture=asOf&asof=${encodeURIComponent(ASOF)}&expanded=1`);
  await expect(bar(page).getByText(/As-of/i)).toHaveCount(0);
});

test("selecting an event via the arrows shows its full timestamp", async ({ page }) => {
  await open(page, "?lecture=history&expanded=1");
  // A selected instant must carry its date/time: never a bare "État à l'instant".
  await page.locator('[aria-label="Événement précédent"]').first().click();
  // Badge reads "État au {date} {HH:MM}" (locale-independent time check) — never a
  // metric without a clear instant (registre §2/§4).
  await expect(
    bar(page)
      .getByText(/État au .*\d{2}:\d{2}/)
      .first(),
  ).toBeVisible();
  await expect(bar(page).getByText("Événement sélectionné").first()).toBeVisible();
  await expect(bar(page).getByText("État à l’instant")).toHaveCount(0);
  // Selecting an event must NOT silently switch the reading to a replay: Lecture
  // stays Historique.
  await expect(bar(page).getByText("Historique").first()).toBeVisible();
});

test("the replay cassette stays on XT-01 (AGIR/Replay), not on SURVEILLER", async ({ page }) => {
  // SURVEILLER (SR-01): event navigation, never a video-player cassette.
  await open(page, "?lecture=history&expanded=1");
  await expect(page.locator('[aria-label="Événement suivant"]').first()).toBeVisible();
  await expect(page.locator('[aria-label="Début"]')).toHaveCount(0);
  await expect(page.locator('[aria-label="Le plus récent"]')).toHaveCount(0);

  // AGIR / Replay (XT-01): the legitimate cassette is present.
  await page.goto("/fr/agir/replay-shadow");
  const voir = page.getByRole("button", { name: /Voir l.historique/ }).first();
  if (await voir.count()) await voir.click();
  await expect(page.locator('[aria-label="Début"]').first()).toBeVisible({ timeout: 15_000 });
  await expect(page.locator('[aria-label="Suivant"]').first()).toBeVisible();
  // …and the signal event-nav is NOT used there.
  await expect(page.locator('[aria-label="Événement suivant"]')).toHaveCount(0);
});
