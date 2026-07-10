import { defineConfig, devices } from "@playwright/test";

/**
 * E2E config for the cockpit frontend.
 *
 * Tests run against the dev stack: this Next app on :3390 pointed at the
 * Tessera backend on :8290 (which itself needs pgvector). The webServer block
 * starts Next if it is not already up and reuses a running one locally; the
 * backend must be started separately (see CLAUDE.md / the functional-page
 * playbook). Override the target with E2E_BASE_URL.
 *
 * SERIAL BY DESIGN (measured 2026-07-10, not assumed). These specs drive ONE
 * shared backend, and several of them mutate durable state (`a-faire` takes an
 * item in charge, `etat-a-date` saves a snapshot). Running them concurrently
 * does not merely slow the stack down — it makes the suite *lie*. Three runs of
 * the same unchanged tree:
 *
 *   4 workers · `next dev`    → 102 failed  (93 pinned at exactly 30.0s/35.0s;
 *                               the backend logged `couldn't get a connection
 *                               after 30.00 sec` — its 10-connection pool starved
 *                               while Next recompiled routes on demand)
 *   4 workers · `next start`  →  72 failed  (pool no longer starves; the single
 *                               dev backend still saturates — a cockpit page
 *                               fans out 20-44 backend calls)
 *   1 worker  · `next start`  →  31 failed, 127 passed  ← the real number
 *
 * So: one worker, and never `next dev` for a full-suite run — build first
 * (`pnpm build && pnpm start -p 3390`). A parallel run reports failures that
 * are timeouts, not defects, and buries the 31 that are real.
 *
 * The server that serves this suite NEEDS `AUTH_SECRET`. Without it NextAuth
 * mints no session and fails soft: every authenticated page still answers 200,
 * rendered as its logged-out shell, so the specs log in, find no table, and
 * report ~170 content failures that never mention the secret. The main checkout
 * has it in `webapp/frontend/.env.local`; an agent worktree does not. Measured
 * 2026-07-10: 170 failures with no secret, 31 with one, same commit.
 */
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3390";

export default defineConfig({
  testDir: "./e2e",
  // Not `fullyParallel`: see the header. Tests within a file share mutations.
  fullyParallel: false,
  workers: 1,
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
    // CI serves a PRODUCTION build: `pnpm build` runs as its own step, then
    // `next start`. That is where the measurements in this header were taken,
    // and a `next dev` run reports compile timeouts as test failures. Locally
    // the dev server stays the default. `reuseExistingServer` is true in both
    // places, so CI reuses the server it started itself and can never silently
    // fall back to `next dev` underneath a full-suite run.
    command: process.env.CI ? "npx next start -p 3390" : "npx next dev -p 3390",
    url: `${baseURL}/fr/login`,
    reuseExistingServer: true,
    timeout: 120_000,
    env: { TESSERA_BACKEND_URL: process.env.TESSERA_BACKEND_URL ?? "http://localhost:8290" },
  },
});
