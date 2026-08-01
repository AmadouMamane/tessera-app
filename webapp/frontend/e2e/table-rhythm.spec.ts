import { type Page, expect, test } from "@playwright/test";

/**
 * Column rhythm, MEASURED on the rendered page.
 *
 * The complaint that produced this file was "the column widths look a bit random, it does not
 * feel premium". That is a statement about geometry, and geometry is the one thing a class
 * scan cannot see. Counting `pr-4` occurrences would report a tidy repo over a table whose
 * columns are visibly uneven, because what reaches the screen is the resolved cascade over the
 * actual content — `tailwind-merge` lets the last caller win, a `w-24` sits among six auto
 * columns, and a long label in one cell pushes every neighbour.
 *
 * So this reads `getBoundingClientRect` off the real DOM in a real browser and asserts on
 * pixels:
 *
 *  1. **One gutter, everywhere but one column.** Every column is sized by its content; a
 *     single named column absorbs whatever the card has left over. An operator reads a table
 *     by its vertical alignment, and gaps of 16, 8, 24, 16 px are what "random" looks like.
 *  2. **The slack goes to the column holding a sentence**, not to the one holding a link — so
 *     the leftover width reads as prose instead of as a hole. (This is why the rule is "one
 *     column" and not "the last column": an earlier version demanded the last one, which put
 *     the slack on "Investiguer" and wrapped the impact sentence beside it onto three lines.)
 *  3. **The rhythm survives a narrower viewport.** A table that is even at 1672 px and ragged
 *     at 1280 px is even by luck.
 *
 * Run it against a BUILT server (see playwright.config.ts): `next dev` recompiles routes on
 * demand and the first paint of a page can be measured mid-layout.
 */

test.use({ viewport: { width: 1672, height: 1000 } });

async function login(page: Page): Promise<void> {
  await page.goto("/fr/login");
  await page.fill("#login-username", process.env.E2E_USER ?? "admin");
  await page.fill("#login-password", process.env.E2E_PASSWORD ?? "tessera-admin");
  await page.click("button[type=submit]");
  await page.waitForURL((url) => !url.pathname.endsWith("/login"), { timeout: 20_000 });
}

/**
 * Wait until the header geometry stops changing.
 *
 * A table can exist and still be resizing: data arrives, a column's longest cell grows, the
 * auto layout redistributes. Measuring in that moment produces numbers that are real and
 * meaningless. Two identical consecutive reads is the cheapest honest "it has settled".
 */
async function settle(page: Page): Promise<void> {
  let previous = "";
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const current = await page.evaluate(() =>
      Array.from(document.querySelectorAll("table thead tr"))
        .map((row) =>
          Array.from(row.children)
            .map((c) => Math.round(c.getBoundingClientRect().width))
            .join(","),
        )
        .join("|"),
    );
    if (current !== "" && current === previous) return;
    previous = current;
    await page.waitForTimeout(250);
  }
}

interface CellBox {
  left: number;
  right: number;
  width: number;
  /** Where the cell's ink actually ends — the widest child's right edge. */
  inkRight: number;
  text: string;
}

/**
 * Every table's COLUMNS, with the extent of the widest ink each one holds.
 *
 * The first version of this measured the header row alone, and it was wrong in a way that
 * produced confident numbers: it reported the "Agent" column as 100-157 px wider than its
 * content on three pages. It is not. The header says "Agent"; the body says
 * "recouvrement-collections", and the column is sized by the body — which is auto-layout
 * doing exactly the right thing. A gutter is the distance from the widest ink IN THE COLUMN
 * to where the next column begins, so that is what is measured.
 */
async function measureTables(page: Page): Promise<CellBox[][]> {
  return page.evaluate(() => {
    /** The rightmost edge of a cell's actual ink, not of its padded box. */
    const ink = (cell: Element): number => {
      const box = cell.getBoundingClientRect();
      const children = Array.from(cell.children);
      if (children.length > 0) {
        return children.reduce((r, c) => Math.max(r, c.getBoundingClientRect().right), box.left);
      }
      if (cell.firstChild) {
        const range = document.createRange();
        range.selectNodeContents(cell);
        return range.getBoundingClientRect().right || box.right;
      }
      return box.left;
    };

    return Array.from(document.querySelectorAll("table"))
      .map((table) => {
        const head = table.querySelector("thead tr");
        if (!head) return [];
        const rows = [head, ...Array.from(table.querySelectorAll("tbody tr"))];
        return Array.from(head.children).map((headCell, column) => {
          const box = headCell.getBoundingClientRect();
          // A column's content width is the WIDEST ink in it, across every row. Taking the
          // header alone reports a column sized by its body as one padded by nothing.
          let inkRight = box.left;
          for (const row of rows) {
            const cell = row.children[column];
            // A `colspan` row (an empty state, a group heading) has fewer cells than the
            // header. Skipping it is not a blind spot — it belongs to no single column.
            if (cell && row.children.length === head.children.length) {
              inkRight = Math.max(inkRight, ink(cell));
            }
          }
          return {
            left: box.left,
            right: box.right,
            width: box.width,
            inkRight,
            text: (headCell.textContent ?? "").trim().slice(0, 24),
          };
        });
      })
      .filter((cells) => cells.length > 1);
  });
}

/** Distinct gaps between the ink of one column and the start of the next, rounded to 1 px. */
function gutters(cells: CellBox[]): number[] {
  const gaps: number[] = [];
  for (let i = 0; i < cells.length - 1; i += 1) {
    const here = cells[i];
    const next = cells[i + 1];
    if (!here || !next) continue;
    gaps.push(Math.round(next.left - here.inkRight));
  }
  return gaps;
}

/** Pages whose cards the complaint was about — the multi-column surfaces an operator lives in. */
const PAGES = [
  "/fr/surveiller/vue-ensemble",
  "/fr/surveiller/qualite-ia",
  "/fr/surveiller/securite-privacy",
] as const;

for (const path of PAGES) {
  test(`${path} — every table keeps one gutter between its columns`, async ({ page }) => {
    await login(page);
    await page.goto(path);
    // NOT `networkidle`: a cockpit page polls, so it never goes idle and the wait times out
    // after 30 s having measured nothing. Wait for the thing being measured to exist instead —
    // and then for it to stop moving, because a table measured mid-hydration reports the
    // skeleton's geometry and would have passed this file for the wrong reason.
    await page.waitForSelector("table thead tr th:nth-child(2)", { timeout: 30_000 });
    await settle(page);
    const tables = await measureTables(page);
    expect(
      tables.length,
      `no multi-column table found on ${path} — the probe went blind`,
    ).toBeGreaterThan(0);

    for (const [index, cells] of tables.entries()) {
      const gaps = gutters(cells);
      // The LAST gap is excluded from the uniformity claim: the final column often carries an
      // action link that is deliberately right-aligned, and its lead-in is a layout choice
      // rather than a rhythm. Everything before it is rhythm.
      const inner = gaps.slice(0, -1).filter((g) => g >= 0);
      if (inner.length < 2) continue;
      const spread = Math.max(...inner) - Math.min(...inner);
      expect(
        spread,
        `table ${index} on ${path}: gutters ${JSON.stringify(inner)} px between columns ` +
          `[${cells.map((c) => c.text).join(" | ")}] — they should be one value, not ${new Set(inner).size}`,
      ).toBeLessThanOrEqual(TOLERANCE_PX);
    }
  });
}

/**
 * How far two gutters may differ and still read as one rhythm.
 *
 * Not zero: sub-pixel layout and font metrics move an ink edge by a fraction, and a test that
 * demands exactness fails on a machine with different font rendering rather than on a defect.
 * Four pixels is under a quarter of the smallest gutter in the design.
 */
const TOLERANCE_PX = 4;

test("the rhythm holds at a laptop width, not only at a wide desktop", async ({ page }) => {
  await login(page);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/fr/surveiller/vue-ensemble");
  await page.waitForSelector("table thead tr th:nth-child(2)", { timeout: 30_000 });
  await settle(page);
  for (const cells of await measureTables(page)) {
    const gaps = gutters(cells).filter((g) => g >= 0);
    if (gaps.length < 3) continue;
    const rhythm = [...gaps].sort((a, b) => a - b).slice(0, -1);
    expect(
      Math.max(...rhythm) - Math.min(...rhythm),
      `at 1280 px the gutters are ${JSON.stringify(gaps)} — even at 1672 px is even by luck`,
    ).toBeLessThanOrEqual(TOLERANCE_PX);
  }
});
