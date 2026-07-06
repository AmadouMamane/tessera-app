import { afterEach, describe, expect, it, vi } from "vitest";

import {
  RecouvrementAssistantApiError,
  sendRecouvrementAssistantAction,
  sendRecouvrementAssistantMessage,
} from "./recouvrement-assistant";

describe("sendRecouvrementAssistantMessage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts the structured Recouvrement payload to the frontend proxy", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        visibleReply: "Vous pouvez contacter M. D. aujourd'hui entre 08:00 et 20:00.",
        artifact: {
          id: "RC-2048-contact-rule-v1",
          type: "contact_rule_v1",
          task: "check_rule",
          title: "Cadre de contact — RC-2048",
          status: "draft",
          content: {},
        },
        cardUpdates: { contactFrame: ["Dossier : RC-2048"] },
        suggestedActions: ["Préparer un script d'appel"],
        businessEvents: [],
        businessScores: [],
        decisions: {},
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await sendRecouvrementAssistantMessage({
      caseId: "RC-2048",
      message: "ok puis-je l'appeler à 22h ?",
      conversationId: "conversation-1",
      turnId: "turn-1",
      assistantState: { activeTask: "check_rule" },
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/recouvrement-assistant/message",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "Content-Type": "application/json" }),
      }),
    );
    const [, requestInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(requestInit.body))).toEqual({
      case_id: "RC-2048",
      message: "ok puis-je l'appeler à 22h ?",
      assistant_state: { activeTask: "check_rule" },
      conversation_id: "conversation-1",
      turn_id: "turn-1",
      surface: "dedicated-ui",
    });
    expect(result.artifact.type).toBe("contact_rule_v1");
  });

  it("throws a controlled sanitized error when the proxy rejects the turn", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        text: async () => '{"detail":"Not Found"}',
      }),
    );

    const promise = sendRecouvrementAssistantMessage({ message: "Comment le contacter ?" });

    await expect(promise).rejects.toThrow(
      "La vérification backend est indisponible. Aucune action n'a été exécutée.",
    );
    await expect(promise).rejects.toBeInstanceOf(RecouvrementAssistantApiError);
  });
});

describe("sendRecouvrementAssistantAction", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts governed artifact actions to the frontend proxy", async () => {
    const artifact = {
      id: "RC-2048-reminder-v1",
      type: "reminder_draft_v1",
      task: "draft_reminder",
      title: "Brouillon de relance — RC-2048",
      status: "draft",
      content: { message_sent: false },
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        visibleReply: "Insertion préparée dans le dossier RC-2048.",
        artifact: { ...artifact, status: "insertion_prepared" },
        cardUpdates: { summary: ["Statut : insertion_prepared"] },
        suggestedActions: ["Confirmer l'insertion"],
        businessEvents: [],
        businessScores: [],
        decisions: {},
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await sendRecouvrementAssistantAction({
      artifact,
      actionName: "insert_artifact_in_case",
      conversationId: "conversation-action",
      turnId: "turn-action",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/recouvrement-assistant/action",
      expect.objectContaining({ method: "POST" }),
    );
    const [, requestInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(requestInit.body))).toEqual({
      case_id: "RC-2048",
      artifact,
      action_name: "insert_artifact_in_case",
      requested_by: "Julie Dubois",
      conversation_id: "conversation-action",
      turn_id: "turn-action",
      surface: "dedicated-ui",
    });
    expect(result.artifact.status).toBe("insertion_prepared");
  });
});
