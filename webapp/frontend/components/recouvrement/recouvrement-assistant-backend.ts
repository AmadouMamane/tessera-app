import type {
  RecouvrementAssistantArtifact,
  RecouvrementAssistantResponse,
} from "@/lib/api/recouvrement-assistant";

export type RecouvrementDrawerTask =
  | "summary"
  | "draft_reminder"
  | "propose_schedule"
  | "check_contact_rule";

export interface RecouvrementDrawerRoute {
  targetTask: RecouvrementDrawerTask;
  backendIntent?: "check_contact_rule" | "propose_schedule" | "draft_reminder";
  useStructuredBackend: boolean;
  useContactRuleBackend: boolean;
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

function hasSummaryIntent(normalized: string): boolean {
  return /\b(resume|resumer|synthese|synthetise)\b/.test(normalized);
}

export function routeRecouvrementDrawerMessage(
  message: string,
  currentTask: RecouvrementDrawerTask,
  _currentArtifact?: RecouvrementAssistantArtifact | null,
): RecouvrementDrawerRoute {
  const normalized = normalizeDrawerMessage(message);
  const durationMonths = extractDurationMonths(message);

  if (hasDraftIntent(normalized)) {
    return {
      targetTask: "draft_reminder",
      backendIntent: "draft_reminder",
      useStructuredBackend: true,
      useContactRuleBackend: false,
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

  return ["Créer un brouillon", "Insérer dans le dossier", "Copier le message"];
}
