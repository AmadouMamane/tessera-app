import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/server/backend", () => ({
  backendHeaders: (extra: Record<string, string>) => extra,
  backendUrl: () => "http://backend.test",
}));

import { POST } from "./route";

describe("POST /api/recouvrement-assistant/message proxy", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("calls the canonical FastAPI path and returns contact_rule_v1", async () => {
    const backendResponse = {
      visibleReply: "Non, vous ne devez pas appeler M. D. à 23:00.",
      artifact: {
        id: "RC-2048-contact-rule-v1",
        type: "contact_rule_v1",
        task: "check_rule",
        title: "Cadre de contact — RC-2048",
        status: "draft",
        content: { decision: "blocked" },
      },
      cardUpdates: { contactFrame: ["Appel à 23:00 : non autorisé"] },
      suggestedActions: ["Planifier un rappel demain"],
      businessEvents: [],
      businessScores: [],
      decisions: { intent: "check_contact_rule" },
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(backendResponse), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      new Request("http://localhost:3097/api/recouvrement-assistant/message", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ message: "Je peux l'appeler à 23h ?" }),
      }) as never,
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://backend.test/recouvrement-assistant/message",
      expect.objectContaining({ method: "POST" }),
    );
    await expect(response.json()).resolves.toMatchObject({
      artifact: { type: "contact_rule_v1" },
    });
  });

  it("does not leak raw backend 404 details", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response('{"detail":"Not Found"}', {
          status: 404,
          headers: { "content-type": "application/json" },
        }),
      ),
    );

    const response = await POST(
      new Request("http://localhost:3097/api/recouvrement-assistant/message", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ message: "Comment le contacter ?" }),
      }) as never,
    );

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({
      detail: "recouvrement assistant backend unavailable",
    });
  });
});
