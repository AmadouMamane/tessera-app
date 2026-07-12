/**
 * The published default credentials are refused on an exposed deployment (audit F-9).
 *
 * `admin/tessera-admin`, `auditor/tessera-auditor` and `collections/tessera-collections` are
 * printed in a git repository. They stayed valid in ANY deployment whose operator had not set
 * three environment variables — the same fail-OPEN shape as the bearer before it: a missing
 * secret opened the door instead of closing it.
 *
 * Dev and CI keep them deliberately (the local loop, the e2e suite and the demo banner all
 * depend on them), so the test proves BOTH directions: refused where a stranger can reach us,
 * kept where one cannot. A fix that only did the first would break every developer.
 *
 * Each case re-imports the module, because the account list is built once at import time —
 * which is exactly what makes it a boot-time decision rather than a per-request one.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const ENV_KEYS = [
  "TESSERA_ENVIRONMENT",
  "TESSERA_AUTH_ADMIN_PASSWORD",
  "TESSERA_AUTH_AUDITOR_PASSWORD",
  "TESSERA_AUTH_COLLECTIONS_PASSWORD",
  "TESSERA_AUTH_SUPERADMIN_PASSWORD",
] as const;

beforeEach(() => {
  // stubEnv, never `process.env.X = undefined` — that assigns the STRING "undefined", which is
  // truthy, so an "unset" password would happily authenticate. NODE_ENV additionally is
  // read-only to TypeScript, and `delete` is banned by the linter.
  for (const key of ENV_KEYS) vi.stubEnv(key, undefined);
  vi.stubEnv("NODE_ENV", "test");
  vi.resetModules();
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

async function accounts() {
  return import("./accounts");
}

describe("an exposed deployment refuses the credentials published in the repo", () => {
  it.each(["staging", "production"])(
    "TESSERA_ENVIRONMENT=%s: the seeded defaults do not authenticate",
    async (environment) => {
      vi.stubEnv("TESSERA_ENVIRONMENT", environment);

      const { verifyCredentials } = await accounts();

      expect(verifyCredentials("admin", "tessera-admin")).toBeNull();
      expect(verifyCredentials("auditor", "tessera-auditor")).toBeNull();
      expect(verifyCredentials("collections", "tessera-collections")).toBeNull();
    },
  );

  it("NODE_ENV=production catches the containerised front, which sets no TESSERA_ENVIRONMENT", async () => {
    // The deployed frontend has no Cloud Run service of its own — nothing sets
    // TESSERA_ENVIRONMENT on it — but Dockerfile.frontend sets NODE_ENV=production. Without
    // this clause the only real deployment would keep the repo's passwords.
    vi.stubEnv("NODE_ENV", "production");

    const { verifyCredentials } = await accounts();

    expect(verifyCredentials("admin", "tessera-admin")).toBeNull();
  });

  it("an EXPLICIT password still works — the demo keeps its theatrical gate", async () => {
    vi.stubEnv("TESSERA_ENVIRONMENT", "staging");
    vi.stubEnv("TESSERA_AUTH_ADMIN_PASSWORD", "a-password-the-operator-chose");

    const { verifyCredentials, demoCredentials } = await accounts();

    expect(verifyCredentials("admin", "a-password-the-operator-chose")).toEqual({ role: "admin" });
    // …and the repo's default is not a second, silent way in.
    expect(verifyCredentials("admin", "tessera-admin")).toBeNull();
    // The banner shows what is actually configured, so the demo still demonstrates RBAC.
    expect(demoCredentials().map((c) => c.username)).toEqual(["admin"]);
  });

  it("says out loud which accounts it just refused", async () => {
    vi.stubEnv("TESSERA_ENVIRONMENT", "production");
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    await accounts();

    const message = spy.mock.calls.flat().join(" ");
    expect(message).toContain("admin");
    expect(message).toContain("auditor");
    expect(message).toContain("collections");
    expect(message).toContain("TESSERA_AUTH_");
  });
});

describe("dev and CI keep the defaults — the local loop depends on them", () => {
  it.each([undefined, "local", "ci"])(
    "TESSERA_ENVIRONMENT=%s: the seeded accounts authenticate",
    async (environment) => {
      if (environment) vi.stubEnv("TESSERA_ENVIRONMENT", environment);

      const { verifyCredentials } = await accounts();

      expect(verifyCredentials("admin", "tessera-admin")).toEqual({ role: "admin" });
      expect(verifyCredentials("auditor", "tessera-auditor")).toEqual({ role: "auditor" });
      expect(verifyCredentials("collections", "tessera-collections")).toEqual({
        role: "collections",
      });
    },
  );

  it("warns that the published defaults are live, naming the tunnel it cannot detect", async () => {
    // The one case no in-process signal distinguishes from a laptop: `next dev` behind
    // cloudflared keeps NODE_ENV=development. It cannot be closed automatically, so it is
    // said out loud.
    const spy = vi.spyOn(console, "warn").mockImplementation(() => {});

    await accounts();

    const message = spy.mock.calls.flat().join(" ");
    expect(message).toContain("tessera-admin");
    expect(message).toContain("TESSERA_ENVIRONMENT=staging");
  });

  it("a wrong password is still a wrong password", async () => {
    const { verifyCredentials } = await accounts();

    expect(verifyCredentials("admin", "not-the-password")).toBeNull();
    expect(verifyCredentials("nobody", "tessera-admin")).toBeNull();
  });
});
