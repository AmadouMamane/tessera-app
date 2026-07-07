import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchBusinessRuns } from "./client";
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

describe("fetchBusinessRuns (recouvrement dimension filters)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads the Recouvrement run read model via the generic business-runs read", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          runs: [
            {
              agent_id: "recouvrement",
              workflow_id: "recouvrement_collections_v1",
              surface: "dedicated-ui",
              case_id: "RC-2048",
              conversation_id: "conv-1",
              turn_id: "turn-1",
              started_at: "2026-07-06T09:00:00+02:00",
              event_count: 2,
              timeline: [
                {
                  event_name: "artifact.status_changed",
                  timestamp: "2026-07-06T09:00:01+02:00",
                  agent_id: "recouvrement",
                  conversation_id: "conv-1",
                  turn_id: "turn-1",
                  workflow_id: "recouvrement_collections_v1",
                  case_id: "RC-2048",
                  artifact_id: "RC-2048-schedule-36-months-v2",
                  artifact_type: "schedule_proposal_v2",
                  artifact_status: "pending_validation",
                  decision: "prepared",
                  reason_codes: ["VALIDATION_REQUIRED", "NO_EXTERNAL_EFFECT"],
                  payload: { no_external_effect: true },
                },
              ],
              artifacts: [
                {
                  artifact_id: "RC-2048-schedule-36-months-v2",
                  artifact_type: "schedule_proposal_v2",
                  artifact_status: "pending_validation",
                  no_external_effect: true,
                },
              ],
              decisions: [
                {
                  event_name: "policy.decision_made",
                  decision: "prepared",
                  reason_codes: ["NO_EXTERNAL_EFFECT"],
                  no_external_effect: true,
                },
              ],
              sensitive_actions: [
                {
                  event_name: "action.prepared",
                  action_name: "submit_for_validation",
                  artifact_id: "RC-2048-schedule-36-months-v2",
                  artifact_type: "schedule_proposal_v2",
                  target_status: "pending_validation",
                  no_external_effect: true,
                  requires_validation: true,
                  reason_codes: ["VALIDATION_REQUIRED", "NO_EXTERNAL_EFFECT"],
                },
              ],
              scores: [
                {
                  metric: "no_uncontrolled_external_effect",
                  score: 1,
                  status: "scored",
                  reason: "no_external_effect_preserved",
                },
              ],
            },
          ],
          events: [],
          scores: [],
          as_of: null,
          agent: "recouvrement",
          workflow_id: "recouvrement_collections_v1",
          conversation_id: null,
          turn_id: null,
          case_id: null,
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchBusinessRuns(undefined, {
      agent: "recouvrement",
      workflowId: "recouvrement_collections_v1",
      limit: 30,
    });

    // ADR 0017 Phase C: recouvrement runs ride the generic dimension-filtered read directly.
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/observability/business/runs?agent=recouvrement&workflow_id=recouvrement_collections_v1&limit=30",
      expect.objectContaining({ headers: expect.objectContaining({ Accept: "application/json" }) }),
    );
    expect(result.runs[0]?.sensitive_actions[0]?.action_name).toBe("submit_for_validation");
    expect(result.runs[0]?.artifacts[0]?.no_external_effect).toBe(true);
  });
});
