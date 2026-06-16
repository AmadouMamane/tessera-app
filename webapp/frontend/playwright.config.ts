import { defineConfig, devices } from "@playwright/test";

/**
 * E2E config for the cockpit frontend.
 *
 * Tests run against the dev stack: this Next app on :3390 pointed at the
 * Tessera backend on :8290 (which itself needs pgvector). The webServer block
 * starts Next if it is not already up and reuses a running one locally; the
 * backend must be started separately (see CLAUDE.md / the functional-page
 * playbook). Override the target with E2E_BASE_URL.
 */
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3390";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "list" : [["list"]],
  use: {
    baseURL,
    trace: "on-first-retry",
    viewport: { width: 1672, height: 1000 },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npx next dev -p 3390",
    url: `${baseURL}/fr/login`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: { TESSERA_BACKEND_URL: process.env.TESSERA_BACKEND_URL ?? "http://localhost:8290" },
  },
});
