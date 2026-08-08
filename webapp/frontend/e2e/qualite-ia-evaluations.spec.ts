import { type Page, expect, test } from "@playwright/test";

/**
 * The evaluations view of Qualité IA — a screen that had **no e2e at all**.
 *
 * Six specs touched this page and every one of them stayed on the monitoring view; not one ever
 * appended `?vue=evaluations`. The half of the page carrying the non-regression verdicts — the
 * decomposition, the case matrix, the model comparison — was covered by unit tests over pure
 * functions and by nothing that ever loaded it.
 *
 * That gap cost a crash on 2026-08-07, and the shape of it is why this file exists: the launch
 * verdict ribbon was added as an async Server Component and handed `AlertRibbon` (a Client
 * Component) an `icon` FUNCTION. Types agreed on both sides, `tsc` was silent, biome was silent,
 * 790 unit tests were green, the gate was twice-green — and every request rendered "This view
 * could not be displayed". Only loading the page can see that class of fault, so loading the
 * page is now a committed test.
 *
 * Assertions are written as an `or` between a real reading and an honest refusal wherever the
 * data depends on which stack is up. What none of them tolerate is a blank view or a screen that
 * renders reassurance it cannot support.
 */

const SIGNALS = "/fr/surveiller/qualite-ia";
const EVALUATIONS = "/fr/surveiller/qualite-ia?vue=evaluations";

test.use({ viewport: { width: 1672, height: 1000 } });

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 15_000 });
}

/** The error boundary's own words. If this is on screen, the view did not render at all. */
const CRASHED = /Cette vue n'a pas pu s'afficher|This view could not be displayed/;

test("both views render — neither falls into the error boundary", async ({ page }) => {
  await login(page);

  for (const url of [SIGNALS, EVALUATIONS]) {
    await page.goto(url);
    await expect(page.getByText(CRASHED)).toHaveCount(0);
    // The switch is the page's own furniture: present on both, so its absence means the shell
    // rendered and the content did not.
    await expect(page.getByRole("link", { name: /Suivi continu/ })).toBeVisible();
  }
});

test("the launch verdict leads BOTH views, and names its subject", async ({ page }) => {
  await login(page);

  for (const url of [SIGNALS, EVALUATIONS]) {
    await page.goto(url);
    // One of the six sentences the band can hold: cleared, cleared-with-pending, one of the four
    // causes, or the honest "cannot say". Never a bare colour.
    const verdict = page.getByText(
      /peuvent être mis en ligne|peut être mis en ligne|Mise en ligne refusée|On ne peut pas savoir si|Impossible de dire si un agent/,
    );
    await expect(verdict.first()).toBeVisible();
    // It says WHAT it judged. Without this the reader cannot tell it apart from the catalogue
    // verdicts further down, which is the confusion this ribbon was built to end.
    await expect(page.getByText(/verdict par agent/).first()).toBeVisible();
  }
});

test("the header states the two instants: sampled, then judged", async ({ page }) => {
  await login(page);
  await page.goto(EVALUATIONS);

  // A run is sampled on one date and its verdicts are decided on another — 24 days apart on the
  // committed sweep. The header measured only the first and called it freshness.
  await expect(page.getByText(/échantillonné le \d{4}-\d{2}-\d{2}/).first()).toBeVisible();
  const judged = page.getByText(/re-jugé le \d{4}-\d{2}-\d{2} sous le barème/);
  const neverRejudged = page.getByText(/jugé à l'exécution, jamais re-jugé depuis/);
  await expect(judged.or(neverRejudged).first()).toBeVisible();
});

test("no score is published as a bare rate — the floor and the contribution travel with it", async ({
  page,
}) => {
  await login(page);
  await page.goto(EVALUATIONS);

  // Case-INSENSITIVE on purpose: the label is uppercased by CSS and the DOM keeps the
  // catalogue's lowercase text, so an uppercase selector silently matches nothing.
  const decomposed = page.getByText(/absolu — ce n'est pas la note/i);
  const honestEmpty = page.getByText(/aucun sweep lisible|Aucun modèle n'a parlé/);
  await expect(decomposed.or(honestEmpty).first()).toBeVisible();

  if ((await decomposed.count()) > 0) {
    // The two terms an absolute rate hides, both named beside it.
    await expect(page.getByText(/plancher du garde/).first()).toBeVisible();
    await expect(page.getByText(/contribution/).first()).toBeVisible();
  }
});

test("the floor is READ, and every surface quotes the same number", async ({ page }) => {
  await login(page);
  await page.goto(EVALUATIONS);

  // The header interpolates the committed floor. Whatever it reads, the catalogue-power warning
  // must quote THAT number — the page used to serve a measured 124 and a hardcoded 122 three
  // blocks apart, and only a reader comparing them could tell.
  const header = page.getByText(/plancher lu dans la baseline commitée : (\d+)\/(\d+)/);
  const honestEmpty = page.getByText(/aucun sweep lisible|Aucun modèle n'a parlé/);

  // WAIT before deciding. `count()` does not auto-wait, so the previous version asked "is the
  // sentence there?" of a page that had not finished rendering, got 0, and SKIPPED — green,
  // silent, and wrong: the served stack prints "124/174" and this test never once read it.
  // A skip is a claim that the stack has no committed floor; it may only be made after looking.
  await expect(header.or(honestEmpty).first()).toBeVisible({ timeout: 30_000 });
  if ((await header.count()) === 0) test.skip(true, "no committed floor on this stack");

  const text = (await header.first().textContent()) ?? "";
  const [, passed, total] = /(\d+)\/(\d+)/.exec(text) ?? [];
  expect(passed).toBeTruthy();

  const warning = page.getByText(/passe déjà \d+ des \d+ runs/);
  if ((await warning.count()) > 0) {
    await expect(warning.first()).toContainText(`${passed} des ${total} runs`);
  }
});

test("the case set is a versioned artefact with no result on it", async ({ page }) => {
  await login(page);
  await page.goto(`${EVALUATIONS}&tab=cases`);

  await expect(page.getByText(CRASHED)).toHaveCount(0);
  await expect(page.getByRole("heading", { name: /Le jeu de cas/ })).toBeVisible();
  // The bench states its own holes, and the floor percentage in that sentence is measured, not
  // typed: it must agree with a real number rather than the "70 %" that was frozen in the
  // message catalogue.
  await expect(page.getByText(/C'est la raison du plancher à \d+ %/).first()).toBeVisible();
});

test("the comparison ranks nothing and shows what the two models disagree on", async ({ page }) => {
  await login(page);
  await page.goto(`${EVALUATIONS}&tab=compare`);

  await expect(page.getByText(CRASHED)).toHaveCount(0);
  const disagreements = page.getByText(/désaccords?/);
  const locked = page.getByText(/opérateur/);
  await expect(disagreements.or(locked).first()).toBeVisible();
});

/**
 * The four surfaces that crossed from the monitoring dashboard.
 *
 * They render CLIENT-side, which is exactly why an HTTP check cannot stand in for this one: all
 * four return 200 with a byte-identical shell, because their content does not exist until the
 * browser has run React Query. A server that answers is not a panel that draws.
 */
const CROSSED = [
  { tab: "archive", marker: /Runs d'évaluation|Datasets de qualité/ },
  { tab: "failed", marker: /Récurrents|Exporter sélection/ },
  { tab: "models", marker: /Comparaison détaillée des modèles/ },
  { tab: "judge", marker: /Matrice de confusion|Diagnostic de calibration/i },
] as const;

for (const { tab, marker } of CROSSED) {
  test(`?tab=${tab} renders on the evaluations view, not on the dashboard`, async ({ page }) => {
    await login(page);
    await page.goto(`${EVALUATIONS}&tab=${tab}`);

    await expect(page.getByText(CRASHED)).toHaveCount(0);
    // The strip RESOLVED this name. `parseTab` falls back to the sweep on anything it does not
    // know, so an unrecognised tab renders a perfectly healthy WRONG page — same URL, no error,
    // different screen. Asserting the tab's own link is the current one is what tells the two
    // apart; counting `aria-current` on the page does not (the sidebar carries one too).
    await expect(page.locator(`a[href*="tab=${tab}"][aria-current="page"]`)).toHaveCount(1);
    // A marker only the PANEL can produce — never the tab label, never the population sentence.
    // The first version of this check looked for "Exécutions passées" and "juge", which the
    // strip and the sentence above the panel both print: it would have gone green on a panel
    // that never drew, which is precisely the failure this file was written to catch. The
    // judge's calibration is computed server-side over a gold set and can take ten seconds on
    // a cold cache, hence the generous timeout — a slow read is not an absent one.
    await expect(page.getByText(marker).first()).toBeVisible({ timeout: 30_000 });
  });
}

test("each crossed surface says which population it is reading", async ({ page }) => {
  await login(page);

  // The whole reason the move needed care: the sweep scores llama3.2:3b at 92 % and the archive
  // at 51.7 %. Both are true of different runs. A tab that shows one of those numbers without
  // naming its population turns an honest difference into a contradiction.
  for (const { tab } of CROSSED) {
    await page.goto(`${EVALUATIONS}&tab=${tab}`);
    await expect(page.getByText(/séance|archive|jeu de référence|annoté/i).first()).toBeVisible({
      timeout: 20_000,
    });
  }
});

test("the strip groups its seven tabs by the population each one reads", async ({ page }) => {
  await login(page);
  await page.goto(EVALUATIONS);

  for (const caption of [/Une même séance/, /L'archive/, /Le juge/]) {
    await expect(page.getByText(caption).first()).toBeVisible();
  }
});

test("the departed tabs are gone from the monitoring strip, and its links follow them", async ({
  page,
}) => {
  await login(page);
  await page.goto(SIGNALS);

  // Two tabs left, not six. A strip still offering "Cas échoués" here would render an empty
  // panel: the queries behind it moved.
  await expect(page.getByRole("tab").or(page.locator("[data-tab-key]"))).not.toHaveCount(6);

  // …and the overview's own drill-down must land on the content, wherever it now lives.
  //
  // EXACT, and unguarded, for two reasons this test learned the hard way. `/Comparer/` also
  // matches "Comparer à Objectif cible" in the temporal rail, which sits earlier in the DOM:
  // `.first()` clicked a dropdown and waited fifteen seconds for a navigation nobody had asked
  // for. And the `if (count > 0)` that used to wrap this made a missing button a silent pass —
  // the one outcome that must never read as green, since a drill-down that disappeared is
  // exactly the regression this assertion exists to catch.
  const compare = page.getByRole("button", { name: "Comparer modèles", exact: true });
  await expect(compare).toHaveCount(1);
  await compare.click();
  await page.waitForURL(/vue=evaluations/, { timeout: 15_000 });
  await expect(page).toHaveURL(/tab=models/);
  await expect(page.getByText(CRASHED)).toHaveCount(0);
  // It arrived at the CONTENT, not merely at the URL.
  await expect(page.getByText(/Comparaison détaillée des modèles/).first()).toBeVisible({
    timeout: 30_000,
  });
});
