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
  // The expanded panel is mounted (the rail scrubber legend is a stable marker).
  await expect(bar(page).getByText("Qualité :").first()).toBeVisible();
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
  // The "État au" chip IS the single picker — no duplicate bottom button.
  await expect(page.getByRole("button", { name: /État au/ }).first()).toBeVisible();
  await expect(page.getByText("Aller à un instant")).toHaveCount(0);
  await expect(page.getByText("Modifier l’instant")).toHaveCount(0);
});

test("À un instant without a date: 'Comparer à' is disabled, never a phantom default", async ({
  page,
}) => {
  await open(page, "?lecture=asOf&expanded=1");
  // No interactive "Comparer à" select while awaiting an instant; the disabled chip
  // reads "Maintenant" (the natural comparison), never "Aucun".
  await expect(bar(page).locator("select")).toHaveCount(0);
  await expect(
    bar(page)
      .getByText(/Comparer à[\s\S]{0,20}Maintenant/)
      .first(),
  ).toBeVisible();
});

test("the 'État au' chip is the single clickable point-in-time picker", async ({ page }) => {
  await open(page, "?lecture=asOf&expanded=1");
  // Clicking the chip opens the calendar (full pick→URL flow is render-verified
  // separately, since enabled days depend on the data range).
  await page
    .getByRole("button", { name: /État au/ })
    .first()
    .click();
  await expect(page.getByRole("button", { name: "Mois précédent" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Mois suivant" })).toBeVisible();
});

test("page export actions sit in the header, no cheap divider, outside the temporal bar", async ({
  page,
}) => {
  await open(page, "?expanded=1");
  const exportBtn = page.getByRole("button", { name: "Exporter rapport" });
  await expect(exportBtn).toBeVisible();
  // Not inside the SR-01 command bar (registre §2).
  await expect(bar(page).getByText("Exporter rapport")).toHaveCount(0);
  // The actions row carries no full-width top border (the old cheap separator).
  const borderTop = await exportBtn.evaluate(
    (el) => getComputedStyle(el.closest("div") as HTMLElement).borderTopWidth,
  );
  expect(borderTop).toBe("0px");
  // The header itself has no full-width bottom border (§1): structure comes from a
  // short premium accent under the title block instead.
  const headerBorderBottom = await page.evaluate(() => {
    const h = document.querySelector("header");
    return h ? getComputedStyle(h).borderBottomWidth : "no-header";
  });
  expect(headerBorderBottom).toBe("0px");
});

test("À un instant with a date: calm rail header, PROUVER link, one return", async ({ page }) => {
  await open(page, `?lecture=asOf&asof=${encodeURIComponent(ASOF)}&compare=now&expanded=1`);
  await expect(bar(page).getByText("À un instant").first()).toBeVisible();
  // The rail header is calm: short title + ONE micro-line, no eyebrow, no badge,
  // no long banner, no ambiguous "actions appliquées au présent".
  await expect(bar(page).getByText("Signaux observés à l’instant choisi").first()).toBeVisible();
  await expect(bar(page).getByText("Fenêtre d’observation")).toHaveCount(0);
  await expect(page.getByText("actions appliquées au présent")).toHaveCount(0);
  await expect(page.getByText("Vous consultez l’état")).toHaveCount(0);
  // The explanation lives in a hover tooltip, never a permanent line.
  await expect(
    page.getByRole("button", { name: /Cette vue montre les signaux tels qu/ }).first(),
  ).toBeVisible();
  await expect(bar(page).getByText("Cette vue montre les signaux tels qu’ils")).toHaveCount(0);
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
  // Date selection lives ONLY in the "État au" chip — no bottom duplicate button.
  await expect(page.getByRole("button", { name: /État au/ }).first()).toBeVisible();
  await expect(page.getByText("Modifier l’instant")).toHaveCount(0);
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
