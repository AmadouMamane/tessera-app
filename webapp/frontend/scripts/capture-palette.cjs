const { chromium, request } = require("playwright");
const BASE = "http://127.0.0.1:3097";
(async () => {
  const api = await request.newContext({ baseURL: BASE });
  const { csrfToken } = await (await api.get("/api/auth/csrf")).json();
  await api.post("/api/auth/callback/credentials", {
    form: {
      csrfToken,
      username: "admin",
      password: "tessera-admin",
      callbackUrl: `${BASE}/fr/select-space`,
      json: "true",
    },
    headers: { "content-type": "application/x-www-form-urlencoded" },
    maxRedirects: 0,
  });
  const session = (await api.storageState()).cookies.find((c) => c.name.includes("session-token"));
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1680, height: 1050 } });
  await ctx.addCookies([session]);
  const page = await ctx.newPage();
  await page.goto(`${BASE}/fr/agents/support-client/synthese`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(1200);
  await page.keyboard.press("Control+k");
  await page.waitForTimeout(900);
  await page.screenshot({ path: "/tmp/palette-open.png" });
  await page.keyboard.type("rele");
  await page.waitForTimeout(500);
  await page.screenshot({ path: "/tmp/palette-filter.png" });
  // also show agents: clear + type an agent-ish term
  for (let i = 0; i < 4; i++) await page.keyboard.press("Backspace");
  await page.keyboard.type("recou");
  await page.waitForTimeout(500);
  await page.screenshot({ path: "/tmp/palette-agent.png" });
  console.log("palette captured");
  await browser.close();
  await api.dispose();
})().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
