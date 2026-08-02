import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import {
  artifactFamilyForArtifact,
  artifactFamilyForTask,
  buildArtifactInsertionPreparedResponse,
  buildArtifactPendingValidationResponse,
  buildCaseSummaryDraft,
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
    expect(source).toContain("contentFromScheduleProposal(proposal, copy)");
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

  it("builds the dynamic blocked-window sentence in the selected locale", () => {
    const response = {
      visibleReply: "blocked",
      artifact: {
        id: "RC-2048-contact-rule-v1",
        type: "contact_rule_v1",
        task: "check_rule",
        title: "Contact rule — RC-2048",
        status: "draft",
        content: { decision: "blocked", requested_time: "23:00", allowed_window: "08:00-20:00" },
      },
      cardUpdates: {},
      suggestedActions: [],
      businessEvents: [],
      businessScores: [],
      decisions: {},
    };

    expect(contactRuleCards(response, "en").allowedItems).toEqual([
      "Phone contact remains permitted only within 08:00–20:00. No call at 23:00 may be prepared.",
    ]);
    expect(contactRuleCards(response, "de").allowedItems).toEqual([
      "Telefonischer Kontakt bleibt nur im Zeitfenster 08:00–20:00 zulässig. Für 23:00 darf kein Anruf vorbereitet werden.",
    ]);
  });
});

describe("footerActionsForRecouvrementArtifact", () => {
  it("localizes generated footer actions without changing their business meaning", () => {
    const artifact = {
      id: "RC-2048-schedule-v2",
      type: "schedule_proposal_v2",
      task: "propose_schedule",
      title: "Schedule — RC-2048",
      status: "draft",
      content: {},
    };

    expect(footerActionsForRecouvrementArtifact(artifact, "en")).toEqual([
      "Adjust duration",
      "Compare options",
      "Prepare customer message",
      "Submit for approval",
    ]);
    expect(footerActionsForRecouvrementArtifact(artifact, "de")).toEqual([
      "Laufzeit anpassen",
      "Optionen vergleichen",
      "Kundennachricht vorbereiten",
      "Zur Freigabe einreichen",
    ]);
  });

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

    expect(source).toContain("copy.ui.verifiedResult");
    expect(source).toContain("copy.ui.blockedResult");
    expect(source).toContain("hasContactRuleArtifact ? copy.ui.recheck : copy.ui.regenerate");
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
    expect(source).toContain("copy.ui.thinking");
    expect(source).toContain("AssistantThinkingIndicator");
    expect(source).toContain("recouvrement-assistant-bloom");
    expect(source).toContain("recouvrement-thinking-dot");
    expect(styles).toContain("@keyframes recouvrement-bloom-breathe");
    expect(styles).toContain("@keyframes recouvrement-dot-wave");
  });
});

describe("localized Recouvrement fallbacks", () => {
  it.each(["en", "de"] as const)("does not leak French business copy in %s", (locale) => {
    const artifact = {
      id: "RC-2048-reminder-v1",
      type: "reminder_draft_v1",
      task: "draft_reminder",
      title: locale === "en" ? "Reminder draft — RC-2048" : "Mahnungsentwurf — RC-2048",
      status: "draft",
      content: { message_sent: false },
    };
    const outputs = [
      buildScheduleProposalDraft("3 months", 3, locale),
      buildCaseSummaryDraft(locale),
      buildContactRuleBackendUnavailableFallback(locale),
      buildDraftBackendUnavailableFallback(artifact, locale),
      buildPaymentOptionsBackendUnavailableFallback(locale),
      buildInvalidDraftEditResponse(null, locale),
      buildArtifactInsertionPreparedResponse(artifact, "insert", locale),
      buildArtifactPendingValidationResponse(artifact, "submit", locale),
      buildReminderPreparedResponse(artifact, locale),
    ];

    expect(JSON.stringify(outputs)).not.toMatch(
      /\b(?:dossier|échéancier|relance|paiement|aucun|aucune|préparé|validation requise|montant dû|retard|mensualité|durée demandée|soumettre|insérer|vérification indisponible)\b/i,
    );
  });
});

// A CLICK IS A DECLARATION, AND A DECLARATION IS NOT A GUESS.
//
// The drawer's five buttons name the capability they invoke, and until 2026-08-02 that name
// was thrown away: the agent re-derived the intent by matching regexes against the button's
// own prose, so "Résumer ce dossier" (whose prompt ends "…pour préparer l'action suivante")
// came back as a reminder draft, and the drawer's opening turn came back as a payment
// schedule. Reproduced on http://localhost:3097 AND on the deployed host before the fix.
describe("declared intent", () => {
  it("mints a declaration for every task click and for no free-text turn", () => {
    const tasks = [
      "summary",
      "draft_reminder",
      "propose_schedule",
      "check_contact_rule",
      "explain_payment_options",
    ] as const;
    for (const task of tasks) {
      const route = routeRecouvrementTaskClick(task);
      expect(route.declaredIntent).toBe(route.backendIntent);
      expect(route.declaredIntent).toBeDefined();
    }
    // Free text concludes; it never declares — the agent's classifier stays the authority.
    for (const message of [
      "Résume ce dossier",
      "Rédige une relance amiable",
      "Propose un échéancier sur 6 mois",
      "Peut-on appeler le client à 21h ?",
    ]) {
      expect(
        routeRecouvrementDrawerMessage(message, "draft_reminder", null).declaredIntent,
      ).toBeUndefined();
    }
  });

  it("no longer reads a bare generic verb as a request for a draft", () => {
    // The exact FR/EN/DE prompts behind the "Résumer" button. Each one contains only a
    // generic verb (préparer / prepare / vorbereiten) and must not route to a draft.
    for (const prompt of [
      "Résume ce dossier de recouvrement pour préparer l'action suivante.",
      "Summarise this collections case to prepare the next action.",
      "Fassen Sie diesen Inkassovorgang zusammen, um die nächste Aktion vorzubereiten.",
    ]) {
      expect(routeRecouvrementDrawerMessage(prompt, "summary", null).targetTask).not.toBe(
        "draft_reminder",
      );
    }
    // And a real draft request still is one — the object, not the verb, carries the intent.
    expect(
      routeRecouvrementDrawerMessage("Rédige une relance amiable", "summary", null).targetTask,
    ).toBe("draft_reminder");
  });

  it("keeps the draft vocabulary in lockstep with the agent's", () => {
    // Two classifiers, one question. When they disagree the front parses one artifact family
    // while the agent returns another, which is the visible half of the same bug. So the two
    // alternations are read from the two real files and compared, not restated here.
    const alternatives = (source: string, open: string, close: string): Set<string> => {
      const start = source.indexOf(open);
      const end = source.indexOf(close, start);
      expect(start).toBeGreaterThan(-1);
      expect(end).toBeGreaterThan(start);
      return new Set(source.slice(start + open.length, end).split("|"));
    };
    const tsSource = readFileSync(
      join(process.cwd(), "components/recouvrement/recouvrement-assistant-backend.ts"),
      "utf8",
    );
    const tsBody = tsSource.slice(tsSource.indexOf("function hasDraftIntent"));
    const tsWords = alternatives(tsBody, "/\\b(", ")\\b/");

    const pySource = readFileSync(
      join(process.cwd(), "../../src/tessera/agent/recouvrement.py"),
      "utf8",
    );
    const pyStart = pySource.indexOf("def _has_draft_intent");
    expect(pyStart).toBeGreaterThan(-1);
    const pyBody = pySource.slice(pyStart, pySource.indexOf("def _has_summary_intent"));
    // Concatenate the adjacent raw-string literals exactly as Python does.
    const pyPattern = (pyBody.match(/r"((?:[^"\\]|\\.)*)"/g) ?? [])
      .map((literal) => literal.slice(2, -1))
      .join("");
    const pyWords = alternatives(pyPattern, "\\b(", ")\\b");

    expect([...tsWords].sort()).toEqual([...pyWords].sort());
    // The words the bug was made of must be in neither.
    for (const generic of ["prepare", "preparer", "write", "vorbereiten"]) {
      expect(tsWords.has(generic)).toBe(false);
      expect(pyWords.has(generic)).toBe(false);
    }
  });

  it("forwards the declaration to the agent, and only that one", () => {
    // Source witness, said out loud: the drawer component is a 2 700-line client component
    // whose turn loop is not reachable without a full render + network double. What is
    // pinned here is the WIRING — that the field sent is the route's declaration, never a
    // re-derivation at the call site. The behaviour itself is pinned agent-side by
    // tests/unit/test_recouvrement_declared_intent.py, which replays the real prompts.
    const source = readFileSync(
      join(process.cwd(), "components/recouvrement/recouvrement-product-experience.tsx"),
      "utf8",
    );
    expect(source).toContain("declaredIntent: route.declaredIntent");
    expect(source).not.toContain("declaredIntent: route.backendIntent");
  });

  it("parses the response by the artifact returned, not by the intent hoped for", () => {
    const source = readFileSync(
      join(process.cwd(), "components/recouvrement/recouvrement-product-experience.tsx"),
      "utf8",
    );
    expect(source).toContain("const returnedFamily = artifactFamilyForArtifact(response.artifact)");
    expect(source).toContain("returnedFamily ?? artifactFamilyForTask(route.targetTask)");
  });
});

describe("editing versus creating a draft", () => {
  const scheduleArtifact = {
    id: "RC-2048-schedule-3-months-v2",
    type: "schedule_proposal_v2",
    task: "propose_schedule",
    title: "Échéancier indicatif — 3 mois",
    status: "draft",
    content: { duration_months: 3 },
  };

  it("still refuses a tone-only edit when nothing editable is on screen", () => {
    for (const message of ["rends-le plus empathique", "version courte", "modifie le message"]) {
      expect(
        routeRecouvrementDrawerMessage(message, "propose_schedule", scheduleArtifact),
        message,
      ).toMatchObject({ blockedReason: "requires_message_artifact" });
    }
  });

  it("answers a creation that merely carries a tone", () => {
    // "Rédige une relance empathique" is not an edit: it names what to write. It used to be
    // refused with "commencez par un message" because the word "empathique" alone decided.
    for (const message of [
      "Rédige une relance empathique",
      "Prépare un message client en version courte",
      "Write an empathetic reminder",
    ]) {
      const route = routeRecouvrementDrawerMessage(message, "check_contact_rule", {
        ...scheduleArtifact,
        type: "contact_rule_v1",
        task: "check_rule",
      });
      expect(route.blockedReason, message).toBeUndefined();
      expect(route.targetTask, message).toBe("draft_reminder");
    }
  });
});
