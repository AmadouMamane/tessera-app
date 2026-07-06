const { chromium, request } = require("playwright");
const BASE = process.env.CAPTURE_BASE || "http://127.0.0.1:3097";
const USER = process.env.TESSERA_ADMIN_USER || "admin";
const PASS = process.env.TESSERA_ADMIN_PASS || "tessera-admin";

(async () => {
  const route = process.argv[2] || "/fr/agents/support-client/console";
  const out = process.argv[3] || "/tmp/console-after.png";

  const api = await request.newContext({ baseURL: BASE });
  const csrfRes = await api.get("/api/auth/csrf");
  const { csrfToken } = await csrfRes.json();
  console.log("csrfToken len:", (csrfToken || "").length);

  const cb = await api
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
    .catch((e) => {
      console.log("post err", e.message);
      return null;
    });
  if (cb) console.log("callback status:", cb.status());

  const storage = await api.storageState();
  const session = storage.cookies.find((c) => c.name.includes("session-token"));
  console.log(
    "session cookie:",
    session ? `${session.name} (${session.value.length} chars)` : "NONE",
  );
  if (!session) {
    await api.dispose();
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
  await page.waitForTimeout(2500);
  await page.screenshot({ path: out, fullPage: true });
  const dims = await page.evaluate(() => ({
    w: document.documentElement.scrollWidth,
    h: document.documentElement.scrollHeight,
  }));
  console.log(`captured ${route} -> ${out} (${dims.w}x${dims.h}) url=${page.url()}`);
  await browser.close();
  await api.dispose();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
