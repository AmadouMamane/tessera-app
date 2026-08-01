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
 * The faithfulness sample size, as each of the two surfaces states it.
 *
 * The ribbon says "18 réponses sur 67 sous l'objectif"; the table's detail line says
 * "1/1 conformes". The denominators are the same quantity — how many scored answers the
 * window holds — so they are directly comparable, and they are what moves when a window
 * changes. Comparing the percentages instead would let two different samples agree by
 * rounding.
 */
async function faithfulnessDenominators(page: Page): Promise<{ hero: number; table: number }> {
  const body = await page.innerText("body");
  const heroMatch = /(\d+)\s+réponses?\s+sur\s+(\d+)/.exec(body);
  const tableMatch = /(\d+)\s*\/\s*(\d+)\s+conformes/.exec(body);
  expect(heroMatch, "the quality ribbon's sample sentence was not found — the probe went blind")
    .not.toBeNull();
  expect(tableMatch, "the faithfulness row's detail line was not found — the probe went blind")
    .not.toBeNull();
  return { hero: Number(heroMatch?.[2]), table: Number(tableMatch?.[2]) };
}

test("the quality ribbon and the controls table count the same window", async ({ page }) => {
  await login(page);
  await page.goto("/fr/surveiller/vue-ensemble");
  await page.waitForSelector("table thead tr th:nth-child(2)", { timeout: 30_000 });

  for (const period of ["30 jours", "7 jours"]) {
    await selectPeriod(page, period);
    const { hero, table } = await faithfulnessDenominators(page);
    expect(
      hero,
      `at «${period}» the ribbon counts ${hero} scored answers and the table counts ${table} — ` +
        "two correct numbers about two different windows, under one label",
    ).toBe(table);
  }
});

test("changing the period changes what the page reports", async ({ page }) => {
  await login(page);
  await page.goto("/fr/surveiller/vue-ensemble");
  await page.waitForSelector("table thead tr th:nth-child(2)", { timeout: 30_000 });

  await selectPeriod(page, "30 jours");
  const wide = await faithfulnessDenominators(page);
  await selectPeriod(page, "24 heures");
  const narrow = await faithfulnessDenominators(page);

  // The anti-vacuity half. Without it the test above passes trivially on a page where the
  // period reaches nothing at all — which is exactly the state this whole change set found.
  expect(
    narrow.table,
    `24 h and 30 d both report ${wide.table} scored answers: the selector is not steering the ` +
      "page, and the agreement asserted above is agreement about one unchanging number",
  ).toBeLessThan(wide.table);
});
