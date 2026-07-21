import type { Locale } from "@/i18n/routing";
import type {
  RecouvrementAssistantArtifact,
  RecouvrementAssistantResponse,
} from "@/lib/api/recouvrement-assistant";
// ADR 0018 §C: the backend intent vocabulary is generated from the AgentSpec
// capabilities, not hand-listed here (regenerate: scripts/generate_agent_enums.py).
import {
  RECOUVREMENT_ARTIFACT_CAPABILITY,
  type RecouvrementArtifactType,
  type RecouvrementIntent,
} from "./recouvrement-enums.generated";
import { localizeRecouvrementFallback } from "./recouvrement-fallback-i18n";

export type RecouvrementDrawerTask =
  | "summary"
  | "draft_reminder"
  | "propose_schedule"
  | "check_contact_rule"
  | "explain_payment_options";

export type RecouvrementBackendIntent = RecouvrementIntent;

export type RecouvrementArtifactFamily =
  | "summary"
  | "message"
  | "schedule"
  | "contact_rule"
  | "payment_options";

export interface RecouvrementDrawerStateModel {
  currentTask: RecouvrementDrawerTask;
  currentArtifact: RecouvrementAssistantArtifact | null;
  artifactHistory: RecouvrementAssistantArtifact[];
  selectedArtifactFamily: RecouvrementArtifactFamily | null;
  pendingAction: string | null;
  lastSuccessfulBackendIntent: RecouvrementBackendIntent | null;
}

export interface RecouvrementDrawerRoute {
  targetTask: RecouvrementDrawerTask;
  backendIntent?: RecouvrementBackendIntent;
  useStructuredBackend: boolean;
  useContactRuleBackend: boolean;
  blockedReason?: "requires_message_artifact";
  extractedSlots: {
    durationMonths?: number;
  };
}

export interface ScheduleProposalDraft {
  visibleReply: string;
  artifact: RecouvrementAssistantArtifact;
  cardUpdates: Record<string, string[]>;
  suggestedActions: string[];
}

const CONTACT_RULE_UNAVAILABLE_REPLY =
  "La vérification backend est indisponible. Aucune action n'a été exécutée.";
const CASE_AMOUNT = 840;

function normalizeDrawerMessage(message: string): string {
  return message
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

function extractDurationMonths(message: string): number | undefined {
  const normalized = normalizeDrawerMessage(message);
  const match = normalized.match(
    /\b(\d{1,3})\s*(?:mois|mensualite|mensualites|months?|instalments?|installments?|monate|monaten|raten)\b/,
  );
  if (!match?.[1]) return undefined;
  const months = Number.parseInt(match[1], 10);
  return Number.isFinite(months) && months > 0 ? months : undefined;
}

function formatEuroAmount(value: number): string {
  return `${value.toFixed(2).replace(".", ",")} €`;
}

function hasScheduleIntent(normalized: string): boolean {
  return /\b(echeancier|etalement|etaler|mensualite|mensualites|mois|paiement|payer|regler|regulariser|duree|payment plan|instalment|installment|monthly payment|months?|repayment|zahlungsplan|ratenplan|rate|raten|monate|laufzeit|tilgung)\b/.test(
    normalized,
  );
}

function hasPaymentOptionsIntent(normalized: string): boolean {
  return /\b(options? de paiement|moyens? de paiement|comment peut[- ]?il payer|comment peut[- ]?il regler|paiement total|paiement partiel|paiement en plusieurs fois|echeancier possible|alternatives? de reglement|solution de paiement|options? de reglement|moyens? de reglement|payment options?|payment methods?|ways? to pay|full payment|partial payment|settlement options?|zahlungsoptionen?|zahlungsarten?|zahlungsmoeglichkeiten|vollzahlung|teilzahlung)\b/.test(
    normalized,
  );
}

function hasContactRuleIntent(normalized: string): boolean {
  const hasContactAction =
    /\b(appel|appeler|telephone|telephoner|contacter|contact|joindre|email|mail|call|phone|contact|reach|anrufen|telefon|kontaktieren|erreichen)\b/.test(
      normalized,
    );
  const hasRuleSignal =
    /\b(regle|regles|autorise|autorisation|interdit|peux|peut|puis|comment|quand|heure|plage|cadre|conforme|conformite|rule|rules|allowed|authorised|authorized|forbidden|may|can|when|time|window|compliant|regel|regeln|erlaubt|zulaessig|verboten|wann|uhrzeit|zeitfenster|konform)\b/.test(
      normalized,
    ) || /(?:[01]?\d|2[0-3])(?:h|:)/.test(normalized);

  return (
    /\b(regle de contact|cadre de contact|contact rule|contact window|kontaktregel|kontaktzeitfenster)\b/.test(
      normalized,
    ) ||
    (hasContactAction && hasRuleSignal)
  );
}

function hasDraftIntent(normalized: string): boolean {
  return /\b(relance|message client|brouillon|email|mail|courrier|rediger|redige|prepare|preparer|version courte|empathique|modifier|modifie|rends-le|rend le|reminder|customer message|client message|draft|write|prepare|short version|empathetic|edit|mahnung|kundennachricht|entwurf|schreiben|vorbereiten|kurze version|einfuehlsam|aendern)\b/.test(
    normalized,
  );
}

function hasDraftEditIntent(normalized: string): boolean {
  return /\b(version courte|empathique|modifier|modifie|rends-le|rend le|short version|empathetic|edit|rewrite|kurze version|einfuehlsam|aendern|umschreiben)\b/.test(
    normalized,
  );
}

function hasSummaryIntent(normalized: string): boolean {
  return /\b(resume|resumer|synthese|synthetise|points cles|prioritaire|priorite|situation du client|que dois je retenir|a retenir|summary|summarise|summarize|key points|priority|customer situation|fallzusammenfassung|zusammenfassen|kernpunkte|prioritaet|kundensituation)\b/.test(
    normalized,
  );
}

/**
 * The ONE hand-written thing left, and it is genuinely a UI concern: what a capability's
 * artifacts are *called* in the drawer. Keyed by the generated intent union, so adding a
 * capability to `agents.yaml` fails typecheck here until its family is named — the manifest
 * drives exhaustiveness instead of the frontend re-listing a vocabulary it does not own.
 */
const FAMILY_BY_CAPABILITY = {
  summarize_case: "summary",
  draft_reminder: "message",
  propose_schedule: "schedule",
  check_contact_rule: "contact_rule",
  explain_payment_options: "payment_options",
} as const satisfies Record<RecouvrementIntent, RecouvrementArtifactFamily>;

export function artifactFamilyForArtifact(
  artifact: RecouvrementAssistantArtifact | null,
): RecouvrementArtifactFamily | null {
  if (!artifact) return null;
  // Which capability declares this artifact type is a manifest fact (`output_artifacts`),
  // not a frontend if-chain. An artifact type nobody declares is `null` — honest, not guessed.
  const capability =
    RECOUVREMENT_ARTIFACT_CAPABILITY[artifact.type as RecouvrementArtifactType] ?? null;
  return capability ? FAMILY_BY_CAPABILITY[capability] : null;
}

export function artifactFamilyForTask(task: RecouvrementDrawerTask): RecouvrementArtifactFamily {
  // The drawer's `summary` task is `summarize_case` under its UI name; every other task IS
  // the capability id.
  return FAMILY_BY_CAPABILITY[task === "summary" ? "summarize_case" : task];
}

export function isEditableMessageArtifact(artifact: RecouvrementAssistantArtifact | null): boolean {
  return artifactFamilyForArtifact(artifact) === "message";
}

export function backendIntentForTask(
  task: RecouvrementDrawerTask,
): RecouvrementBackendIntent | undefined {
  // A drawer task IS a declared capability; only `summary` wears a UI name. The four-branch
  // if-chain was a hand-written copy of the manifest's own vocabulary.
  return task === "summary" ? "summarize_case" : task;
}

export function routeRecouvrementTaskClick(task: RecouvrementDrawerTask): RecouvrementDrawerRoute {
  const backendIntent = backendIntentForTask(task);
  return {
    targetTask: task,
    backendIntent,
    useStructuredBackend: backendIntent !== undefined,
    useContactRuleBackend: backendIntent === "check_contact_rule",
    extractedSlots: {},
  };
}

export function routeRecouvrementDrawerMessage(
  message: string,
  currentTask: RecouvrementDrawerTask,
  currentArtifact?: RecouvrementAssistantArtifact | null,
): RecouvrementDrawerRoute {
  const normalized = normalizeDrawerMessage(message);
  const durationMonths = extractDurationMonths(message);
  const paymentOptionsIntent = hasPaymentOptionsIntent(normalized);

  if (hasDraftEditIntent(normalized) && !isEditableMessageArtifact(currentArtifact ?? null)) {
    return {
      targetTask: currentTask,
      useStructuredBackend: false,
      useContactRuleBackend: false,
      blockedReason: "requires_message_artifact",
      extractedSlots: {},
    };
  }

  if (hasScheduleIntent(normalized) && (durationMonths || !paymentOptionsIntent)) {
    return {
      targetTask: "propose_schedule",
      backendIntent: "propose_schedule",
      useStructuredBackend: true,
      useContactRuleBackend: false,
      extractedSlots: { durationMonths },
    };
  }

  if (paymentOptionsIntent) {
    return {
      targetTask: "explain_payment_options",
      backendIntent: "explain_payment_options",
      useStructuredBackend: true,
      useContactRuleBackend: false,
      extractedSlots: {},
    };
  }

  if (hasDraftIntent(normalized)) {
    return {
      targetTask: "draft_reminder",
      backendIntent: "draft_reminder",
      useStructuredBackend: true,
      useContactRuleBackend: false,
      extractedSlots: {},
    };
  }

  if (hasContactRuleIntent(normalized)) {
    return {
      targetTask: "check_contact_rule",
      backendIntent: "check_contact_rule",
      useStructuredBackend: true,
      useContactRuleBackend: true,
      extractedSlots: {},
    };
  }

  if (hasSummaryIntent(normalized)) {
    return {
      targetTask: "summary",
      backendIntent: "summarize_case",
      useStructuredBackend: true,
      useContactRuleBackend: false,
      extractedSlots: {},
    };
  }

  const backendIntent = backendIntentForTask(currentTask);
  if (backendIntent) {
    return {
      targetTask: currentTask,
      backendIntent,
      useStructuredBackend: true,
      useContactRuleBackend: backendIntent === "check_contact_rule",
      extractedSlots: {},
    };
  }

  return {
    targetTask: currentTask,
    useStructuredBackend: false,
    useContactRuleBackend: false,
    extractedSlots: {},
  };
}

export function isRecouvrementContactRuleTurn(
  message: string,
  currentTask: RecouvrementDrawerTask,
  currentArtifact?: RecouvrementAssistantArtifact | null,
): boolean {
  return routeRecouvrementDrawerMessage(message, currentTask, currentArtifact)
    .useContactRuleBackend;
}

export function buildScheduleProposalDraft(
  message: string,
  durationMonths = extractDurationMonths(message) ?? 3,
  locale: Locale = "fr",
): ScheduleProposalDraft {
  const monthlyAmount = CASE_AMOUNT / durationMonths;
  const monthlyAmountLabel = formatEuroAmount(monthlyAmount);
  const title = `Échéancier indicatif — ${durationMonths} mois`;
  const paymentPlan = [
    title,
    "Montant dû : 840,00 €",
    `Durée demandée : ${durationMonths} mois`,
    `Mensualité indicative : ${monthlyAmountLabel}`,
    "Statut : validation requise avant proposition",
    "Échéancier non créé",
  ];
  const suggestedActions = [
    "Ajuster la durée",
    "Comparer les options",
    "Préparer le message client",
    "Soumettre à validation",
  ];

  return localizeRecouvrementFallback(
    {
      visibleReply: `Pour RC-2048, un étalement sur ${durationMonths} mois représenterait environ ${monthlyAmountLabel} par mois pour un montant dû de 840,00 €. Cette proposition reste indicative, nécessite validation avant d'être proposée au client, et aucun échéancier n'a été créé.`,
      artifact: {
        id: `RC-2048-schedule-${durationMonths}-months-v2`,
        type: "schedule_proposal_v2",
        task: "propose_schedule",
        title,
        status: "draft",
        content: {
          case_id: "RC-2048",
          amount_due: "840,00 €",
          duration_months: durationMonths,
          monthly_amount: monthlyAmountLabel,
          validation_required: true,
          created: false,
        },
      },
      cardUpdates: {
        context: [
          "Dossier : RC-2048",
          "Client : M. D.",
          "Montant dû : 840,00 €",
          "Retard : 32 jours",
          "Échéancier indicatif uniquement après validation",
        ],
        summary: [
          `Étalement demandé : ${durationMonths} mois`,
          `Mensualité indicative : ${monthlyAmountLabel}`,
          "Validation requise avant proposition au client",
          "Échéancier non créé",
        ],
        paymentPlan,
        complianceChecks: [
          "Validation requise avant proposition",
          "Accord client nécessaire avant création",
          "Échéancier non créé",
          "Montant total conservé : 840,00 €",
        ],
        nextActions: suggestedActions,
      },
      suggestedActions,
    },
    locale,
  );
}

export function buildCaseSummaryDraft(locale: Locale = "fr"): ScheduleProposalDraft {
  const suggestedActions = ["Rédiger une relance", "Proposer un échéancier", "Vérifier une règle"];

  return localizeRecouvrementFallback(
    {
      visibleReply:
        "Voici le résumé opérationnel de RC-2048 : M. D. doit 840,00 €, le retard est de 32 jours et la promesse de paiement du 12 juin n'a pas été tenue.",
      artifact: {
        id: "RC-2048-summary-v1",
        type: "case_summary_v1",
        task: "summary",
        title: "Résumé du dossier — RC-2048",
        status: "ready",
        content: {
          case_id: "RC-2048",
          client: "M. D.",
          amount_due: "840,00 €",
          days_late: 32,
          promise_status: "Promesse de paiement non tenue le 12 juin",
        },
      },
      cardUpdates: {
        summary: [
          "Dossier : RC-2048",
          "Client : M. D.",
          "Montant dû : 840,00 €",
          "Retard : 32 jours",
          "Promesse de paiement non tenue le 12 juin",
        ],
        complianceChecks: [
          "Contexte dossier conservé",
          "Aucune action exécutée",
          "Aucun message client généré",
        ],
        nextActions: suggestedActions,
      },
      suggestedActions,
    },
    locale,
  );
}

export function buildContactRuleBackendUnavailableFallback(
  locale: Locale = "fr",
): RecouvrementAssistantResponse {
  const suggestedActions = [
    "Préparer un rappel pour demain",
    "Rédiger un email de confirmation",
    "Reporter le contact",
    "Insérer la note dans le dossier",
  ];

  return localizeRecouvrementFallback(
    {
      visibleReply: CONTACT_RULE_UNAVAILABLE_REPLY,
      artifact: {
        id: "RC-2048-contact-rule-unavailable",
        type: "contact_rule_v1",
        task: "check_rule",
        title: "Cadre de contact — RC-2048",
        status: "unavailable",
        content: {
          decision: "blocked",
          contact_status: "Vérification indisponible",
          reason_codes: ["BACKEND_UNAVAILABLE"],
        },
      },
      cardUpdates: {
        contactFrame: [
          "Dossier : RC-2048",
          "Client : M. D.",
          "Vérification backend indisponible",
          "Aucune action exécutée",
        ],
        allowedItems: [
          "Le cadre connu indique une plage 08:00–20:00, mais la règle n'a pas été revérifiée.",
        ],
        validationItems: [
          "Aucun appel ne doit être préparé tant que la vérification backend est indisponible.",
        ],
        nextActions: suggestedActions,
      },
      suggestedActions,
      businessEvents: [],
      businessScores: [],
      decisions: {
        intent: "check_contact_rule",
        decision: "backend_unavailable",
      },
    },
    locale,
  );
}

export function buildDraftBackendUnavailableFallback(
  currentArtifact?: RecouvrementAssistantArtifact | null,
  locale: Locale = "fr",
): RecouvrementAssistantResponse {
  const fromSchedule = currentArtifact?.type === "schedule_proposal_v2";
  const suggestedActions = [
    "Modifier le message",
    "Copier le message",
    "Insérer dans le dossier",
    "Soumettre à validation",
  ];
  const message =
    "La préparation backend du message est indisponible. Aucun message n'a été envoyé et aucun échéancier n'a été créé.";

  return localizeRecouvrementFallback(
    {
      visibleReply: message,
      artifact: {
        id: fromSchedule ? "RC-2048-client-message-unavailable" : "RC-2048-reminder-unavailable",
        type: fromSchedule ? "client_message_artifact" : "reminder_draft_v1",
        task: "draft_reminder",
        title: fromSchedule ? "Message client préparé — RC-2048" : "Brouillon de relance — RC-2048",
        status: "unavailable",
        content: {
          message_sent: false,
          schedule_created: false,
          validation_required: fromSchedule,
          source_artifact_id: currentArtifact?.id ?? null,
        },
      },
      cardUpdates: {
        summary: [
          "Dossier : RC-2048",
          "Client : M. D.",
          "Préparation backend indisponible",
          "Aucun message envoyé",
        ],
        clientMessage: [message],
        draftVersionLabel: ["Action non disponible"],
        complianceChecks: [
          "Aucun message envoyé",
          "Aucun échéancier créé",
          fromSchedule ? "Validation requise avant toute proposition" : "Aucune action exécutée",
        ],
        nextActions: suggestedActions,
      },
      suggestedActions,
      businessEvents: [],
      businessScores: [],
      decisions: {
        intent: "draft_reminder",
        decision: "backend_unavailable",
      },
    },
    locale,
  );
}

export function buildPaymentOptionsBackendUnavailableFallback(
  locale: Locale = "fr",
): RecouvrementAssistantResponse {
  const suggestedActions = [
    "Proposer un échéancier",
    "Préparer le message client",
    "Soumettre à validation",
    "Insérer dans le dossier",
  ];
  const visibleReply =
    "La préparation backend des options de paiement est indisponible. Aucun paiement n'a été initié et aucune action client n'a été exécutée.";
  return localizeRecouvrementFallback(
    {
      visibleReply,
      artifact: {
        id: "RC-2048-payment-options-unavailable",
        type: "payment_options_v1",
        task: "explain_payment_options",
        title: "Options de paiement — RC-2048",
        status: "unavailable",
        content: {
          no_payment_initiated: true,
          no_payment_link_created: true,
          no_payment_link_sent: true,
          no_schedule_created: true,
          no_external_effect: true,
        },
      },
      cardUpdates: {
        summary: [
          "Dossier : RC-2048",
          "Options de paiement indisponibles côté backend",
          "Aucun paiement initié",
          "Aucun lien de paiement créé ou envoyé",
          "Aucun échéancier créé",
        ],
        paymentOptions: [
          "Options à confirmer selon les moyens disponibles dans le dossier.",
          "Échéancier indicatif uniquement après validation interne et accord client.",
        ],
        complianceChecks: [
          "Aucun paiement initié",
          "Aucun lien de paiement créé",
          "Aucun lien de paiement envoyé",
          "Aucun échéancier créé",
          "Aucune action client exécutée",
        ],
        nextActions: suggestedActions,
      },
      suggestedActions,
      businessEvents: [],
      businessScores: [],
      decisions: {
        intent: "explain_payment_options",
        decision: "backend_unavailable",
      },
    },
    locale,
  );
}

export function buildInvalidDraftEditResponse(
  currentArtifact: RecouvrementAssistantArtifact | null,
  locale: Locale = "fr",
): RecouvrementAssistantResponse {
  const family = artifactFamilyForArtifact(currentArtifact);
  const suggestedActions = [
    "Rédiger une relance",
    "Préparer le message client",
    "Conserver l'artefact actuel",
  ];
  return localizeRecouvrementFallback(
    {
      visibleReply:
        "Cette modification s'applique à un brouillon de relance ou à un message client. Aucun nouvel artefact n'a été généré.",
      artifact: currentArtifact ?? {
        id: "RC-2048-action-unavailable",
        type: "case_summary_v1",
        task: "summary",
        title: "Action non disponible — RC-2048",
        status: "unavailable",
        content: {},
      },
      cardUpdates: {
        summary: [
          "Modification de ton non appliquée",
          `Famille d'artefact active : ${family ?? "aucune"}`,
          "Un brouillon de relance ou message client est nécessaire",
        ],
        complianceChecks: ["Aucune action exécutée", "Aucun message envoyé"],
        nextActions: suggestedActions,
      },
      suggestedActions,
      businessEvents: [],
      businessScores: [],
      decisions: {
        intent: "draft_reminder",
        decision: "requires_message_artifact",
      },
    },
    locale,
  );
}

export function buildArtifactInsertionPreparedResponse(
  artifact: RecouvrementAssistantArtifact,
  actionLabel: string,
  locale: Locale = "fr",
): RecouvrementAssistantResponse {
  const family = artifactFamilyForArtifact(artifact);
  const isNote = family === "contact_rule";
  const visibleReply = isNote
    ? "Note de règle préparée pour RC-2048. Aucune écriture définitive n'a été exécutée."
    : "Insertion préparée pour RC-2048. Aucune écriture définitive n'a été exécutée.";
  const updatedArtifact: RecouvrementAssistantArtifact = {
    ...artifact,
    status: "insertion_prepared",
    content: {
      ...artifact.content,
      insertion_status: "insertion_prepared",
      insertion_action: actionLabel,
      insertion_executed: false,
    },
  };
  return localizeRecouvrementFallback(
    {
      visibleReply,
      artifact: updatedArtifact,
      cardUpdates: {
        summary: [
          `Artefact ciblé : ${artifact.title}`,
          "Statut : insertion préparée",
          "Écriture réelle : non exécutée",
        ],
        complianceChecks: [
          "Artefact courant conservé",
          "Aucune réponse client régénérée",
          "Aucune action irréversible exécutée",
        ],
        nextActions: ["Confirmer l'insertion", "Annuler", "Voir le dossier"],
      },
      suggestedActions: ["Confirmer l'insertion", "Annuler", "Voir le dossier"],
      businessEvents: [],
      businessScores: [],
      decisions: {
        action: "insert_artifact_in_case",
        status: "insertion_prepared",
        artifact_id: artifact.id,
      },
    },
    locale,
  );
}

export function buildArtifactPendingValidationResponse(
  artifact: RecouvrementAssistantArtifact,
  actionLabel: string,
  locale: Locale = "fr",
): RecouvrementAssistantResponse {
  const updatedArtifact: RecouvrementAssistantArtifact = {
    ...artifact,
    status: "pending_validation",
    content: {
      ...artifact.content,
      validation_status: "pending_validation",
      validation_action: actionLabel,
      action_executed: false,
    },
  };
  return localizeRecouvrementFallback(
    {
      visibleReply:
        "Demande de validation préparée pour RC-2048. Aucun message n'a été envoyé et aucune action définitive n'a été exécutée.",
      artifact: updatedArtifact,
      cardUpdates: {
        summary: [
          `Artefact ciblé : ${artifact.title}`,
          "Statut : validation préparée",
          "Action réelle : non exécutée",
        ],
        complianceChecks: [
          "Validation requise",
          "Aucun message envoyé",
          "Aucune action irréversible exécutée",
        ],
        nextActions: ["Confirmer la demande", "Annuler", "Voir le dossier"],
      },
      suggestedActions: ["Confirmer la demande", "Annuler", "Voir le dossier"],
      businessEvents: [],
      businessScores: [],
      decisions: {
        action: "submit_for_validation",
        status: "pending_validation",
        artifact_id: artifact.id,
      },
    },
    locale,
  );
}

export function buildReminderPreparedResponse(
  artifact: RecouvrementAssistantArtifact,
  locale: Locale = "fr",
): RecouvrementAssistantResponse {
  const updatedArtifact: RecouvrementAssistantArtifact = {
    ...artifact,
    status: "reminder_prepared",
    content: {
      ...artifact.content,
      reminder_status: "reminder_prepared",
      calendar_event_created: false,
      action_executed: false,
      no_external_effect: true,
    },
  };
  return localizeRecouvrementFallback(
    {
      visibleReply:
        "Rappel préparé pour demain pour RC-2048. Aucun événement calendrier réel n'a été créé.",
      artifact: updatedArtifact,
      cardUpdates: {
        summary: [
          `Artefact ciblé : ${artifact.title}`,
          "Statut : reminder_prepared",
          "Événement calendrier réel : non créé",
        ],
        complianceChecks: [
          "Aucun événement calendrier créé",
          "Aucun appel préparé hors plage",
          "Aucune action client exécutée",
          "no_external_effect = true",
        ],
        nextActions: ["Voir le rappel préparé", "Rédiger un email", "Annuler"],
      },
      suggestedActions: ["Voir le rappel préparé", "Rédiger un email", "Annuler"],
      businessEvents: [],
      businessScores: [],
      decisions: {
        action: "prepare_reminder_tomorrow",
        status: "reminder_prepared",
        artifact_id: artifact.id,
        no_external_effect: true,
      },
    },
    locale,
  );
}

export function contactRuleCards(response: RecouvrementAssistantResponse, locale: Locale = "fr") {
  const updates = response.cardUpdates ?? {};
  const decision = response.artifact.content.decision;
  const requestedTime =
    typeof response.artifact.content.requested_time === "string"
      ? response.artifact.content.requested_time
      : "";
  const allowedWindow =
    typeof response.artifact.content.allowed_window === "string"
      ? response.artifact.content.allowed_window.replace("-", "–")
      : "08:00–20:00";
  const allowedItems =
    decision === "blocked" && requestedTime
      ? [
          locale === "en"
            ? `Phone contact remains permitted only within ${allowedWindow}. No call at ${requestedTime} may be prepared.`
            : locale === "de"
              ? `Telefonischer Kontakt bleibt nur im Zeitfenster ${allowedWindow} zulässig. Für ${requestedTime} darf kein Anruf vorbereitet werden.`
              : `Un contact téléphonique reste autorisé uniquement sur la plage ${allowedWindow}. Aucun appel à ${requestedTime} ne doit être préparé.`,
        ]
      : (updates.allowedItems ?? []);

  return {
    contactFrame: updates.contactFrame ?? updates.context ?? [],
    allowedItems,
    validationItems: updates.validationItems ?? [],
    nextActions: response.suggestedActions ?? updates.nextActions ?? [],
  };
}

export function footerActionsForRecouvrementArtifact(
  artifact: RecouvrementAssistantArtifact | null,
  locale: Locale = "fr",
): string[] {
  const actions = {
    fr: {
      reminder: "Préparer un rappel pour demain",
      call: "Préparer un script d'appel",
      email: "Rédiger un email de confirmation",
      postpone: "Reporter le contact",
      insertNote: "Insérer la note dans le dossier",
      duration: "Ajuster la durée",
      compare: "Comparer les options",
      clientMessage: "Préparer le message client",
      submit: "Soumettre à validation",
      edit: "Modifier le message",
      copy: "Copier le message",
      insert: "Insérer dans le dossier",
      draft: "Rédiger une relance",
      rule: "Vérifier une règle",
      schedule: "Proposer un échéancier",
    },
    en: {
      reminder: "Schedule a callback tomorrow",
      call: "Prepare a call script",
      email: "Draft a confirmation email",
      postpone: "Reschedule contact",
      insertNote: "Insert the note into the case",
      duration: "Adjust duration",
      compare: "Compare options",
      clientMessage: "Prepare customer message",
      submit: "Submit for approval",
      edit: "Edit message",
      copy: "Copy message",
      insert: "Insert into case",
      draft: "Draft a reminder",
      rule: "Check a rule",
      schedule: "Propose a payment plan",
    },
    de: {
      reminder: "Rückruf für morgen vorbereiten",
      call: "Anrufskript vorbereiten",
      email: "Bestätigungs-E-Mail entwerfen",
      postpone: "Kontakt verschieben",
      insertNote: "Notiz in den Vorgang einfügen",
      duration: "Laufzeit anpassen",
      compare: "Optionen vergleichen",
      clientMessage: "Kundennachricht vorbereiten",
      submit: "Zur Freigabe einreichen",
      edit: "Nachricht bearbeiten",
      copy: "Nachricht kopieren",
      insert: "In den Vorgang einfügen",
      draft: "Mahnung entwerfen",
      rule: "Regel prüfen",
      schedule: "Ratenplan vorschlagen",
    },
  }[locale];
  if (artifact?.type === "contact_rule_v1") {
    const decision = artifact.content.decision;
    return [
      decision === "blocked" ? actions.reminder : actions.call,
      actions.email,
      actions.postpone,
      actions.insertNote,
    ];
  }

  if (artifact?.type === "schedule_proposal_v2") {
    return [actions.duration, actions.compare, actions.clientMessage, actions.submit];
  }

  if (artifact?.type === "reminder_draft_v1" || artifact?.type === "client_message_artifact") {
    return [actions.edit, actions.copy, actions.insert, actions.submit];
  }

  if (artifact?.type === "case_summary_v1") {
    return [actions.draft, actions.rule, actions.schedule, actions.insert];
  }

  if (artifact?.type === "payment_options_v1") {
    return [actions.schedule, actions.clientMessage, actions.submit, actions.insert];
  }

  return [actions.draft, actions.schedule, actions.rule];
}
