// Log in as admin via the credentials form, then capture an AGENT page at the
// normative image's native width (1536px), full-page, against the seeded agent.
// Usage: node scripts/capture-login-console.cjs <route> <outPath>
const { chromium } = require("playwright");

const BASE = process.env.CAPTURE_BASE || "http://127.0.0.1:3097";
const USER = process.env.TESSERA_ADMIN_USER || "admin";
const PASS = process.env.TESSERA_ADMIN_PASS || "tessera-admin";

(async () => {
  const route = process.argv[2] || "/fr/agents/support-client/console";
  const out = process.argv[3] || "/tmp/console-capture.png";
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1536, height: 1000 } });
  const page = await ctx.newPage();

  // 1. Log in.
  await page.goto(`${BASE}/fr/login`, { waitUntil: "domcontentloaded" });
  await page.fill("#login-username", USER);
  await page.fill("#login-password", PASS);
  await Promise.all([
    page.waitForURL(/select-space|synthese|produit/, { timeout: 15000 }).catch(() => {}),
    page.click('button[type="submit"]'),
  ]);
  await page.waitForTimeout(800);

  // 2. Navigate to the target route and settle.
  await page.goto(`${BASE}${route}`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(2500);

  await page.screenshot({ path: out, fullPage: true });
  const dims = await page.evaluate(() => ({
    w: document.documentElement.scrollWidth,
    h: document.documentElement.scrollHeight,
  }));
  console.log(`captured ${route} -> ${out} (${dims.w}x${dims.h}) url=${page.url()}`);
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
