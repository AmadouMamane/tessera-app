import { type Page, expect, test } from "@playwright/test";

/**
 * Every number on a page must be reading the same window — measured on the page.
 *
 * On 2026-08-01, the day the period selector first reached the data, Vue d'ensemble rendered
 * this, one above the other:
 *
 *     OBJECTIF DE QUALITÉ  Fidélité — 73,1 % < objectif 95,0 %   · 18 réponses sur 67
 *     Fidélité (objectif de service)   100 %   ≥ 95 %   · 1/1 conformes
 *
 * Neither is wrong. The ribbon read all of history, the table read the selected seven days,
 * and nothing on screen said so. That is the worst shape a disagreement can take: two correct
 * numbers about two different weeks, under one label, with no way to tell.
 *
 * It happened because wiring a dimension is a per-call-site job and the ribbon's call site was
 * missed — its own comment already promised it would "never disagree with the grid below it",
 * about the agent scope, which WAS wired. A unit test cannot catch this: each component is
 * individually correct. Only the assembled page shows it, so this reads the assembled page.
 *
 * The assertion is deliberately narrow — one metric, two renderings of it, same window — and
 * for the same reason it is deliberately REPEATED at two periods: agreement at the default
 * period could be a coincidence of the data, agreement at two different windows cannot.
 */

test.use({ viewport: { width: 1672, height: 1100 } });

async function login(page: Page): Promise<void> {
  await page.goto("/fr/login");
  await page.fill("#login-username", process.env.E2E_USER ?? "admin");
  await page.fill("#login-password", process.env.E2E_PASSWORD ?? "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 20_000 });
}

/** Switch the header's period selector to a labelled option and let the reads settle. */
async function selectPeriod(page: Page, label: string): Promise<void> {
  await page.getByRole("button", { name: /Période/ }).click();
  await page.getByRole("menuitem", { name: label, exact: true }).click();
  // The ribbon and the table are separate queries; both must have re-fetched before a
  // comparison means anything. A fixed wait is crude but honest here — there is no single
  // element whose settling proves BOTH have settled, which is the very coupling under test.
  await page.waitForTimeout(2500);
}

/**
 * Faithfulness as each of the two surfaces states it, in percent.
 *
 * The percentage, not the sample sentence: the ribbon only prints "N réponses sur M" when it
 * is BREACHING, and a probe keyed on that sentence reports "blind" on a healthy window — which
 * is a correct refusal, but it leaves the comparison unmade exactly when the page is calm.
 * The percentage is on screen either way.
 *
 * `null` when a surface shows nothing at all. That is a real state and not a failure: over a
 * window holding no scored answers the ribbon does not render and the controls table drops the
 * row, which is the honest thing for both to do.
 */
async function faithfulness(page: Page): Promise<{ hero: number | null; table: number | null }> {
  return page.evaluate(() => {
    const text = document.body.innerText;
    const heroMatch = /Fidélité\s*—\s*([\d,.]+)\s*%/.exec(text);
    // The controls row: its rendered value sits between the row's label and its bar.
    const tableMatch = /Fidélité \(objectif de service\)[\s\S]{0,200}?(\d+(?:[.,]\d+)?)\s*%/.exec(
      text,
    );
    const num = (raw: string | undefined): number | null =>
      raw === undefined ? null : Number(raw.replace(",", "."));
    return { hero: num(heroMatch?.[1]), table: num(tableMatch?.[1]) };
  });
}

/** How far the two may differ: they round to different precisions (61,2 % vs 61 %). */
const ROUNDING_PTS = 1;

test("the quality ribbon and the controls table read the same window", async ({ page }) => {
  await login(page);
  await page.goto("/fr/surveiller/vue-ensemble");
  await page.waitForSelector("table thead tr th:nth-child(2)", { timeout: 30_000 });

  let compared = 0;
  for (const period of ["30 jours", "7 jours"]) {
    await selectPeriod(page, period);
    const { hero, table } = await faithfulness(page);
    if (hero === null || table === null) continue;
    compared += 1;
    expect(
      Math.abs(hero - table),
      `at «${period}» the ribbon reads ${hero} % and the table reads ${table} % — two correct ` +
        "numbers about two different windows, under one label",
    ).toBeLessThanOrEqual(ROUNDING_PTS);
  }
  // Anti-vacuity: a run where neither surface rendered would otherwise "pass" having compared
  // nothing. That is the shape this whole file exists to refuse.
  expect(
    compared,
    "neither period produced a comparable pair — the probe saw nothing",
  ).toBeGreaterThan(0);
});

test("changing the period changes what the page reports", async ({ page }) => {
  await login(page);
  await page.goto("/fr/surveiller/vue-ensemble");
  await page.waitForSelector("table thead tr th:nth-child(2)", { timeout: 30_000 });

  await selectPeriod(page, "30 jours");
  const wide = await faithfulness(page);
  await selectPeriod(page, "7 jours");
  const narrow = await faithfulness(page);

  expect(wide.table, "the 30-day window reported no faithfulness at all").not.toBeNull();
  expect(narrow.table, "the 7-day window reported no faithfulness at all").not.toBeNull();
  // Without this the agreement asserted above is agreement about one unchanging number — which
  // is precisely the state the cockpit was in until the period first reached the data.
  expect(
    narrow.table,
    `7 d and 30 d both report ${wide.table} % — the selector is not steering the page`,
  ).not.toBe(wide.table);
});
