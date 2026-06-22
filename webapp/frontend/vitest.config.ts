import path from "node:path";

import { defineConfig } from "vitest/config";

/**
 * Vitest config for the dashboard's unit tests.
 *
 * `include` is restricted to `*.test.ts(x)` under the source dirs so the runner
 * never collects the Playwright end-to-end specs (`e2e/*.spec.ts`, run via
 * `test:e2e`). The `@` alias mirrors the tsconfig path map so unit tests can
 * import application modules the same way the app does.
 */
export default defineConfig({
  resolve: {
    alias: { "@": path.resolve(process.cwd()) },
  },
  test: {
    include: ["{lib,components,app}/**/*.test.{ts,tsx}"],
  },
});
