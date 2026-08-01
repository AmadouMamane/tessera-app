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
  // The signal registry, which lives behind its own tab. Reached explicitly because the
  // default tab does not render it — and a probe that silently measures a different table
  // than the one it names is the shape this file has already fallen into twice.
  "/fr/surveiller/qualite-ia?tab=signals",
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
      const gaps = gutters(cells).filter((g) => g >= 0);
      if (gaps.length < 3) continue;
      // ONE column may absorb the card's leftover width, and exactly one. That is the design
      // rule: every column is sized by its content, and whatever the card has left over goes
      // to a single named column — the one holding a sentence, so the slack reads as prose
      // rather than as a hole. Drop the widest gutter (that column's); the rest must be one
      // value.
      //
      // Written this way after a version that demanded the LAST gutter be the odd one. That
      // forces the slack onto whichever column happens to be last: on Contrôles critiques
      // that is a one-word "Investiguer" link, and giving it the leftover wrapped the impact
      // sentence beside it onto three lines. On Sécurité the slack sits on "Action demandée",
      // the fifth of seven columns, and the old rule reported a defect that was the design.
      const rhythm = [...gaps].sort((a, b) => a - b).slice(0, -1);
      const spread = Math.max(...rhythm) - Math.min(...rhythm);
      expect(
        spread,
        `table ${index} on ${path}: gutters ${JSON.stringify(gaps)} px between columns ` +
          `[${cells.map((c) => c.text).join(" | ")}] — one column may absorb the slack; the ` +
          `other ${rhythm.length} should be one value, and they are ${new Set(rhythm).size}`,
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

/**
 * A short cell must not wrap.
 *
 * This is the other half of "widths fit their content", and the half that is easy to break
 * while fixing the first: once ONE column absorbs the card's leftover width, every other
 * column collapses to its narrowest legal box, and for a text column that box is "wrap at
 * every space". The first pass at the slack column did exactly that — «≤ 0.10%» broke across
 * two lines and «Fidélité (objectif de service)» across three.
 *
 * Twelve characters is the threshold because it separates the two cases cleanly: a threshold,
 * a percentage, a state badge, a count are all shorter; a sentence in the impact column is
 * far longer and SHOULD wrap. A two-word header like «Valeur actuelle» sits between them and
 * is deliberately left alone — forcing it onto one line would widen the column past its data.
 */
const SHORT_TEXT_CHARS = 12;

for (const path of PAGES) {
  test(`${path} — no short cell is narrower than its own text`, async ({ page }) => {
    await login(page);
    await page.goto(path);
    await page.waitForSelector("table thead tr th:nth-child(2)", { timeout: 30_000 });
    await settle(page);

    const wrapped = await page.evaluate((limit) => {
      const offenders: string[] = [];
      for (const cell of Array.from(document.querySelectorAll("table td, table th"))) {
        const text = (cell.textContent ?? "").trim();
        if (text.length === 0 || text.length > limit || !text.includes(" ")) continue;
        // A cell that stacks BLOCK children is meant to be several lines — a value with its
        // detail line beneath it. Only inline content can be said to have wrapped.
        if (cell.querySelector("div, p, ul, table")) continue;
        // Measure the TEXT, not the cell. A `<td>` is as tall as its ROW, so a threshold
        // sitting beside a three-line signal name reports as wrapped while rendering on one
        // line — which is what the first version of this probe did, on every page at once.
        const range = document.createRange();
        range.selectNodeContents(cell);
        const ink = range.getBoundingClientRect();
        const line = Number.parseFloat(getComputedStyle(cell).lineHeight) || 16;
        if (ink.height > line * 1.6) {
          offenders.push(
            `«${text}» in a ${Math.round(cell.getBoundingClientRect().width)}px column`,
          );
        }
      }
      return offenders;
    }, SHORT_TEXT_CHARS);

    expect(wrapped, `short cells wrapped: ${wrapped.join("; ")}`).toEqual([]);
  });
}
