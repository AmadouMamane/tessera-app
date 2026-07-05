import { describe, expect, it } from "vitest";

import {
  assistantActionFromLabel,
  createInitialTreatmentAssistantState,
  handleAssistantAction,
  handleUserMessage,
  routeUserIntent,
} from "./recouvrement-product-experience";

function contentText(value: unknown): string {
  if (Array.isArray(value)) return value.join("\n");
  if (value && typeof value === "object") return Object.values(value).map(contentText).join("\n");
  return typeof value === "string" ? value : "";
}

function artifactText(artifact: ReturnType<typeof handleUserMessage>["artifact"]): string {
  return Object.values(artifact.content).map(contentText).join("\n");
}

describe("Recouvrement treatment assistant state machine", () => {
  it("routes a free schedule request to a non-created schedule proposal artifact", () => {
    const transition = handleUserMessage(
      "Propose un échéancier pour 840 €",
      createInitialTreatmentAssistantState(),
    );

    expect(transition.routedTurn?.intent).toBe("propose_schedule");
    expect(transition.state.currentTask).toBe("propose_schedule");
    expect(transition.artifact.type).toBe("schedule_proposal");
    expect(transition.artifact.status).toBe("draft");
    expect(transition.artifact.content.scheduleItems).toEqual(
      expect.arrayContaining([
        "3 mensualités de 280,00 €",
        "4 mensualités de 210,00 €",
        "6 mensualités de 140,00 €",
        "Échéancier non créé",
      ]),
    );
  });

  it("prepares a client message from the existing schedule without erasing it", () => {
    const scheduleTransition = handleUserMessage(
      "Propose un échéancier pour 840 €",
      createInitialTreatmentAssistantState(),
    );
    const action = assistantActionFromLabel("Préparer le message", scheduleTransition.state);
    const messageTransition = handleAssistantAction(action, scheduleTransition.state);

    expect(messageTransition.artifact.type).toBe("client_message_artifact");
    expect(messageTransition.artifact.sourceArtifactId).toBe(scheduleTransition.artifact.id);
    expect(
      messageTransition.state.artifacts.some((item) => item.id === scheduleTransition.artifact.id),
    ).toBe(true);
    expect(messageTransition.artifact.content.clientMessage).toContain(
      "Une solution d'échelonnement peut être étudiée avec vous",
    );
    expect(artifactText(messageTransition.artifact)).not.toContain("Le message devrait inclure");
    expect(artifactText(messageTransition.artifact)).not.toContain(
      "Pour proposer un échéancier, nous devons considérer",
    );
  });

  it("switches from any active task to payment options for a payment-options question", () => {
    const ruleState = handleAssistantAction(
      "CHECK_CONTACT_RULE",
      createInitialTreatmentAssistantState(),
    ).state;
    const route = routeUserIntent("ok comment peut-il régler ses échéances ?", ruleState);
    const transition = handleUserMessage("ok comment peut-il régler ses échéances ?", ruleState);
    const text = artifactText(transition.artifact);

    expect(route.intent).toBe("explain_payment_options");
    expect(transition.state.currentTask).toBe("explain_payment_options");
    expect(transition.artifact.type).toBe("payment_options_v1");
    expect(text).toContain("Paiement du solde dû : 840,00 €");
    expect(text).toContain("Proposition d'échéancier à valider");
    expect(text).not.toContain("opposition carte");
    expect(text).not.toContain("numéro d'opposition");
  });

  it("rejects a 22h outbound call and proposes contact alternatives", () => {
    const transition = handleUserMessage(
      "ok puis-je l'appeler à 22h ?",
      createInitialTreatmentAssistantState(),
    );

    expect(transition.routedTurn?.intent).toBe("check_contact_rule");
    expect(transition.visibleReply).toContain("Non, vous ne devez pas appeler M. D. à 22h");
    expect(transition.visibleReply).toContain("8h et 20h");
    expect(transition.artifact.content.nextActions).toEqual(
      expect.arrayContaining([
        "Rédiger un email de confirmation",
        "Reporter le contact",
        "Voir la règle de contact",
      ]),
    );
    expect(transition.artifact.content.nextActions).not.toContain("Préparer un script d'appel");
  });

  it("marks the current artifact inserted without regenerating cards", () => {
    const scheduleTransition = handleUserMessage(
      "Propose un échéancier pour 840 €",
      createInitialTreatmentAssistantState(),
    );
    const messageTransition = handleAssistantAction(
      "PREPARE_CLIENT_MESSAGE_FROM_SCHEDULE",
      scheduleTransition.state,
    );
    const insertedTransition = handleAssistantAction(
      "INSERT_ARTIFACT_IN_CASE",
      messageTransition.state,
    );

    expect(insertedTransition.artifact.id).toBe(messageTransition.artifact.id);
    expect(insertedTransition.artifact.status).toBe("inserted");
    expect(insertedTransition.artifact.content).toBe(messageTransition.artifact.content);
    expect(insertedTransition.state.artifacts).toHaveLength(
      messageTransition.state.artifacts.length,
    );
    expect(insertedTransition.visibleReply).toBe("Message inséré dans RC-2048.");
  });

  it("marks the current artifact pending validation without automatic sending", () => {
    const scheduleTransition = handleUserMessage(
      "Propose un échéancier pour 840 €",
      createInitialTreatmentAssistantState(),
    );
    const submittedTransition = handleAssistantAction(
      "SUBMIT_FOR_VALIDATION",
      scheduleTransition.state,
    );

    expect(submittedTransition.artifact.id).toBe(scheduleTransition.artifact.id);
    expect(submittedTransition.artifact.status).toBe("pending_validation");
    expect(submittedTransition.artifact.content).toBe(scheduleTransition.artifact.content);
    expect(submittedTransition.visibleReply).toContain("Aucun envoi automatique");
  });
});
