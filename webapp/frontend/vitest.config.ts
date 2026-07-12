import path from "node:path";

import { defineConfig } from "vitest/config";

/**
 * Vitest config for the dashboard's unit tests.
 *
 * `include` is restricted to `*.test.ts(x)` under the source dirs so the runner
 * never collects the Playwright end-to-end specs (`e2e/*.spec.ts`, run via
 * `test:e2e`). The `@` alias mirrors the tsconfig path map so unit tests can
 * import application modules the same way the app does.
 *
 * `jsx: "automatic"` matches what Next compiles the app with. Without it esbuild uses the
 * classic transform, which needs `React` in scope — so a component test fails with
 * "React is not defined" and looks like a missing import rather than a config gap.
 */
export default defineConfig({
  esbuild: { jsx: "automatic" },
  resolve: {
    alias: { "@": path.resolve(process.cwd()) },
  },
  test: {
    include: ["{lib,components,app}/**/*.test.{ts,tsx}"],
  },
});
