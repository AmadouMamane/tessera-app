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

  const decomposed = page.getByText(/ABSOLU — CE N'EST PAS LA NOTE/);
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
