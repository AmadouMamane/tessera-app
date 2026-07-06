// Runtime sweep: log in as operator, visit each cockpit route, collect any
// next-intl MISSING_MESSAGE (raw-key leak) seen in the browser console.
const { chromium, request } = require("playwright");
const BASE = process.env.CAPTURE_BASE || "http://127.0.0.1:3097";
const USER = process.env.TESSERA_ADMIN_USER || "admin";
const PASS = process.env.TESSERA_ADMIN_PASS || "tessera-admin";

const ROUTES = (process.env.ROUTES || "").split(",").filter(Boolean);

(async () => {
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
    .catch(() => {});
  const storage = await api.storageState();
  const session = storage.cookies.find((c) => c.name.includes("session-token"));
  if (!session) {
    console.log("NO SESSION");
    process.exit(2);
  }

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1536, height: 1000 } });
  await ctx.addCookies([session]);
  const page = await ctx.newPage();

  const found = {};
  const record = (txt) => {
    const m =
      /MISSING_MESSAGE[^\n]*?`?([\w.$-]+)`?[^\n]*?locale `?(\w+)`?/i.exec(txt) ||
      /Could not resolve `([^`]+)` in messages for locale `(\w+)`/i.exec(txt);
    if (m) {
      const k = m[1];
      (found[k] = found[k] || new Set()).add(page.url().replace(BASE, ""));
    }
  };
  page.on("console", (msg) => {
    if (msg.type() === "error") record(msg.text());
  });
  page.on("pageerror", (err) => record(String(err)));

  for (const r of ROUTES) {
    try {
      await page.goto(`${BASE}${r}`, { waitUntil: "domcontentloaded" });
      await page.waitForLoadState("networkidle").catch(() => {});
      await page.waitForTimeout(1200);
    } catch (e) {
      console.log(`  visit error ${r}: ${e.message}`);
    }
  }

  const keys = Object.keys(found).sort();
  console.log(`\n=== ${keys.length} clé(s) MISSING_MESSAGE ===`);
  for (const k of keys) console.log(`  ${k}  @ ${[...found[k]].join(", ")}`);
  await browser.close();
  await api.dispose();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
