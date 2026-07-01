// Capture the three shell-chrome states on a cockpit page: full sidebar, icon
// rail (⌘B / persisted), and focus mode (⌘. — session). Admin login.
const { chromium, request } = require("playwright");
const BASE = process.env.CAPTURE_BASE || "http://127.0.0.1:3097";
const ROUTE = process.argv[2] || "/fr/agents/support-client/synthese";

(async () => {
  const api = await request.newContext({ baseURL: BASE });
  const { csrfToken } = await (await api.get("/api/auth/csrf")).json();
  await api.post("/api/auth/callback/credentials", {
    form: { csrfToken, username: "admin", password: "tessera-admin", callbackUrl: `${BASE}/fr/select-space`, json: "true" },
    headers: { "content-type": "application/x-www-form-urlencoded" },
    maxRedirects: 0,
  });
  const session = (await api.storageState()).cookies.find((c) => c.name.includes("session-token"));

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1680, height: 1050 } });
  await ctx.addCookies([session]);
  const page = await ctx.newPage();

  // 1. Full sidebar (default).
  await page.goto(`${BASE}${ROUTE}`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(1500);
  await page.screenshot({ path: "/tmp/chrome-full.png", fullPage: false });

  // 2. Icon rail via ⌘B, then verify persistence survives reload.
  await page.keyboard.press("Control+b");
  await page.waitForTimeout(600);
  await page.screenshot({ path: "/tmp/chrome-rail.png", fullPage: false });
  const persisted = await page.evaluate(() => window.localStorage.getItem("tessera.sidebarCollapsed"));
  console.log("collapsed persisted =", persisted);

  // restore full for the focus shot
  await page.keyboard.press("Control+b");
  await page.waitForTimeout(400);

  // 3. Focus mode via ⌘.  (hides sidebar + topbar, widens content).
  await page.keyboard.press("Control+.");
  await page.waitForTimeout(600);
  await page.screenshot({ path: "/tmp/chrome-focus.png", fullPage: false });

  console.log("captured full/rail/focus");
  await browser.close();
  await api.dispose();
})().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
