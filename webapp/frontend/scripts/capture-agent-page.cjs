// Side-by-side conformance capture: log in as admin, render an AGENT page at the
// normative image's native width (1536px), full-page, against the seeded agent.
// Usage: node scripts/capture-agent-page.cjs <route> <outPath>
const { chromium } = require("playwright");

const BASE = process.env.CAPTURE_BASE || "http://127.0.0.1:3097";
const HOST = new URL(BASE).hostname;
const SESSION = process.env.SESSION_TOKEN; // authjs.session-token value (admin)

(async () => {
  const route = process.argv[2] || "/fr/agents/support-client/synthese";
  const out = process.argv[3] || "/tmp/capture.png";
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1536, height: 1000 } });
  if (SESSION) {
    await ctx.addCookies([
      {
        name: "authjs.session-token",
        value: SESSION,
        domain: HOST,
        path: "/",
        httpOnly: true,
        sameSite: "Lax",
      },
    ]);
  }
  const page = await ctx.newPage();

  await page.goto(`${BASE}${route}`, { waitUntil: "domcontentloaded" });
  // Let client queries hydrate; networkidle then a settle delay.
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(2500);

  await page.screenshot({ path: out, fullPage: true });
  const dims = await page.evaluate(() => ({
    w: document.documentElement.scrollWidth,
    h: document.documentElement.scrollHeight,
  }));
  console.log(`captured ${route} -> ${out} (${dims.w}x${dims.h})`);
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
