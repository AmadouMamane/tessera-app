// Login as admin, render a page, then screenshot specific cards by their title text.
// Usage: SESSION via login; node scripts/capture-cards.cjs <route> <outDir> "Title A" "Title B" ...
const { chromium, request } = require("playwright");
const BASE = process.env.CAPTURE_BASE || "http://127.0.0.1:3097";
const USER = process.env.TESSERA_ADMIN_USER || "admin";
const PASS = process.env.TESSERA_ADMIN_PASS || "tessera-admin";

(async () => {
  const route = process.argv[2];
  const outDir = process.argv[3];
  const titles = process.argv.slice(4);

  const api = await request.newContext({ baseURL: BASE });
  const { csrfToken } = await (await api.get("/api/auth/csrf")).json();
  await api
    .post("/api/auth/callback/credentials", {
      form: {
        csrfToken,
        username: USER,
        password: PASS,
        callbackUrl: `${BASE}/fr/select-space`,
        json: "true",
      },
      headers: { "content-type": "application/x-www-form-urlencoded" },
      maxRedirects: 0,
    })
    .catch(() => null);
  const storage = await api.storageState();
  const session = storage.cookies.find((c) => c.name.includes("session-token"));
  if (!session) {
    console.error("NO SESSION");
    process.exit(2);
  }

  const browser = await chromium.launch();
  const W = Number(process.env.CAP_W || 1536),
    H = Number(process.env.CAP_H || 1000);
  const ctx = await browser.newContext({ viewport: { width: W, height: H } });
  await ctx.addCookies([session]);
  const page = await ctx.newPage();
  await page.goto(`${BASE}${route}`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(2800);

  let i = 0;
  for (const title of titles) {
    i++;
    // Find the CardTitle whose text starts with the given title, climb to its Card.
    const card = page
      .locator(`div.rounded-lg:has(> div:has-text(${JSON.stringify(title)}))`)
      .first();
    const handle = page.getByText(title, { exact: false }).first();
    try {
      await handle.scrollIntoViewIfNeeded();
      await page.waitForTimeout(400);
      // Screenshot the nearest Card ancestor (has rounded-lg + border).
      const cardEl = handle.locator("xpath=ancestor::div[contains(@class,'rounded-lg')][1]");
      const out = `${outDir}/card-${i}.png`;
      await cardEl.screenshot({ path: out });
      const box = await cardEl.boundingBox();
      console.log(
        `[${i}] "${title}" -> ${out} ${box ? `${Math.round(box.width)}x${Math.round(box.height)}` : "(no box)"}`,
      );
    } catch (e) {
      console.log(`[${i}] "${title}" FAILED: ${e.message}`);
    }
  }
  await browser.close();
  await api.dispose();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
