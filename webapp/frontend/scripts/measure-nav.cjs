// Measure AGENT tab navigation: did the skeleton paint instantly, and how long
// until real content. Pass BASE via env (dev :3097 or prod :3098).
const { chromium, request } = require("playwright");
const BASE = process.env.CAPTURE_BASE || "http://127.0.0.1:3097";

async function tabNav(page, label, hrefPart) {
  const t0 = Date.now();
  // click the AgentTabs link for the target sub-page
  await page.click(`a[href*="${hrefPart}"]`);
  // skeleton should appear ~immediately
  let skeletonMs = -1;
  try {
    await page.waitForSelector('[data-testid="agent-loading"]', { timeout: 3000, state: "attached" });
    skeletonMs = Date.now() - t0;
  } catch {}
  // wait for the skeleton to go away (real content) — or networkidle fallback
  await page.waitForSelector('[data-testid="agent-loading"]', { state: "detached", timeout: 30000 }).catch(()=>{});
  await page.waitForLoadState("networkidle").catch(()=>{});
  const contentMs = Date.now() - t0;
  console.log(`  ${label}: skeleton@${skeletonMs}ms  content@${contentMs}ms`);
}

(async () => {
  const api = await request.newContext({ baseURL: BASE });
  const { csrfToken } = await (await api.get("/api/auth/csrf")).json();
  await api.post("/api/auth/callback/credentials", { form:{csrfToken,username:"admin",password:"tessera-admin",callbackUrl:`${BASE}/fr/select-space`,json:"true"}, headers:{"content-type":"application/x-www-form-urlencoded"}, maxRedirects:0 });
  const session = (await api.storageState()).cookies.find(c=>c.name.includes("session-token"));
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport:{width:1536,height:1000} });
  await ctx.addCookies([session]);
  const page = await ctx.newPage();
  await page.goto(`${BASE}/fr/agents/support-client/synthese`, { waitUntil:"networkidle" });
  await page.waitForTimeout(800);

  console.log(`BASE=${BASE}`);
  console.log("First visit per tab (dev: includes compile):");
  await tabNav(page, "→ configurations", "/configurations");
  await tabNav(page, "→ evaluations", "/evaluations");
  await tabNav(page, "→ garde-fous", "/garde-fous");
  console.log("Revisit (cached + compiled):");
  await tabNav(page, "→ configurations (revisit)", "/configurations");
  await tabNav(page, "→ synthese (revisit)", "/synthese");

  await browser.close(); await api.dispose();
})().catch(e=>{console.error(e.message||e);process.exit(1);});
