import { type Page, expect, test } from "@playwright/test";

/**
 * The page is called "observabilité" and used to answer "is it running".
 *
 * Those are two questions: health asks *is it alive*, observability asks *can I know what
 * happened*. What follows checks the second one is now on the screen — and, more importantly,
 * that each block refuses to answer when it cannot see. Every assertion below is an `or` between
 * a real reading and an honest empty state, because these run against whatever stack happens to
 * be up: a spec that demanded green numbers would be red on a laptop and green in CI, which
 * teaches nobody anything. What it will NOT tolerate is a block that renders reassurance out of
 * a store it could not reach.
 */

const PAGE = "/fr/surveiller/observabilite";

test.use({ viewport: { width: 1672, height: 1000 } });

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 15_000 });
}

test("the verdict leads the page instead of twenty rows to scan", async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  const observing = page.getByText(/J'observe \d+\/\d+ composants/);
  const unreadable = page.getByText(/Verdict illisible/);
  await expect(observing.or(unreadable).first()).toBeVisible();
});

test("the chain is drawn with its four stages", async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByText("La chaîne d'observabilité", { exact: true })).toBeVisible();
  const stages = page.getByText("Acheminement", { exact: true });
  const unreadable = page.getByText(/la chaîne n'a pas pu être obtenue/);
  await expect(stages.or(unreadable).first()).toBeVisible();
});

test("each store says what its silence costs", async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByText("Ce que chaque magasin porte", { exact: true })).toBeVisible();
  // The row that carries the consequence an operator actually pays for.
  await expect(page.getByText("Preuve de tour (niveau L1)", { exact: true })).toBeVisible();
});

test("availability never appears without the share of the window that was watched", async ({
  page,
}) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByText("Dans le temps", { exact: true })).toBeVisible();
  const observedColumn = page.getByRole("columnheader", { name: "Observé" });
  const nothingRecorded = page.getByText(/Rien d'enregistré sur cette fenêtre/);
  // Either the table is there WITH its observed-share column, or the honest empty state. What
  // must never exist is an availability column standing on its own.
  await expect(observedColumn.or(nothingRecorded).first()).toBeVisible();
});

test("instrumentation coverage names its evidence rather than implying spans", async ({ page }) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByText("Couverture d'instrumentation", { exact: true })).toBeVisible();
  const proxy = page.getByText(/événements métier — pas un magasin de spans/);
  const unreadable = page.getByText(/Magasin muet/);
  const noAgents = page.getByText(/Aucun agent manifesté/);
  await expect(proxy.or(unreadable).or(noAgents).first()).toBeVisible();
});

test("a loopback tool link is shown but not promised from a non-loopback vantage point", async ({
  page,
  baseURL,
}) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByText("Ouvrir les outils", { exact: true })).toBeVisible();

  const grafana = page.getByTitle(/13000/).first();
  const none = page.getByText(/Aucune adresse navigateur configurée/);
  await expect(grafana.or(none).first()).toBeVisible();

  // The property worth pinning: served over loopback, the door opens; served from anywhere
  // else, the address is shown as host-only and is NOT an anchor.
  if ((await grafana.count()) > 0) {
    const servedFromLoopback = /^https?:\/\/(localhost|127\.0\.0\.1)(:|$)/.test(baseURL ?? "");
    const tag = await grafana.evaluate((node) => node.tagName.toLowerCase());
    expect(tag).toBe(servedFromLoopback ? "a" : "span");
  }
});

test("the tail-sampling panel renders real retention or an honest empty state", async ({
  page,
}) => {
  await login(page);
  await page.goto(PAGE);
  await expect(page.getByText("Conservation ciblée des traces", { exact: true })).toBeVisible();
  // Either real counters (buffer has traces) or the honest empty state.
  const counters = page.getByText("Traces vues");
  const empty = page.getByText(/tampon replay est vide/);
  await expect(counters.or(empty).first()).toBeVisible();
});
