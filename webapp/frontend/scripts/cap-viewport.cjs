// Capture a route at an EXACT viewport (no fullPage), to compare pixel-for-pixel
// against a fixed-size normative. Usage: node cap-viewport.cjs <route> <out> [w] [h]
const { chromium } = require("playwright");
const BASE = process.env.CAPTURE_BASE || "http://127.0.0.1:3097";
const HOST = new URL(BASE).hostname;
const SESSION = process.env.SESSION_TOKEN;
(async () => {
  const route = process.argv[2] || "/fr/agents/support-client/evaluations-mock";
  const out = process.argv[3] || "/tmp/cap.png";
  const W = Number(process.argv[4] || 1536);
  const H = Number(process.argv[5] || 1024);
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  if (SESSION) {
    await ctx.addCookies([
      { name: "authjs.session-token", value: SESSION, domain: HOST, path: "/", httpOnly: true, sameSite: "Lax" },
    ]);
  }
  const page = await ctx.newPage();
  await page.goto(`${BASE}${route}`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(1800);
  await page.screenshot({ path: out, clip: { x: 0, y: 0, width: W, height: H } });
  console.log(`captured ${route} -> ${out} (${W}x${H})`);
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
