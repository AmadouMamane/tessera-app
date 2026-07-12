/**
 * The proxy refuses to hand personal data to a stranger (audit 2026-07-12, P1 F-4).
 *
 * `observability` sat in `ALWAYS_PUBLIC`, so `GET /api/observability/conversation-messages`
 * proxied an anonymous visitor straight through — with the service bearer attached on their
 * behalf. Pre-fix, every test in the first block below returns 200 and a transcript.
 *
 * The other half of the finding is the one that is easy to forget when fixing it: the
 * aggregate reads MUST stay public (ADR 0009), and the operator's own reads must keep
 * working, which means this proxy has to MINT the assertion the agent now demands. A fix that
 * locks the cockpit for its own operators is not a fix.
 */
import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { authMock } = vi.hoisted(() => ({ authMock: vi.fn() }));

vi.mock("@/auth", () => ({ auth: authMock }));
vi.mock("@/lib/server/backend", () => ({
  backendHeaders: (extra: Record<string, string>) => extra,
  backendUrl: () => "http://backend.test",
}));

import { isSubjectScopedPath } from "@/lib/auth/subject-paths";

import { GET } from "./route";

const SIGNING_KEY = "test-signing-key";

function get(path: string, query = ""): NextRequest {
  // A real NextRequest: the handler reads `nextUrl.search` to forward the query string.
  return new NextRequest(`http://localhost:3097/api/${path}${query}`);
}

function params(path: string): { params: Promise<{ path: string[] }> } {
  return { params: Promise.resolve({ path: path.split("/") }) };
}

function decodeAssertion(token: string): Record<string, unknown> {
  const [body] = token.split(".");
  return JSON.parse(Buffer.from(body ?? "", "base64url").toString("utf-8")) as Record<
    string,
    unknown
  >;
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.stubEnv("TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY", SIGNING_KEY);
  authMock.mockReset();
  fetchMock = vi.fn(
    async () =>
      new Response(JSON.stringify({ available: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("the transcript is not public", () => {
  const SUBJECT_SCOPED = [
    "observability/conversation-messages",
    "observability/conversations",
    "observability/session-detail",
    "observability/memory-inventory",
    "observability/replays",
    "observability/trace-snapshot",
    "observability/handoffs",
    "observability/context-overflow",
    "observability/agent-historique",
    "observability/trajectory/abc123",
    "observability/provenance/abc123",
    "observability/erasure/00000000-0000-0000-0000-000000000000",
    "memory/00000000-0000-0000-0000-000000000000/items",
  ];

  it.each(SUBJECT_SCOPED)("refuses an anonymous caller on %s", async (path) => {
    authMock.mockResolvedValue(null);

    const response = await GET(get(path), params(path));

    expect(response.status).toBe(401);
    // It refused BEFORE proxying — the agent was never asked, so the bearer was never lent.
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("refuses a customer session (no operator role) with 401", async () => {
    authMock.mockResolvedValue({ user: { name: "someone", role: undefined } });

    const path = "observability/conversation-messages";
    const response = await GET(get(path, "?conversation_id=x"), params(path));

    expect(response.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("the operator's own reads keep working", () => {
  it.each(["admin", "auditor", "superadmin", "collections"])(
    "mints a signed assertion carrying the %s principal",
    async (role) => {
      authMock.mockResolvedValue({ user: { name: "aline.durand", role } });

      const path = "observability/conversation-messages";
      const response = await GET(get(path, "?conversation_id=x"), params(path));

      expect(response.status).toBe(200);
      expect(fetchMock).toHaveBeenCalledTimes(1);

      const headers = fetchMock.mock.calls[0]?.[1]?.headers as Record<string, string>;
      const assertion = headers["X-Tessera-Operator-Assertion"];
      expect(assertion).toBeTruthy();

      const payload = decodeAssertion(assertion ?? "");
      expect(payload.principal).toBe("aline.durand");
      expect(payload.role).toBe(role);
      // The surface is derived from the role's authority, never from a client hint: the
      // business-plane role can only ever mint its own console.
      expect(payload.surface).toBe(role === "collections" ? "dedicated-ui" : "cockpit-embedded");
    },
  );

  it("the AUDITOR reads — that is its trade (ADR 0009)", async () => {
    authMock.mockResolvedValue({ user: { name: "auditor", role: "auditor" } });

    const path = "observability/session-detail";
    const response = await GET(get(path, "?conversation_id=x"), params(path));

    // The mutation plane refuses the auditor (403). The READ plane must not: an audit role
    // that cannot read what it audits is not an audit role.
    expect(response.status).toBe(200);
  });

  it("fails loudly, not silently, when the signing key is unset", async () => {
    // NOT `= undefined`: that stores the STRING "undefined", which is truthy — the key would
    // look configured and the assertion would be signed with the word "undefined".
    vi.stubEnv("TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY", undefined);
    authMock.mockResolvedValue({ user: { name: "admin", role: "admin" } });

    const path = "observability/conversation-messages";
    const response = await GET(get(path, "?conversation_id=x"), params(path));

    // 503 and a diagnosable message — never a silent proxy that the agent then 401s, which
    // would surface to the operator as "the transcript is empty".
    expect(response.status).toBe(503);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("the public aggregate surface is untouched (ADR 0009)", () => {
  const PUBLIC = [
    "observability/scores",
    "observability/snapshot",
    "observability/fleet",
    "observability/tail-sampling",
    "observability/replay-shadow",
    "observability/erasure-coverage",
    "observability/memory",
    "healthz",
    "readyz",
  ];

  it.each(PUBLIC)("proxies %s with no session at all", async (path) => {
    authMock.mockResolvedValue(null);

    const response = await GET(get(path), params(path));

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    // No assertion is minted for a public read: it carries no subject, so there is no one
    // to identify.
    const headers = fetchMock.mock.calls[0]?.[1]?.headers as Record<string, string>;
    expect(headers["X-Tessera-Operator-Assertion"]).toBeUndefined();
  });

  it("does not confuse erasure-coverage (3 integers) with erasure/{id} (a subject)", () => {
    // The trap this asserts against: a prefix match on `observability/erasure` without the
    // trailing slash would lock the public coverage counter and break the cockpit.
    expect(isSubjectScopedPath(["observability", "erasure", "some-id"])).toBe(true);
    expect(isSubjectScopedPath(["observability", "erasure-coverage"])).toBe(false);
  });

  it("does not confuse agent-console (config) with agent-console/feedback (a conversation)", () => {
    expect(isSubjectScopedPath(["observability", "agent-console"])).toBe(false);
    expect(isSubjectScopedPath(["observability", "agent-console", "feedback"])).toBe(true);
  });
});
