// Log in as admin, open the Console, run ONE real live turn, wait for the XT-01
// waterfall to populate, then screenshot. Proves the post-turn real state.
const { chromium, request } = require("playwright");
const BASE = process.env.CAPTURE_BASE || "http://127.0.0.1:3097";
const USER = "admin";
const PASS = "tessera-admin";
const QUESTION =
  process.env.QUESTION || "Quels documents pour ouvrir un compte courant chez Crédit Aurore ?";

(async () => {
  const out = process.argv[2] || "/tmp/console-turn.png";
  const api = await request.newContext({ baseURL: BASE });
  const { csrfToken } = await (await api.get("/api/auth/csrf")).json();
  await api.post("/api/auth/callback/credentials", {
    form: { csrfToken, username: USER, password: PASS, callbackUrl: `${BASE}/fr/select-space`, json: "true" },
    headers: { "content-type": "application/x-www-form-urlencoded" },
    maxRedirects: 0,
  });
  const session = (await api.storageState()).cookies.find((c) => c.name.includes("session-token"));
  if (!session) throw new Error("no session cookie");

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1536, height: 1000 } });
  await ctx.addCookies([session]);
  const page = await ctx.newPage();
  await page.goto(`${BASE}/fr/agents/support-client/console`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle").catch(() => {});

  const input = page.locator('input[placeholder*="Posez"]');
  await input.waitFor({ timeout: 15000 });
  await input.fill(QUESTION);
  await input.press("Enter");

  // Wait for the turn to finish: the XT-01 waterfall shows "Durée totale" only
  // once the SSE envelope (debug.trace) arrived.
  await page
    .getByText("Durée totale", { exact: false })
    .waitFor({ timeout: 120000 })
    .catch(() => console.log("WARN: trace total not seen within timeout"));
  await page.waitForTimeout(1500);

  await page.screenshot({ path: out, fullPage: true });
  const dims = await page.evaluate(() => ({
    w: document.documentElement.scrollWidth,
    h: document.documentElement.scrollHeight,
  }));
  console.log(`captured turn -> ${out} (${dims.w}x${dims.h}) url=${page.url()}`);
  await browser.close();
  await api.dispose();
})().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
