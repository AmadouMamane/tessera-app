// Capture the CLIENT chat (/produit): send one real turn, screenshot the premium
// bubble rendering (avatars, Markdown, citations) to prove the extraction left it
// unchanged. No login needed (product surface is public).
const { chromium } = require("playwright");
const BASE = process.env.CAPTURE_BASE || "http://127.0.0.1:3097";
const QUESTION =
  process.env.QUESTION || "Quels documents pour ouvrir un compte courant chez Crédit Aurore ?";

(async () => {
  const out = process.argv[2] || "/tmp/produit.png";
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 1000 } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/fr/produit`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle").catch(() => {});

  const box = page.locator("textarea, input[type=text]").first();
  await box.waitFor({ timeout: 15000 });
  await box.fill(QUESTION);
  await box.press("Enter");

  // Wait for the assistant reply (the "regenerate" affordance appears once done).
  await page
    .getByText("régénérer", { exact: false })
    .waitFor({ timeout: 120000 })
    .catch(() => console.log("WARN: regenerate not seen; capturing anyway"));
  await page.waitForTimeout(1500);

  await page.screenshot({ path: out, fullPage: true });
  console.log(`captured /produit -> ${out} url=${page.url()}`);
  await browser.close();
})().catch((e) => {
  console.error(e.message || e);
  process.exit(1);
});
