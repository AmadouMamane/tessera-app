import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { type Locator, type Page, expect, test } from "@playwright/test";

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

/**
 * The error boundary's own words. If this is on screen, the view did not render at all.
 *
 * READ FROM THE CATALOGUE, NEVER RETYPED — and that is the whole lesson of 2026-08-15.
 *
 * This constant used to be a hand-written literal: `/Cette vue n'a pas pu s'afficher|This view
 * could not be displayed/`. The catalogue says *"Cette vue n’a pas pu **être affichée**"* — a
 * different verb, and a typographic apostrophe `’` where the literal had an ASCII `'`. Two
 * mismatches, either one fatal. Since every URL in this file is a `/fr/` one, the French
 * alternative was the only one that could ever fire, and it could not: the six
 * `expect(getByText(CRASHED)).toHaveCount(0)` assertions below were asking a healthy page and a
 * dead one the same unanswerable question, and getting `0` from both.
 *
 * So the Comparaison tab rendered nothing but the error boundary for a day while the file
 * written to catch exactly that — see the docstring at the top — stayed green. A witness that
 * cannot see may never report "ok" (ADR 0026); the way to make sure this one can is to give it
 * no string of its own to get wrong.
 */
const ERROR_TITLES = (["fr", "de", "en"] as const).map((locale) => {
  const catalogue = JSON.parse(
    readFileSync(resolve(__dirname, "..", "messages", `${locale}.json`), "utf8"),
  );
  const title: unknown = catalogue?.errorBoundary?.title;
  // A missing key would silently build `//`, which matches every page and would turn all six
  // assertions from vacuously true into permanently false. Fail here instead, naming the key.
  if (typeof title !== "string" || title.length < 10) {
    throw new Error(`messages/${locale}.json has no usable errorBoundary.title (got ${title})`);
  }
  return title;
});
const CRASHED = new RegExp(
  ERROR_TITLES.map((s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|"),
);

test("the crash detector can see a crash — the positive control", () => {
  // Cheap, and it is the assertion whose absence cost a day: the detector must match the very
  // sentence the boundary renders, in the language these tests browse in.
  for (const title of ERROR_TITLES) expect(CRASHED.test(title)).toBe(true);
  expect(CRASHED.test("Le jeu de cas · 63 cas")).toBe(false);
});

/**
 * The view DREW — proven the only way absence can be proven: by waiting for a presence first.
 *
 * `expect(getByText(CRASHED)).toHaveCount(0)` is a web-first assertion, so it retries until the
 * count MATCHES — and it matches on the first try, because zero is what an empty page has. It
 * therefore never waits for the failure it is looking for. That is not theory: run this file
 * against the stack that was serving the broken Comparaison tab and the boundary check passes,
 * then the marker below times out thirty seconds later with the boundary's own heading sitting
 * in the snapshot. `app/[locale]/error.tsx` is a CLIENT component; on a server-render failure
 * Next streams the shell and React paints the boundary only after hydration, which is strictly
 * later than the moment the old order asked its question.
 *
 * So: wait for something the working view alone can produce, THEN check the boundary is absent.
 * In that order the second assertion is about a settled page and finally means something.
 */
async function expectDrawn(page: Page, marker: Locator, timeout = 30_000) {
  await expect(marker.first()).toBeVisible({ timeout });
  await expect(page.getByText(CRASHED)).toHaveCount(0);
}

test("both views render — neither falls into the error boundary", async ({ page }) => {
  await login(page);

  for (const url of [SIGNALS, EVALUATIONS]) {
    await page.goto(url);
    // The switch is the page's own furniture: present on both, so its absence means the shell
    // rendered and the content did not.
    await expectDrawn(page, page.getByRole("link", { name: /Suivi continu/ }));
  }
});

test("the launch verdict leads the evaluations view, and names its subject", async ({ page }) => {
  await login(page);

  // The FULL ribbon lives on the view whose question it answers. It used to lead both views;
  // the operator read that as the monitoring view opening on the other view's headline.
  await page.goto(EVALUATIONS);
  // One of the six sentences the band can hold: cleared, cleared-with-pending, one of the four
  // causes, or the honest "cannot say". Never a bare colour.
  const verdict = page.getByText(
    /peuvent être mis en ligne|peut être mis en ligne|Mise en ligne refusée|On ne peut pas savoir si|Impossible de dire si un agent/,
  );
  await expect(verdict.first()).toBeVisible();
  // It says WHAT it judged. Without this the reader cannot tell it apart from the catalogue
  // verdicts further down, which is the confusion this ribbon was built to end.
  await expect(page.getByText(/verdict par agent/).first()).toBeVisible();
});

test("on the monitoring view the verdict rides the evaluations door — visible, at door size", async ({
  page,
}) => {
  await login(page);
  await page.goto(SIGNALS);

  // The door to the evaluations view carries the one-line verdict (counts, or the honest
  // "unreachable"), so the per-agent PRÊT column keeps its explainer on this view too.
  const door = page.getByRole("link", { name: /Évaluations avant mise en ligne/ });
  await expect(door).toBeVisible();
  await expect(door).toContainText(/peuvent être mis en ligne|bloqué|jamais évalué|injoignable/);
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
  const honestEmpty = page.getByText(/aucun banc d'essai lisible|Aucun modèle n'a parlé/);
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
  const honestEmpty = page.getByText(/aucun banc d'essai lisible|Aucun modèle n'a parlé/);

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

  await expectDrawn(page, page.getByRole("heading", { name: /Le jeu de cas/ }));
  // The bench states its own holes, and the floor percentage in that sentence is measured, not
  // typed: it must agree with a real number rather than the "70 %" that was frozen in the
  // message catalogue.
  await expect(page.getByText(/C'est la raison du plancher à \d+ %/).first()).toBeVisible();
});

test("the comparison ranks nothing and shows what the two models disagree on", async ({ page }) => {
  await login(page);
  await page.goto(`${EVALUATIONS}&tab=compare`);

  // A marker only the PANEL can produce, on both branches. The previous pair was
  // `/désaccords?/ OR /opérateur/`, and the second half is printed by a dozen unrelated strings
  // in this catalogue — the sidebar's role chip among them — so the refusal branch would have
  // gone green on a page that never drew the comparison at all.
  const compared = page.getByRole("heading", { name: /Le coût réel/ });
  const locked = page.getByText(/Accès opérateur requis/);
  await expectDrawn(page, compared.or(locked));
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

    // A marker only the PANEL can produce — never the tab label, never the population sentence.
    // The first version of this check looked for "Exécutions passées" and "juge", which the
    // strip and the sentence above the panel both print: it would have gone green on a panel
    // that never drew, which is precisely the failure this file was written to catch. The
    // judge's calibration is computed server-side over a gold set and can take ten seconds on
    // a cold cache, hence the generous timeout — a slow read is not an absent one.
    await expectDrawn(page, page.getByText(marker));
    // The strip RESOLVED this name. `parseTab` falls back to the sweep on anything it does not
    // know, so an unrecognised tab renders a perfectly healthy WRONG page — same URL, no error,
    // different screen. Asserting the tab's own link is the current one is what tells the two
    // apart; counting `aria-current` on the page does not (the sidebar carries one too).
    await expect(page.locator(`a[href*="tab=${tab}"][aria-current="page"]`)).toHaveCount(1);
  });
}

test("each crossed surface says which population it is reading", async ({ page }) => {
  await login(page);

  // The whole reason the move needed care: the sweep scores llama3.2:3b at 92 % and the archive
  // at 51.7 %. Both are true of different runs. A tab that shows one of those numbers without
  // naming its population turns an honest difference into a contradiction.
  for (const { tab } of CROSSED) {
    await page.goto(`${EVALUATIONS}&tab=${tab}`);
    await expect(
      page.getByText(/banc d'essai|archive|jeu de référence|annoté/i).first(),
    ).toBeVisible({
      timeout: 20_000,
    });
  }
});

test("the strip groups its seven tabs by the population each one reads", async ({ page }) => {
  await login(page);
  await page.goto(EVALUATIONS);

  for (const caption of [/Le banc d'essai/, /L'archive/, /Le juge/]) {
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
  // The toolbar's "Comparer modèles" button used to carry this check; it left the monitoring
  // view with the rest of the eval-shaped controls (operator feedback, 2026-08-12), so the
  // surviving cross-boundary control is the case-set link. EXACT, and unguarded: the
  // `if (count > 0)` that once wrapped this made a missing control a silent pass — the one
  // outcome that must never read as green, since a drill-down that disappeared is exactly the
  // regression this assertion exists to catch.
  const openCases = page.getByRole("link", { name: "Jeu de cas — vue Évaluations", exact: true });
  await expect(openCases).toHaveCount(1);
  await openCases.click();
  await page.waitForURL(/vue=evaluations/, { timeout: 15_000 });
  await expect(page).toHaveURL(/tab=cases/);
  // It arrived at the CONTENT, not merely at the URL.
  await expectDrawn(page, page.getByRole("heading", { name: /Le jeu de cas/ }));
});

test("the rating band names its methods — or names its blind spot — and carries no rate", async ({
  page,
}) => {
  await login(page);
  await page.goto(SIGNALS);

  // The rating-methods zone (ADR 0017 §Amendment 4) — since 2026-08-25 a house-mould Zone
  // in the dashboard's overview tab, below the temporal sequence (operator feedback: the
  // free-standing band broke the hero→rail reading order). Loading the page is the only
  // witness for its RSC/client seam (the 2026-08-07 lesson above), and the served content
  // must land in one of exactly two states: a real reading naming at least one method, or
  // the named failed-read line. A blank zone — the skeleton that never resolves — is the
  // one outcome this assertion refuses.
  const band = page.locator('section[aria-label="Méthodes de notation"]');
  await expect(band).toBeVisible();
  await expect(
    band
      .getByText(/Réponses envoyées — notées par un juge IA/)
      .or(band.getByText(/Impossible de lire qui est noté comment/)),
  ).toBeVisible({ timeout: 15_000 });

  // Two rulers never share a denominator, on the SERVED page too: whatever the band shows,
  // it is counts — the hero above owns the page's only percentage.
  const text = (await band.textContent()) ?? "";
  expect(text).not.toMatch(/%/);
  expect(text).not.toMatch(/barème|population|régime/i);
});
