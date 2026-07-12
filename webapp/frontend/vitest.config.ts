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
 *
 * `server-only` resolves to a no-op stub. It is a Next build-time marker (it throws if a
 * module is pulled into a client bundle) with no runtime meaning, and it is unresolvable
 * outside the Next compiler — so without this alias, any `import "server-only"` module is
 * untestable. `lib/auth/accounts.ts` is one, and it holds the credential check (audit F-9):
 * exactly the kind of code that must be tested rather than trusted.
 */
export default defineConfig({
  esbuild: { jsx: "automatic" },
  resolve: {
    alias: {
      "@": path.resolve(process.cwd()),
      "server-only": path.resolve(process.cwd(), "test/stubs/server-only.ts"),
    },
  },
  test: {
    include: ["{lib,components,app}/**/*.test.{ts,tsx}"],
  },
});
