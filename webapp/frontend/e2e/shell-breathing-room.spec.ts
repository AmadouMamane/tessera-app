import { type Page, expect, test } from "@playwright/test";

/**
 * The end of a scrolled page must not sit ON the footer.
 *
 * The shell used `py-5`, giving the END of a long scroll the same 20px the top gets — and 20px
 * under the last card, with a fixed footer bar immediately beneath it, reads as touching. An
 * operator scrolled to the bottom of `/surveiller/observabilite` and saw the last panel welded
 * to the compliance strip.
 *
 * This is a property of the SHELL, not of any one page, so it is asserted here and on more than
 * one route: a fix applied to a single page's own padding would leave every other long page
 * exactly as it was.
 *
 * It has to be MEASURED. No selector can see this — every element is present, visible, and
 * correctly labelled while the gap is zero. Only the geometry says it.
 *
 * The real cause was one class deeper than the padding. The content box carried `h-full`, so it
 * was exactly the viewport and its children OVERFLOWED it: the scroll container's padding-bottom
 * was declared, applied to a box the content had already escaped, and therefore never seen.
 * Measured before the fix: 1px of clearance on /observabilite, 0px on /qualite-ia.
 *
 * NOT asserted here, and deliberately named rather than quietly excluded (ADR 0026):
 * `/surveiller/vue-ensemble` has a SEPARATE, pre-existing anomaly — its content overflows the
 * shell's scroll container by ~117px, so `scrollTop` moves while the picture does not. The shell
 * fix does not address it and this spec would be red on it for a reason that has nothing to do
 * with the property above. It needs its own diagnosis in `overview-dashboard.tsx`.
 */

test.use({ viewport: { width: 1672, height: 900 } });

/** Minimum clearance, in CSS pixels, between the end of the content and the footer. */
const MIN_GAP = 24;

async function login(page: Page) {
  await page.goto("/fr/login");
  await page.fill("#login-username", "admin");
  await page.fill("#login-password", "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 20_000 });
}

const LONG_PAGES = ["/fr/surveiller/observabilite", "/fr/surveiller/qualite-ia"];

for (const route of LONG_PAGES) {
  test(`the end of ${route} keeps room above the footer`, async ({ page }) => {
    await login(page);
    await page.goto(route);
    const content = page.locator("[data-shell-content]");
    await expect(content).toBeVisible();

    // Scroll the shell's own scroll container — the window does not scroll here.
    await page.evaluate(() => {
      const main = document.querySelector("[data-shell-content]")?.parentElement;
      if (main) main.scrollTop = main.scrollHeight;
    });
    // One frame for the scroll to settle before measuring boxes.
    await page.waitForTimeout(250);

    const gap = await page.evaluate(() => {
      const content = document.querySelector("[data-shell-content]");
      const footer = document.querySelector("footer");
      if (content === null || footer === null) return null;
      return footer.getBoundingClientRect().top - content.getBoundingClientRect().bottom;
    });

    // `null` means the shell is not on screen at all (an unauthenticated redirect, say) —
    // reported as skipped rather than silently passing on a measurement nobody took.
    expect(gap, "the shell content and its footer must both be present to measure").not.toBeNull();
    expect(gap ?? 0).toBeGreaterThanOrEqual(MIN_GAP);
  });
}
