/**
 * The action proxy refuses anonymous and read-only callers (audit 2026-07-12, P0 F-1).
 *
 * This is the route the finding named twice: it executes governed artifact transitions
 * AND the old wire contract let the body assert `requested_by` — anonymous action,
 * spoofable attribution. Pre-fix, every test in the guard block failed: no session
 * check, service bearer attached on the caller's behalf.
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

const ARTIFACT = {
  id: "RC-2048-reminder-v1",
  type: "reminder_draft_v1",
  task: "draft_reminder",
  title: "Brouillon de relance — RC-2048",
  status: "draft",
  content: { no_external_effect: true },
};

function actionRequest(): Request {
  return new Request("http://localhost:3097/api/recouvrement-assistant/action", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      artifact: ARTIFACT,
      action_name: "insert_artifact_in_case",
      language: "en",
    }),
  });
}

function decodeAssertion(token: string): Record<string, unknown> {
  const [body] = token.split(".");
  return JSON.parse(Buffer.from(body ?? "", "base64url").toString("utf-8")) as Record<
    string,
    unknown
  >;
}

describe("POST /api/recouvrement-assistant/action — the edge gate (P0 F-1)", () => {
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

    const response = await POST(actionRequest() as never);

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      detail: "operator authentication required",
    });
    // Pre-fix this reached the agent, executed a governed transition, and wrote
    // whatever name the body claimed into the ledger.
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("refuses the auditor with 403 — an audit role that writes is not an audit role", async () => {
    authMock.mockResolvedValue({ user: { role: "auditor", name: "auditor" } });
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(actionRequest() as never);

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({
      detail: "this role is read-only on the recouvrement business plane",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("proxies a collections operator, forwarding the assertion the ledger will trust", async () => {
    authMock.mockResolvedValue({ user: { role: "collections", name: "collections" } });
    const backendResponse = {
      visibleReply:
        "Insertion préparée dans le dossier RC-2048. Aucune écriture définitive n'a encore été exécutée.",
      artifact: { ...ARTIFACT, status: "insertion_prepared" },
      cardUpdates: { summary: ["Statut : insertion_prepared"] },
      suggestedActions: ["Confirmer l'insertion"],
      businessEvents: [],
      businessScores: [],
      decisions: { artifactAction: { action_name: "insert_artifact_in_case" } },
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(backendResponse), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(actionRequest() as never);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://backend.test/recouvrement-assistant/action",
      expect.objectContaining({ method: "POST" }),
    );
    const [, requestInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = requestInit.headers as Record<string, string>;
    expect(JSON.parse(String(requestInit.body))).toMatchObject({ language: "en" });
    const token = headers["X-Tessera-Operator-Assertion"] ?? "";
    expect(token).toBeTruthy();
    // `requested_by` now travels HERE — as the assertion's verified principal, signed
    // with a key the browser never holds — not as a body field anyone could type.
    expect(decodeAssertion(token)).toMatchObject({
      principal: "collections",
      role: "collections",
      surface: "dedicated-ui",
    });
    await expect(response.json()).resolves.toMatchObject({
      artifact: { status: "insertion_prepared" },
    });
  });

  it("fails 503 with a diagnosable message when the signing key is unset", async () => {
    vi.stubEnv("TESSERA_API_OPERATOR_ASSERTION_SIGNING_KEY", "");
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    authMock.mockResolvedValue({ user: { role: "collections", name: "collections" } });
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(actionRequest() as never);

    expect(response.status).toBe(503);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does not leak raw backend action errors to an authorized caller", async () => {
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

    const response = await POST(actionRequest() as never);

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({
      detail: "recouvrement assistant backend unavailable",
    });
  });
});
