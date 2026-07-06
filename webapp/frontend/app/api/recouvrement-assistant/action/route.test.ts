import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/server/backend", () => ({
  backendHeaders: (extra: Record<string, string>) => extra,
  backendUrl: () => "http://backend.test",
}));

import { POST } from "./route";

describe("POST /api/recouvrement-assistant/action proxy", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("calls the canonical FastAPI action path and returns the governed artifact", async () => {
    const backendResponse = {
      visibleReply:
        "Insertion préparée dans le dossier RC-2048. Aucune écriture définitive n'a encore été exécutée.",
      artifact: {
        id: "RC-2048-reminder-v1",
        type: "reminder_draft_v1",
        task: "draft_reminder",
        title: "Brouillon de relance — RC-2048",
        status: "insertion_prepared",
        content: { no_external_effect: true },
      },
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

    const response = await POST(
      new Request("http://localhost:3097/api/recouvrement-assistant/action", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          artifact: backendResponse.artifact,
          action_name: "insert_artifact_in_case",
        }),
      }) as never,
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://backend.test/recouvrement-assistant/action",
      expect.objectContaining({ method: "POST" }),
    );
    await expect(response.json()).resolves.toMatchObject({
      artifact: { status: "insertion_prepared" },
    });
  });

  it("does not leak raw backend action errors", async () => {
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
      new Request("http://localhost:3097/api/recouvrement-assistant/action", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ action_name: "submit_for_validation", artifact: {} }),
      }) as never,
    );

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({
      detail: "recouvrement assistant backend unavailable",
    });
  });
});
