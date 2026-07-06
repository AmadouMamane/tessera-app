import type {
  RecouvrementAssistantArtifact,
  RecouvrementAssistantResponse,
} from "@/lib/api/recouvrement-assistant";

export type RecouvrementDrawerTask =
  | "summary"
  | "draft_reminder"
  | "propose_schedule"
  | "check_contact_rule";

export type RecouvrementBackendIntent =
  | "check_contact_rule"
  | "propose_schedule"
  | "draft_reminder";

export type RecouvrementArtifactFamily = "summary" | "message" | "schedule" | "contact_rule";

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
  const match = normalized.match(/\b(\d{1,3})\s*(?:mois|mensualite|mensualites)\b/);
  if (!match?.[1]) return undefined;
  const months = Number.parseInt(match[1], 10);
  return Number.isFinite(months) && months > 0 ? months : undefined;
}

function formatEuroAmount(value: number): string {
  return `${value.toFixed(2).replace(".", ",")} €`;
}

function hasScheduleIntent(normalized: string): boolean {
  return /\b(echeancier|etalement|etaler|mensualite|mensualites|mois|paiement|payer|regler|regulariser|duree)\b/.test(
    normalized,
  );
}

function hasContactRuleIntent(normalized: string): boolean {
  const hasContactAction =
    /\b(appel|appeler|telephone|telephoner|contacter|contact|joindre|email|mail)\b/.test(
      normalized,
    );
  const hasRuleSignal =
    /\b(regle|regles|autorise|autorisation|interdit|peux|peut|puis|comment|quand|heure|plage|cadre|conforme|conformite)\b/.test(
      normalized,
    ) || /(?:[01]?\d|2[0-3])(?:h|:)/.test(normalized);

  return (
    /\b(regle de contact|cadre de contact)\b/.test(normalized) ||
    (hasContactAction && hasRuleSignal)
  );
}

function hasDraftIntent(normalized: string): boolean {
  return /\b(relance|message client|brouillon|email|mail|courrier|rediger|redige|prepare|preparer|version courte|empathique|modifier|modifie|rends-le|rend le)\b/.test(
    normalized,
  );
}

function hasDraftEditIntent(normalized: string): boolean {
  return /\b(version courte|empathique|modifier|modifie|rends-le|rend le)\b/.test(normalized);
}

function hasSummaryIntent(normalized: string): boolean {
  return /\b(resume|resumer|synthese|synthetise)\b/.test(normalized);
}

export function artifactFamilyForArtifact(
  artifact: RecouvrementAssistantArtifact | null,
): RecouvrementArtifactFamily | null {
  if (!artifact) return null;
  if (artifact.type === "contact_rule_v1") return "contact_rule";
  if (artifact.type === "schedule_proposal_v2") return "schedule";
  if (artifact.type === "reminder_draft_v1" || artifact.type === "client_message_artifact") {
    return "message";
  }
  if (artifact.type === "case_summary_v1") return "summary";
  return null;
}

export function artifactFamilyForTask(task: RecouvrementDrawerTask): RecouvrementArtifactFamily {
  if (task === "check_contact_rule") return "contact_rule";
  if (task === "propose_schedule") return "schedule";
  if (task === "draft_reminder") return "message";
  return "summary";
}

export function isEditableMessageArtifact(artifact: RecouvrementAssistantArtifact | null): boolean {
  return artifactFamilyForArtifact(artifact) === "message";
}

export function backendIntentForTask(
  task: RecouvrementDrawerTask,
): RecouvrementBackendIntent | undefined {
  if (task === "check_contact_rule") return "check_contact_rule";
  if (task === "propose_schedule") return "propose_schedule";
  if (task === "draft_reminder") return "draft_reminder";
  return undefined;
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

  if (hasDraftEditIntent(normalized) && !isEditableMessageArtifact(currentArtifact ?? null)) {
    return {
      targetTask: currentTask,
      useStructuredBackend: false,
      useContactRuleBackend: false,
      blockedReason: "requires_message_artifact",
      extractedSlots: {},
    };
  }

  if (hasScheduleIntent(normalized)) {
    return {
      targetTask: "propose_schedule",
      backendIntent: "propose_schedule",
      useStructuredBackend: true,
      useContactRuleBackend: false,
      extractedSlots: { durationMonths },
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
      useStructuredBackend: false,
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

  return {
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
  };
}

export function buildCaseSummaryDraft(): ScheduleProposalDraft {
  const suggestedActions = ["Rédiger une relance", "Proposer un échéancier", "Vérifier une règle"];

  return {
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
  };
}

export function buildContactRuleBackendUnavailableFallback(): RecouvrementAssistantResponse {
  const suggestedActions = [
    "Planifier un rappel demain",
    "Rédiger un email de confirmation",
    "Reporter le contact",
    "Insérer la note dans le dossier",
  ];

  return {
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
  };
}

export function buildDraftBackendUnavailableFallback(
  currentArtifact?: RecouvrementAssistantArtifact | null,
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

  return {
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
  };
}

export function buildInvalidDraftEditResponse(
  currentArtifact: RecouvrementAssistantArtifact | null,
): RecouvrementAssistantResponse {
  const family = artifactFamilyForArtifact(currentArtifact);
  const suggestedActions = [
    "Rédiger une relance",
    "Préparer le message client",
    "Conserver l'artefact actuel",
  ];
  return {
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
  };
}

export function buildArtifactInsertionPreparedResponse(
  artifact: RecouvrementAssistantArtifact,
  actionLabel: string,
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
  return {
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
  };
}

export function buildArtifactPendingValidationResponse(
  artifact: RecouvrementAssistantArtifact,
  actionLabel: string,
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
  return {
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
  };
}

export function contactRuleCards(response: RecouvrementAssistantResponse) {
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
          `Un contact téléphonique reste autorisé uniquement sur la plage ${allowedWindow}. Aucun appel à ${requestedTime} ne doit être préparé.`,
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
): string[] {
  if (artifact?.type === "contact_rule_v1") {
    const decision = artifact.content.decision;
    return [
      decision === "blocked" ? "Planifier un rappel demain" : "Préparer un script d'appel",
      "Rédiger un email de confirmation",
      "Reporter le contact",
      "Insérer la note dans le dossier",
    ];
  }

  if (artifact?.type === "schedule_proposal_v2") {
    return [
      "Ajuster la durée",
      "Comparer les options",
      "Préparer le message client",
      "Soumettre à validation",
    ];
  }

  if (artifact?.type === "reminder_draft_v1" || artifact?.type === "client_message_artifact") {
    return [
      "Modifier le message",
      "Copier le message",
      "Insérer dans le dossier",
      "Soumettre à validation",
    ];
  }

  if (artifact?.type === "case_summary_v1") {
    return ["Rédiger une relance", "Proposer un échéancier", "Vérifier une règle"];
  }

  return ["Rédiger une relance", "Proposer un échéancier", "Vérifier une règle"];
}
