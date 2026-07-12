/**
 * The message proxy refuses anonymous and read-only callers (audit 2026-07-12, P0 F-1).
 *
 * Pre-fix, every test in the guard block below failed: the handler proxied ANY caller —
 * no session check — while `backendHeaders` attached the service bearer on their behalf.
 * The upstream-behaviour tests at the bottom keep the pre-existing contract honest for
 * the callers that are allowed through.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { authMock } = vi.hoisted(() => ({ authMock: vi.fn() }));

vi.mock("@/auth", () => ({ auth: authMock }));
vi.mock("@/lib/server/backend", () => ({
  backendHeaders: (extra: Record<string, string>) => extra,
  backendUrl: () => "http://backend.test",
}));

import { POST } from "./route";

const SIGNING_KEY = "test-signing-key";

function messageRequest(): Request {
  return new Request("http://localhost:3097/api/recouvrement-assistant/message", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ case_id: "RC-2048", message: "ok puis-je l'appeler à 22h ?" }),
  });
}

function decodeAssertion(token: string): Record<string, unknown> {
  const [body] = token.split(".");
  return JSON.parse(Buffer.from(body ?? "", "base64url").toString("utf-8")) as Record<
    string,
    unknown
  >;
}

describe("POST /api/recouvrement-assistant/message — the edge gate (P0 F-1)", () => {
  beforeEach(() => {
    vi.stubEnv("TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY", SIGNING_KEY);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    authMock.mockReset();
  });

  it("refuses an anonymous caller with 401 and never contacts the backend", async () => {
    authMock.mockResolvedValue(null);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(messageRequest() as never);

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      detail: "operator authentication required",
    });
    // The refusal must happen at the edge: pre-fix, this fetch carried the service
    // bearer to the agent on the anonymous caller's behalf.
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("refuses the auditor with 403 — enters the console, does not act from it", async () => {
    authMock.mockResolvedValue({ user: { role: "auditor", name: "auditor" } });
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(messageRequest() as never);

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({
      detail: "this role is read-only on the recouvrement business plane",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("proxies a collections operator and forwards a real assertion for the agent", async () => {
    authMock.mockResolvedValue({ user: { role: "collections", name: "collections" } });
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ visibleReply: "ok" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(messageRequest() as never);

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://backend.test/recouvrement-assistant/message",
      expect.objectContaining({ method: "POST" }),
    );
    const [, requestInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = requestInit.headers as Record<string, string>;
    const token = headers["X-Tessera-Operator-Assertion"] ?? "";
    expect(token).toBeTruthy();
    // The assertion carries the VERIFIED identity the agent will trust — principal and
    // role from the session, surface fixed to recouvrement's console. This is the wire
    // fact that replaces the old body-asserted identity.
    expect(decodeAssertion(token)).toMatchObject({
      principal: "collections",
      role: "collections",
      surface: "dedicated-ui",
    });
  });

  it("fails 503 with a diagnosable message when the signing key is unset", async () => {
    vi.stubEnv("TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY", "");
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    authMock.mockResolvedValue({ user: { role: "collections", name: "collections" } });
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(messageRequest() as never);

    // Without the key the agent would refuse anyway (401) — failing HERE names the
    // actual misconfiguration instead of letting it surface as an opaque auth error.
    expect(response.status).toBe(503);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does not leak raw backend errors to an authorized caller", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    authMock.mockResolvedValue({ user: { role: "collections", name: "collections" } });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response('{"detail":"Not Found"}', {
          status: 404,
          headers: { "content-type": "application/json" },
        }),
      ),
    );

    const response = await POST(messageRequest() as never);

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({
      detail: "recouvrement assistant backend unavailable",
    });
  });
});
