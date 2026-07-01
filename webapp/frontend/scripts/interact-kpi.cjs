// Verify the KPI overlay-link drill-down: clicking the card navigates to the real
// source; clicking the ⓘ opens the popover WITHOUT navigating.
const { chromium, request } = require("playwright");
const BASE = "http://127.0.0.1:3097";

(async () => {
  const api = await request.newContext({ baseURL: BASE });
  const { csrfToken } = await (await api.get("/api/auth/csrf")).json();
  await api.post("/api/auth/callback/credentials", {
    form: { csrfToken, username: "admin", password: "tessera-admin", callbackUrl: `${BASE}/fr/select-space`, json: "true" },
    headers: { "content-type": "application/x-www-form-urlencoded" }, maxRedirects: 0,
  }).catch(() => null);
  const session = (await api.storageState()).cookies.find((c) => c.name.includes("session-token"));

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1536, height: 1000 } });
  await ctx.addCookies([session]);
  const page = await ctx.newPage();

  // 1) Click the "Risques ouverts" KPI card body → should navigate to incidents-playbooks.
  await page.goto(`${BASE}/fr/surveiller/vue-ensemble`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(2500);
  const risk = page.getByText("Risques ouverts", { exact: false }).first();
  const card = risk.locator("xpath=ancestor::div[contains(@class,'rounded-lg')][1]");
  // Click the overlay <Link> directly (the pointer-transparent content forwards
  // real clicks here too; targeting it explicitly removes test flakiness).
  await card.locator('a[href$="incidents-playbooks"]').first().click();
  await page.waitForURL(/incidents-playbooks/, { timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(500);
  console.log("after card click url:", page.url(), page.url().includes("/agir/incidents-playbooks") ? "PASS" : "FAIL");

  // 2) Back to overview; click the ⓘ on "Score qualité" → popover opens, URL unchanged.
  await page.goto(`${BASE}/fr/surveiller/vue-ensemble`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(2500);
  const before = page.url();
  const quality = page.getByText("Score qualité", { exact: false }).first();
  const qcard = quality.locator("xpath=ancestor::div[contains(@class,'rounded-lg')][1]");
  const info = qcard.locator("button[aria-label]").first();
  await info.click();
  await page.waitForTimeout(800);
  const popoverVisible = await page.getByText(/évaluation continue|continuous evaluation|laufenden Bewertung/i).first().isVisible().catch(() => false);
  const after = page.url();
  console.log("after info click url:", after, "popover:", popoverVisible, after === before && popoverVisible ? "PASS" : "FAIL");

  await browser.close();
  await api.dispose();
})().catch((e) => { console.error(e); process.exit(1); });
