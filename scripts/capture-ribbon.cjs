// Log in as admin, render the Qualité IA page, and capture the TOP region (ribbon
// + sticky rail) at native 1536px so we can verify the alert ribbon is not masked.
const { chromium, request } = require("playwright");
const BASE = process.env.CAPTURE_BASE || "http://127.0.0.1:3097";
const USER = process.env.TESSERA_ADMIN_USER || "admin";
const PASS = process.env.TESSERA_ADMIN_PASS || "tessera-admin";

(async () => {
  const route = process.argv[2] || "/fr/surveiller/qualite-ia";
  const out = process.argv[3] || "/tmp/ribbon-top.png";

  const api = await request.newContext({ baseURL: BASE });
  const { csrfToken } = await (await api.get("/api/auth/csrf")).json();
  await api
    .post("/api/auth/callback/credentials", {
      form: { csrfToken, username: USER, password: PASS, callbackUrl: `${BASE}/fr/select-space`, json: "true" },
      headers: { "content-type": "application/x-www-form-urlencoded" },
      maxRedirects: 0,
    })
    .catch(() => {});
  const storage = await api.storageState();
  const session = storage.cookies.find((c) => c.name.includes("session-token"));
  if (!session) { console.log("NO SESSION"); await api.dispose(); process.exit(2); }

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1536, height: 900 } });
  await ctx.addCookies([session]);
  const page = await ctx.newPage();
  await page.goto(`${BASE}${route}`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(2800);
  if (process.env.CAP_SCROLL) {
    const y = Number(process.env.CAP_SCROLL);
    await page.evaluate((sy) => {
      const m = document.querySelector("main");
      if (m) m.scrollTop = sy;
    }, y);
    await page.waitForTimeout(500);
  }

  // Top region only (ribbon + rail), then a scrolled shot to prove the rail no
  // longer eats the ribbon during the scroll transition.
  if (process.env.CAP_FULL) {
    await page.screenshot({ path: out, fullPage: true });
  } else {
    const h = Number(process.env.CAP_CLIP_H || 360);
    await page.screenshot({ path: out, clip: { x: 0, y: 0, width: 1536, height: h } });
  }
  console.log(`captured ${route} -> ${out} url=${page.url()}`);
  await browser.close();
  await api.dispose();
})().catch((e) => { console.error(e); process.exit(1); });
