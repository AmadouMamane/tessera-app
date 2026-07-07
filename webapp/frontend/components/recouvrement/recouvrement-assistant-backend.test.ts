import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import {
  artifactFamilyForArtifact,
  artifactFamilyForTask,
  buildArtifactInsertionPreparedResponse,
  buildContactRuleBackendUnavailableFallback,
  buildDraftBackendUnavailableFallback,
  buildInvalidDraftEditResponse,
  buildPaymentOptionsBackendUnavailableFallback,
  buildReminderPreparedResponse,
  buildScheduleProposalDraft,
  contactRuleCards,
  footerActionsForRecouvrementArtifact,
  isRecouvrementContactRuleTurn,
  routeRecouvrementDrawerMessage,
  routeRecouvrementTaskClick,
} from "./recouvrement-assistant-backend";

describe("routeRecouvrementDrawerMessage", () => {
  it("routes real contact-rule turns to the structured backend", () => {
    expect(
      isRecouvrementContactRuleTurn("Je peux l'appeler à 22h ?", "check_contact_rule", null),
    ).toBe(true);
    expect(
      routeRecouvrementDrawerMessage(
        "Vérifie les règles applicables avant de contacter le client.",
        "draft_reminder",
        null,
      ),
    ).toMatchObject({
      targetTask: "check_contact_rule",
      backendIntent: "check_contact_rule",
      useStructuredBackend: true,
      useContactRuleBackend: true,
    });
  });

  it("detects contact-rule follow-up questions outside the active tab", () => {
    expect(
      isRecouvrementContactRuleTurn("ok puis-je l'appeler à 22h ?", "draft_reminder", null),
    ).toBe(true);
    expect(isRecouvrementContactRuleTurn("Comment le contacter ?", "draft_reminder", null)).toBe(
      true,
    );
  });

  it("lets schedule wording override the active contact-rule task", () => {
    const blockedContactArtifact = {
      id: "RC-2048-contact-rule-v1",
      type: "contact_rule_v1",
      task: "check_rule",
      title: "Cadre de contact — RC-2048",
      status: "draft",
      content: { decision: "blocked" },
    };
    const route = routeRecouvrementDrawerMessage(
      "ok puis je lui proposer un étalement sur 36 mois",
      "check_contact_rule",
      blockedContactArtifact,
    );

    expect(route).toEqual({
      targetTask: "propose_schedule",
      backendIntent: "propose_schedule",
      useStructuredBackend: true,
      useContactRuleBackend: false,
      extractedSlots: { durationMonths: 36 },
    });
    expect(
      isRecouvrementContactRuleTurn(
        "ok puis-je lui proposer un étalement sur 36 mois ?",
        "check_contact_rule",
        blockedContactArtifact,
      ),
    ).toBe(false);
  });

  it("lets payment duration wording override a relance keyword", () => {
    const route = routeRecouvrementDrawerMessage(
      "ok puis-je lui proposer une relance avec un paiement sur 24 mois ?",
      "draft_reminder",
      null,
    );

    expect(route).toEqual({
      targetTask: "propose_schedule",
      backendIntent: "propose_schedule",
      useStructuredBackend: true,
      useContactRuleBackend: false,
      extractedSlots: { durationMonths: 24 },
    });
  });

  it("routes payment-option wording to the structured backend without schedule duration", () => {
    const route = routeRecouvrementDrawerMessage(
      "comment peut-il payer et quelles sont les options de paiement ?",
      "check_contact_rule",
      {
        id: "RC-2048-contact-rule-v1",
        type: "contact_rule_v1",
        task: "check_rule",
        title: "Cadre de contact — RC-2048",
        status: "draft",
        content: { decision: "blocked" },
      },
    );

    expect(route).toEqual({
      targetTask: "explain_payment_options",
      backendIntent: "explain_payment_options",
      useStructuredBackend: true,
      useContactRuleBackend: false,
      extractedSlots: {},
    });
  });

  it("routes reminder and client-message wording to the structured backend", () => {
    expect(routeRecouvrementDrawerMessage("Rédiger une relance", "summary", null)).toMatchObject({
      targetTask: "draft_reminder",
      backendIntent: "draft_reminder",
      useStructuredBackend: true,
      useContactRuleBackend: false,
    });
    expect(
      routeRecouvrementDrawerMessage("Prépare le message client", "propose_schedule", {
        id: "RC-2048-schedule-36-months-v2",
        type: "schedule_proposal_v2",
        task: "propose_schedule",
        title: "Échéancier indicatif — 36 mois",
        status: "draft",
        content: { duration_months: 36, monthly_amount: "23,33 €" },
      }),
    ).toMatchObject({
      targetTask: "draft_reminder",
      backendIntent: "draft_reminder",
      useStructuredBackend: true,
      useContactRuleBackend: false,
    });
  });

  it("rejects empathic edits unless the current artifact is an editable message", () => {
    const route = routeRecouvrementDrawerMessage("rends-le plus empathique", "propose_schedule", {
      id: "RC-2048-schedule-36-months-v2",
      type: "schedule_proposal_v2",
      task: "propose_schedule",
      title: "Échéancier indicatif — 36 mois",
      status: "draft",
      content: { duration_months: 36, monthly_amount: "23,33 €" },
    });

    expect(route).toMatchObject({
      targetTask: "propose_schedule",
      useStructuredBackend: false,
      blockedReason: "requires_message_artifact",
    });
  });
});

describe("artifact family and task click routing", () => {
  it("routes task tabs directly to their artifact family and backend intent", () => {
    expect(artifactFamilyForTask("draft_reminder")).toBe("message");
    expect(artifactFamilyForTask("propose_schedule")).toBe("schedule");
    expect(artifactFamilyForTask("check_contact_rule")).toBe("contact_rule");
    expect(artifactFamilyForTask("explain_payment_options")).toBe("payment_options");
    expect(routeRecouvrementTaskClick("check_contact_rule")).toMatchObject({
      targetTask: "check_contact_rule",
      backendIntent: "check_contact_rule",
      useStructuredBackend: true,
    });
    expect(routeRecouvrementTaskClick("propose_schedule")).toMatchObject({
      targetTask: "propose_schedule",
      backendIntent: "propose_schedule",
      useStructuredBackend: true,
    });
    expect(routeRecouvrementTaskClick("summary")).toMatchObject({
      targetTask: "summary",
      backendIntent: "summarize_case",
      useStructuredBackend: true,
    });
    expect(routeRecouvrementTaskClick("explain_payment_options")).toMatchObject({
      targetTask: "explain_payment_options",
      backendIntent: "explain_payment_options",
      useStructuredBackend: true,
    });
  });

  it("routes case-summary wording to the structured backend", () => {
    expect(routeRecouvrementDrawerMessage("Résumer ce dossier", "draft_reminder", null)).toEqual({
      targetTask: "summary",
      backendIntent: "summarize_case",
      useStructuredBackend: true,
      useContactRuleBackend: false,
      extractedSlots: {},
    });
    expect(
      routeRecouvrementDrawerMessage(
        "que dois-je retenir sur la situation du client ?",
        "summary",
        null,
      ),
    ).toMatchObject({
      targetTask: "summary",
      backendIntent: "summarize_case",
      useStructuredBackend: true,
    });
  });

  it("classifies current artifacts without falling through to another family", () => {
    expect(
      artifactFamilyForArtifact({
        id: "RC-2048-reminder-v1",
        type: "reminder_draft_v1",
        task: "draft_reminder",
        title: "Brouillon de relance — RC-2048",
        status: "draft",
        content: {},
      }),
    ).toBe("message");
    expect(
      artifactFamilyForArtifact({
        id: "RC-2048-contact-rule-v1",
        type: "contact_rule_v1",
        task: "check_rule",
        title: "Cadre de contact — RC-2048",
        status: "draft",
        content: {},
      }),
    ).toBe("contact_rule");
    expect(
      artifactFamilyForArtifact({
        id: "RC-2048-payment-options-v1",
        type: "payment_options_v1",
        task: "explain_payment_options",
        title: "Options de paiement — RC-2048",
        status: "draft",
        content: {},
      }),
    ).toBe("payment_options");
  });
});

describe("buildScheduleProposalDraft", () => {
  it("builds a 36-month indicative schedule without backend contact routing", () => {
    const proposal = buildScheduleProposalDraft("ok puis je lui proposer un étalement sur 36 mois");

    expect(proposal.artifact.type).toBe("schedule_proposal_v2");
    expect(proposal.artifact.content.monthly_amount).toBe("23,33 €");
    expect(proposal.cardUpdates.paymentPlan).toContain("Mensualité indicative : 23,33 €");
    expect(proposal.cardUpdates.paymentPlan).toContain("Échéancier non créé");
    expect(proposal.cardUpdates.complianceChecks).toContain("Validation requise avant proposition");
    expect(proposal.suggestedActions).toEqual([
      "Ajuster la durée",
      "Comparer les options",
      "Préparer le message client",
      "Soumettre à validation",
    ]);
  });
});

describe("structured schedule backend bridge", () => {
  it("keeps schedule on the structured backend and not on contact-rule routing", () => {
    const source = readFileSync(
      join(process.cwd(), "components/recouvrement/recouvrement-product-experience.tsx"),
      "utf8",
    );

    expect(source).toContain("contentFromRecouvrementScheduleResponse");
    expect(source).toContain("contentFromRecouvrementDraftResponse");
    expect(source).toContain("usesStructuredSummaryBackend");
    expect(source).toContain("usesStructuredPaymentOptionsBackend");
    expect(source).toContain("contentFromCaseSummaryResponse(response)");
    expect(source).toContain("contentFromPaymentOptionsResponse(response)");
    expect(source).toContain('route.backendIntent === "propose_schedule"');
    expect(source).toContain('route.backendIntent === "draft_reminder"');
    expect(source).toContain('route.backendIntent === "explain_payment_options"');
    expect(source).toContain("const currentArtifact =");
    expect(source).toContain("currentArtifact,");
    expect(source).toContain("contentFromScheduleProposal(proposal)");
  });
});

describe("contactRuleCards", () => {
  it("maps backend card updates without exposing business events", () => {
    const cards = contactRuleCards({
      visibleReply: "Non, vous ne devez pas appeler M. D. à 23:00.",
      artifact: {
        id: "RC-2048-contact-rule-v1",
        type: "contact_rule_v1",
        task: "check_rule",
        title: "Cadre de contact — RC-2048",
        status: "draft",
        content: {
          decision: "blocked",
          requested_time: "23:00",
          allowed_window: "08:00-20:00",
        },
      },
      cardUpdates: {
        contactFrame: ["Appel à 23:00 : non autorisé"],
        allowedItems: ["Vous pouvez contacter M. D. aujourd'hui entre 08:00 et 20:00."],
        validationItems: ["Un appel à 23:00 n'est pas autorisé."],
        nextActions: ["Reporter le contact"],
      },
      suggestedActions: ["Préparer un rappel pour demain"],
      businessEvents: [{ event_name: "ACTION_BLOCKED" }],
      businessScores: [{ score_name: "contact_rule_compliance", value: 1 }],
      decisions: { intent: "check_contact_rule" },
    });

    expect(cards).toEqual({
      contactFrame: ["Appel à 23:00 : non autorisé"],
      allowedItems: [
        "Un contact téléphonique reste autorisé uniquement sur la plage 08:00–20:00. Aucun appel à 23:00 ne doit être préparé.",
      ],
      validationItems: ["Un appel à 23:00 n'est pas autorisé."],
      nextActions: ["Préparer un rappel pour demain"],
    });
  });

  it("builds a check-rule fallback without technical backend details", () => {
    const fallback = buildContactRuleBackendUnavailableFallback();
    const cards = contactRuleCards(fallback);

    expect(fallback.artifact.type).toBe("contact_rule_v1");
    expect(fallback.artifact.task).toBe("check_rule");
    expect(fallback.visibleReply).toBe(
      "La vérification backend est indisponible. Aucune action n'a été exécutée.",
    );
    expect(JSON.stringify(fallback)).not.toContain("404");
    expect(JSON.stringify(fallback)).not.toContain("Not Found");
    expect(cards.contactFrame).toContain("Vérification backend indisponible");
    expect(cards.validationItems).toContain(
      "Aucun appel ne doit être préparé tant que la vérification backend est indisponible.",
    );
  });
});

describe("footerActionsForRecouvrementArtifact", () => {
  it("uses blocked contact actions instead of draft actions", () => {
    expect(
      footerActionsForRecouvrementArtifact({
        id: "RC-2048-contact-rule-v1",
        type: "contact_rule_v1",
        task: "check_rule",
        title: "Cadre de contact — RC-2048",
        status: "draft",
        content: { decision: "blocked" },
      }),
    ).toEqual([
      "Préparer un rappel pour demain",
      "Rédiger un email de confirmation",
      "Reporter le contact",
      "Insérer la note dans le dossier",
    ]);
  });

  it("uses check-rule actions when the structured backend is unavailable", () => {
    expect(
      footerActionsForRecouvrementArtifact(buildContactRuleBackendUnavailableFallback().artifact),
    ).toEqual([
      "Préparer un rappel pour demain",
      "Rédiger un email de confirmation",
      "Reporter le contact",
      "Insérer la note dans le dossier",
    ]);
  });

  it("uses client-message actions for backend reminder artifacts", () => {
    expect(
      footerActionsForRecouvrementArtifact({
        id: "RC-2048-reminder-v1",
        type: "reminder_draft_v1",
        task: "draft_reminder",
        title: "Brouillon de relance — RC-2048",
        status: "draft",
        content: { message_sent: false },
      }),
    ).toEqual([
      "Modifier le message",
      "Copier le message",
      "Insérer dans le dossier",
      "Soumettre à validation",
    ]);
  });

  it("uses payment-option actions for backend payment artifacts", () => {
    expect(
      footerActionsForRecouvrementArtifact({
        id: "RC-2048-payment-options-v1",
        type: "payment_options_v1",
        task: "explain_payment_options",
        title: "Options de paiement — RC-2048",
        status: "draft",
        content: { no_payment_initiated: true },
      }),
    ).toEqual([
      "Proposer un échéancier",
      "Préparer le message client",
      "Soumettre à validation",
      "Insérer dans le dossier",
    ]);
  });

  it("keeps payment backend failures within the payment-options family", () => {
    const fallback = buildPaymentOptionsBackendUnavailableFallback();

    expect(fallback.artifact.type).toBe("payment_options_v1");
    expect(fallback.artifact.content.no_payment_initiated).toBe(true);
    expect(fallback.artifact.content.no_payment_link_created).toBe(true);
    expect(fallback.artifact.content.no_payment_link_sent).toBe(true);
    expect(fallback.artifact.content.no_schedule_created).toBe(true);
    expect(JSON.stringify(fallback)).not.toContain("Créer un brouillon");
  });

  it("does not render the internal Chat Recouvrement card anymore", () => {
    const source = readFileSync(
      join(process.cwd(), "components/recouvrement/recouvrement-product-experience.tsx"),
      "utf8",
    );

    expect(source).not.toContain("<AssistantConversationPanel");
    expect(source).not.toContain(">Chat Recouvrement<");
  });

  it("never falls back to the old generic create-draft footer", () => {
    expect(footerActionsForRecouvrementArtifact(null)).toEqual([
      "Rédiger une relance",
      "Proposer un échéancier",
      "Vérifier une règle",
    ]);
    expect(footerActionsForRecouvrementArtifact(null)).not.toContain("Créer un brouillon");
  });

  it("prepares insertion on the current artifact without generating a draft", () => {
    const response = buildArtifactInsertionPreparedResponse(
      {
        id: "RC-2048-reminder-v1",
        type: "reminder_draft_v1",
        task: "draft_reminder",
        title: "Brouillon de relance — RC-2048",
        status: "draft",
        content: { message_sent: false },
      },
      "Insérer dans le dossier",
    );

    expect(response.artifact.status).toBe("insertion_prepared");
    expect(response.artifact.content.insertion_executed).toBe(false);
    expect(response.visibleReply).toContain("Aucune écriture définitive");
    expect(JSON.stringify(response)).not.toContain("Créer un brouillon");
  });

  it("prepares a blocked-contact reminder without creating a calendar event", () => {
    const response = buildReminderPreparedResponse({
      id: "RC-2048-contact-rule-v1",
      type: "contact_rule_v1",
      task: "check_rule",
      title: "Cadre de contact — RC-2048",
      status: "draft",
      content: { decision: "blocked" },
    });

    expect(response.artifact.status).toBe("reminder_prepared");
    expect(response.artifact.content.calendar_event_created).toBe(false);
    expect(response.artifact.content.no_external_effect).toBe(true);
    expect(response.visibleReply).toContain("Aucun événement calendrier réel");
  });

  it("keeps backend failures within the same covered task family", () => {
    const draftFallback = buildDraftBackendUnavailableFallback({
      id: "RC-2048-schedule-36-months-v2",
      type: "schedule_proposal_v2",
      task: "propose_schedule",
      title: "Échéancier indicatif — 36 mois",
      status: "draft",
      content: { duration_months: 36 },
    });
    const invalidEdit = buildInvalidDraftEditResponse(draftFallback.artifact);

    expect(draftFallback.artifact.type).toBe("client_message_artifact");
    expect(draftFallback.artifact.content.schedule_created).toBe(false);
    expect(draftFallback.artifact.content.message_sent).toBe(false);
    expect(invalidEdit.decisions?.decision).toBe("requires_message_artifact");
    expect(JSON.stringify(draftFallback)).not.toContain("Réponse au client générique");
  });

  it("does not route backend contact failures through the legacy draft stream", () => {
    const source = readFileSync(
      join(process.cwd(), "components/recouvrement/recouvrement-product-experience.tsx"),
      "utf8",
    );

    expect(source).toContain("buildContactRuleBackendUnavailableFallback");
    expect(source).not.toContain(
      "Backend Recouvrement indisponible, reprise avec la logique front",
    );
  });

  it("labels deterministic contact-rule actions as verification, not generation", () => {
    const source = readFileSync(
      join(process.cwd(), "components/recouvrement/recouvrement-product-experience.tsx"),
      "utf8",
    );

    expect(source).toContain("Règle de contact vérifiée pour RC-2048.");
    expect(source).toContain("Action de contact bloquée pour RC-2048.");
    expect(source).toContain('hasContactRuleArtifact ? "Revérifier" : "Régénérer"');
    expect(source).not.toContain("Voici une proposition adaptée au dossier RC-2048.");
  });

  it("keeps footer buttons on the action dispatcher instead of free-text chat", () => {
    const source = readFileSync(
      join(process.cwd(), "components/recouvrement/recouvrement-product-experience.tsx"),
      "utf8",
    );

    expect(source).toContain("handleAssistantAction");
    expect(source).toContain("sendRecouvrementAssistantAction");
    expect(source).toContain("buildArtifactInsertionPreparedResponse");
    expect(source).toContain('runBackendArtifactAction("insert_artifact_in_case"');
    expect(source).toContain('runBackendArtifactAction("submit_for_validation"');
    expect(source).toContain('runBackendArtifactAction("prepare_reminder_tomorrow"');
    expect(source).toContain('forcedTask: "check_contact_rule"');
    expect(source).toContain('forcedTask: "propose_schedule"');
    expect(source).toContain('forcedTask: "draft_reminder"');
  });

  it("keeps the thinking animation visible for deterministic turns", () => {
    const source = readFileSync(
      join(process.cwd(), "components/recouvrement/recouvrement-product-experience.tsx"),
      "utf8",
    );
    const styles = readFileSync(join(process.cwd(), "app/globals.css"), "utf8");

    expect(source).toContain("MIN_ASSISTANT_THINKING_MS = 1800");
    expect(source).toContain("completeAfterThinkingMinimum");
    expect(source).toContain("Recouvrement réfléchit");
    expect(source).toContain("AssistantThinkingIndicator");
    expect(source).toContain("recouvrement-assistant-bloom");
    expect(source).toContain("recouvrement-thinking-dot");
    expect(styles).toContain("@keyframes recouvrement-bloom-breathe");
    expect(styles).toContain("@keyframes recouvrement-dot-wave");
  });
});
