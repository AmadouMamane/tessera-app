"use client";

import {
  Bell,
  CalendarDays,
  Check,
  ChevronDown,
  ChevronRight,
  CircleCheck,
  CircleHelp,
  Clock3,
  Copy,
  FileText,
  Folder,
  Home,
  Info,
  LockKeyhole,
  Mail,
  Maximize2,
  Minimize2,
  PenLine,
  Phone,
  Pin,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { CreditAuroreLogo } from "@/components/brand/credit-aurore-logo";
import { DemoLauncherLink } from "@/components/layout/demo-launcher-link";
import {
  type RecouvrementDrawerStateModel,
  type RecouvrementDrawerTask,
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
  routeRecouvrementDrawerMessage,
  routeRecouvrementTaskClick,
} from "@/components/recouvrement/recouvrement-assistant-backend";
import type { Locale } from "@/i18n/routing";
import {
  type RecouvrementAssistantArtifact,
  type RecouvrementAssistantResponse,
  sendRecouvrementAssistantAction,
  sendRecouvrementAssistantMessage,
} from "@/lib/api/recouvrement-assistant";
import { streamChat } from "@/lib/api/sse";
import { cn } from "@/lib/cn";
import { type ArtifactStatusTone, artifactStatusMeta } from "@/lib/recouvrement/artifact-status";

const navigation = [
  { label: "Ma journée", Icon: Home, active: true },
  { label: "Dossiers", Icon: Folder },
  { label: "Relances", Icon: Send, count: 14 },
  { label: "Échéanciers", Icon: CalendarDays, count: 8 },
  { label: "Situations à vérifier", Icon: ShieldCheck, count: 5 },
  { label: "Historique", Icon: Clock3 },
];

const reasons = [
  "Promesse de paiement non tenue le 12 juin.",
  "Retard significatif : 32 jours",
  "Échéancier envisageable",
  "Contact autorisé aujourd'hui de 8h à 20h",
];

const assistantActions = [
  {
    label: "Résumer ce dossier",
    description: "Obtenir les points clés en quelques secondes",
    prompt: "Résume ce dossier de recouvrement pour préparer l'action suivante.",
    Icon: FileText,
  },
  {
    label: "Rédiger une relance",
    description: "Message personnalisé prêt à envoyer",
    prompt: "Prépare une relance amiable et propose un échéancier adapté à la situation.",
    Icon: PenLine,
  },
  {
    label: "Vérifier une règle",
    description: "Contrôler la conformité en un clic",
    prompt: "Vérifie les règles applicables avant de contacter le client sur ce dossier.",
    Icon: ShieldCheck,
  },
  {
    label: "Proposer un échéancier",
    description: "Simulation adaptée à la situation",
    prompt: "Propose un échéancier adapté à la situation et indique les points à valider.",
    Icon: CalendarDays,
  },
  {
    label: "Options de paiement",
    description: "Lister les alternatives sans actionner de paiement",
    prompt: "Prépare les options de paiement possibles pour ce dossier sans initier de paiement.",
    Icon: CircleHelp,
  },
];

const nextItems = [
  { value: "4", label: "Relances", detail: "à valider", Icon: Send, accent: "orange" },
  { value: "3", label: "Échéanciers", detail: "à confirmer", Icon: CalendarDays, accent: "violet" },
  { value: "5", label: "Situations", detail: "à vérifier", Icon: ShieldCheck, accent: "violet" },
];

const quickActions = [
  { label: "Préparer une relance", detail: "Rédiger un message personnalisé", Icon: FileText },
  {
    label: "Préparer un échéancier",
    detail: "Proposer un plan de remboursement",
    Icon: CalendarDays,
  },
  { label: "Reporter un dossier", detail: "Choisir une nouvelle date", Icon: FileText },
  { label: "Escalader à un responsable", detail: "Demander une validation", Icon: Users },
  { label: "Consulter l'historique", detail: "Voir toutes les actions", Icon: Clock3 },
];

const cardClass =
  "rounded-[6px] border border-[#dcdee6] bg-white shadow-[0_2px_8px_rgba(0,0,0,0.06)]";

const defaultAssistantTab = "Préparer une relance";

const assistantTabs = [
  defaultAssistantTab,
  "Proposer un échéancier",
  "Options de paiement",
  "Vérifier une règle",
  "Résumer",
];

const contextItems = [
  "Promesse de paiement non tenue le 12 juin.",
  "840,00 €",
  "Retard de 32 jours",
  "Contact autorisé aujourd'hui de 8h à 20h",
];

const verificationItems = [
  "Ton professionnel et factuel",
  "Absence de pression injustifiée",
  "Informations exactes et à jour",
  "Contact autorisé aujourd'hui",
  "Conforme au cadre réglementaire",
];

type AssistantMode = "closed" | "drawer" | "pinned";
type AssistantStatus = "idle" | "loading" | "ready" | "error";

interface DraftVersion {
  id: string;
  label: string;
  title: string;
  body: string;
}

interface AssistantThreadMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  error?: boolean;
}

interface GeneratedAssistantContent {
  summary: string[];
  versions: DraftVersion[];
  paymentPlan: string;
  complianceChecks: string[];
  nextActions: string[];
  rawResponse: string;
  artifact: RecouvrementAssistantArtifact | null;
  artifactCards: Record<string, string[]>;
  businessScores: Array<Record<string, unknown>>;
}

interface AssistantTurnOptions {
  forcedTask?: RecouvrementDrawerTask;
  pendingAction?: string | null;
}

const fallbackAssistantContent: GeneratedAssistantContent = {
  summary: [],
  versions: [],
  paymentPlan: "",
  complianceChecks: [],
  nextActions: [],
  rawResponse: "",
  artifact: null,
  artifactCards: {},
  businessScores: [],
};

const pendingContactRuleContent: GeneratedAssistantContent = {
  ...fallbackAssistantContent,
  artifact: {
    id: "RC-2048-contact-rule-v1",
    type: "contact_rule_v1",
    task: "check_rule",
    title: "Cadre de contact — RC-2048",
    status: "loading",
    content: {},
  },
};

function pendingContentForTask(task: RecouvrementDrawerTask): GeneratedAssistantContent {
  if (task === "check_contact_rule") return pendingContactRuleContent;
  if (task === "explain_payment_options") {
    return {
      ...fallbackAssistantContent,
      artifact: {
        id: "RC-2048-payment-options-pending",
        type: "payment_options_v1",
        task: "explain_payment_options",
        title: "Options de paiement — RC-2048",
        status: "loading",
        content: {},
      },
    };
  }
  if (task === "propose_schedule") {
    return {
      ...fallbackAssistantContent,
      artifact: {
        id: "RC-2048-schedule-pending",
        type: "schedule_proposal_v2",
        task: "propose_schedule",
        title: "Proposition d'échéancier — RC-2048",
        status: "loading",
        content: {},
      },
    };
  }
  if (task === "summary") {
    return {
      ...fallbackAssistantContent,
      artifact: {
        id: "RC-2048-summary-pending",
        type: "case_summary_v1",
        task: "summary",
        title: "Résumé du dossier — RC-2048",
        status: "loading",
        content: {},
      },
    };
  }
  return {
    ...fallbackAssistantContent,
    artifact: {
      id: "RC-2048-reminder-pending",
      type: "reminder_draft_v1",
      task: "draft_reminder",
      title: "Brouillon de relance — RC-2048",
      status: "loading",
      content: {},
    },
  };
}

const initialDrawerStateModel: RecouvrementDrawerStateModel = {
  currentTask: "draft_reminder",
  currentArtifact: null,
  artifactHistory: [],
  selectedArtifactFamily: "message",
  pendingAction: null,
  lastSuccessfulBackendIntent: null,
};

function assistantTaskForTab(tab: string): RecouvrementDrawerTask {
  if (tab === "Vérifier une règle") return "check_contact_rule";
  if (tab === "Proposer un échéancier") return "propose_schedule";
  if (tab === "Options de paiement") return "explain_payment_options";
  if (tab === "Résumer") return "summary";
  return "draft_reminder";
}

function assistantTabForTask(task: RecouvrementDrawerTask): string {
  if (task === "check_contact_rule") return "Vérifier une règle";
  if (task === "propose_schedule") return "Proposer un échéancier";
  if (task === "explain_payment_options") return "Options de paiement";
  if (task === "summary") return "Résumer";
  return "Préparer une relance";
}

const loadingRows = ["loading-row-1", "loading-row-2", "loading-row-3"];
const skeletonLineKeys = [
  "skeleton-line-1",
  "skeleton-line-2",
  "skeleton-line-3",
  "skeleton-line-4",
  "skeleton-line-5",
  "skeleton-line-6",
];

const recouvrementThinkingSteps = [
  "Recouvrement analyse le dossier RC-2048",
  "Recouvrement prépare les variantes de réponse",
  "Recouvrement vérifie les règles de contact",
  "Recouvrement consolide les prochaines actions",
];
const MIN_ASSISTANT_THINKING_MS = 1800;

const defaultAssistantPrompt =
  "Prépare une relance amiable et propose un échéancier adapté à la situation.";

const recouvrementDrawerSystemPrompt = [
  "Tu es l'assistant interne Recouvrement de Crédit Aurore pour Julie Dubois, chargée de recouvrement.",
  "Tu aides à préparer une action sur un dossier, tu ne promets jamais qu'elle est exécutée.",
  "N'oriente jamais Julie vers un service client : tu formules directement l'aide opérationnelle pour le dossier.",
  "N'invente pas de téléphone, d'adresse e-mail, de frais ou de sanction.",
  "Base les brouillons sur le contexte dossier transmis, pas sur des conditions générales externes sauf si l'utilisateur demande explicitement une règle.",
  "N'utilise pas les expressions manquement grave, résiliation, sanction, frais d'incident ou mise en demeure dans une relance amiable.",
  "Le ton d'une réponse client doit rester amiable, factuel, sans menace et sans pression injustifiée.",
  "Un échéancier est seulement préparé ou proposé, puis validé avec le client.",
  "Réponds en français, sans JSON, avec exactement ces titres Markdown dans cet ordre :",
  "## Résumé du dossier",
  "## Réponse au client",
  "### V1 — version courte et directe",
  "### V2 — version plus empathique",
  "### V3 — version avec proposition d'échéancier",
  "## Règles et conformité",
  "## Prochaines actions suggérées",
  "Chaque version doit contenir un brouillon complet prêt à relire, pas une consigne.",
  "Les règles et conformité doivent mentionner seulement les contrôles utiles au recouvrement de ce dossier.",
].join("\n");

const dossierContextForAssistant = [
  "Contexte dossier RC-2048 transmis par l'espace Recouvrement.",
  "Client : M. D.",
  "Montant dû : 840,00 €.",
  "Retard : 32 jours.",
  "Promesse de paiement non tenue le 12 juin.",
  "Contact autorisé aujourd'hui de 8h à 20h.",
  "Échéancier envisageable, uniquement après validation client.",
].join("\n");

function getSubjectId(): string | undefined {
  if (typeof window === "undefined") return undefined;
  const key = "tessera.subjectId";
  let id = window.localStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    window.localStorage.setItem(key, id);
  }
  return id;
}

function CountBadge({ count, className }: { count: number; className?: string }) {
  return (
    <span
      className={cn(
        "grid h-6 min-w-6 place-items-center rounded-full bg-[#f1efeb] px-2 font-semibold text-[#2b2d36] text-xs",
        className,
      )}
    >
      {count}
    </span>
  );
}

const ARTIFACT_STATUS_TONE_CLASS: Record<ArtifactStatusTone, string> = {
  neutral: "border-[#dfe2ec] bg-[#f4f5f9] text-[#071044]/75",
  info: "border-[#c8bbff] bg-[#f0edff] text-[#5237d6]",
  warning: "border-[#ffdca3] bg-[#fff3e0] text-[#a3620a]",
  success: "border-[#bfe6c6] bg-[#e9f7e9] text-[#145b2b]",
  danger: "border-[#ffd2c9] bg-[#fff1ef] text-[#a23b2a]",
};

function ArtifactStatusBadge({
  status,
  className,
}: {
  status?: string | null;
  className?: string;
}) {
  if (!status) return null;
  const meta = artifactStatusMeta(status);
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-full border px-2.5 py-0.5 font-bold text-[0.64rem] whitespace-nowrap",
        ARTIFACT_STATUS_TONE_CLASS[meta.tone],
        className,
      )}
    >
      {meta.label}
    </span>
  );
}

function AssistantCardBloom() {
  return (
    <svg
      className="recouvrement-assistant-bloom pointer-events-none absolute top-[56px] right-[-15px] z-30 h-[78px] w-[28px]"
      viewBox="0 0 28 78"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <filter id="assistantBloomBlur" x="-25%" y="-20%" width="150%" height="140%">
          <feGaussianBlur stdDeviation="3" />
        </filter>
        <radialGradient id="assistantBloomFill" cx="50%" cy="50%" r="64%">
          <stop offset="0" stopColor="#c9c0ff" stopOpacity="0.52" />
          <stop offset="0.54" stopColor="#d8d1ff" stopOpacity="0.32" />
          <stop offset="1" stopColor="#e7e3ff" stopOpacity="0" />
        </radialGradient>
      </defs>
      <path
        d="M14 0V4M14 74V78"
        fill="none"
        stroke="#c8bbff"
        strokeLinecap="round"
        strokeOpacity="0.7"
        strokeWidth="1"
      />
      <path
        d="M14 4C15.2 25.9 18.2 33.4 26 39C18.2 44.6 15.2 52.1 14 74C12.8 52.1 9.8 44.6 2 39C9.8 33.4 12.8 25.9 14 4Z"
        fill="#faf8ff"
      />
      <path
        d="M14 3C15.3 25.5 18.4 33.2 27 39C18.4 44.8 15.3 52.5 14 75C12.7 52.5 9.6 44.8 1 39C9.6 33.2 12.7 25.5 14 3Z"
        fill="#d7d0ff"
        fillOpacity="0.18"
        filter="url(#assistantBloomBlur)"
      />
      <path
        d="M14 4C15.2 25.9 18.2 33.4 26 39C18.2 44.6 15.2 52.1 14 74C12.8 52.1 9.8 44.6 2 39C9.8 33.4 12.8 25.9 14 4Z"
        fill="url(#assistantBloomFill)"
      />
    </svg>
  );
}

function assistantTabForAction(action: string) {
  if (action.includes("Options de paiement")) {
    return "Options de paiement";
  }
  if (action.includes("échéancier")) {
    return "Proposer un échéancier";
  }
  if (action.includes("règle")) {
    return "Vérifier une règle";
  }
  if (action.includes("Résumer")) {
    return "Résumer";
  }
  return "Préparer une relance";
}

function assistantPromptForTab(activeTab: string) {
  const action = assistantActions.find((item) => assistantTabForAction(item.label) === activeTab);
  return action?.prompt ?? defaultAssistantPrompt;
}

function asString(value: unknown) {
  if (typeof value !== "string") return "";
  return value
    .trim()
    .replace(/^fait dossier\s*:?\s*/i, "")
    .replace(/\bnotre service client\b/gi, "Crédit Aurore")
    .replace(/\ble service client\b/gi, "Crédit Aurore")
    .replace(/\bdu service client\b/gi, "de Crédit Aurore");
}

function normalizeAssistantText(value: string) {
  return value
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

function cleanAssistantHeading(line: string) {
  return line
    .replace(/^#+\s*/, "")
    .replace(/^[-*]\s*/, "")
    .replace(/^[_*]+/, "")
    .replace(/[_*:]+$/, "")
    .trim();
}

function isVersionHeading(line: string) {
  const normalized = normalizeAssistantText(cleanAssistantHeading(line));
  return /^(reponse au client\s*[-–—:]?\s*)?(version\s*)?v?\s*[123]\b/.test(normalized);
}

function isAssistantSectionHeading(line: string) {
  const normalized = normalizeAssistantText(cleanAssistantHeading(line));
  if (isVersionHeading(line)) return true;
  if (normalized.length > 84) return false;
  return [
    "resume du dossier",
    "resume",
    "reponse au client",
    "regles et conformite",
    "conformite",
    "prochaines actions",
    "prochaines actions suggerees",
    "echeancier",
    "plan de paiement",
  ].some((heading) => normalized.startsWith(heading));
}

function stripListPrefix(line: string) {
  return line
    .replace(/^[-*•]\s*/, "")
    .replace(/^\d+[.)]\s*/, "")
    .replace(/^:\s*/, "")
    .trim();
}

function blockToItems(block: string, maxItems = 5) {
  return block
    .split(/\r?\n/)
    .map(stripListPrefix)
    .filter((line) => line && !isAssistantSectionHeading(line))
    .slice(0, maxItems);
}

function extractSectionBlock(lines: string[], headings: string[]) {
  const start = lines.findIndex((line) => {
    const normalized = normalizeAssistantText(cleanAssistantHeading(line));
    return headings.some((heading) => normalized.startsWith(heading));
  });
  if (start === -1) return "";

  const body: string[] = [];
  for (const line of lines.slice(start + 1)) {
    if (isAssistantSectionHeading(line)) break;
    body.push(line);
  }
  return body.join("\n").trim();
}

function extractDraftVersions(lines: string[]): DraftVersion[] {
  const markers = lines.flatMap((line, index) => {
    const cleaned = cleanAssistantHeading(line);
    const match = cleaned.match(
      /^(?:Réponse au client\s*[-–—:]?\s*)?(?:Version\s*)?V?\s*([123])\b\s*[-–—:]?\s*(.*)$/i,
    );
    if (!match) return [];
    return [
      {
        index,
        id: `v${match[1]}`,
        label: `V${match[1]}`,
        title: match[2]?.trim() || `Version ${match[1]}`,
      },
    ];
  });

  return markers
    .map((marker, markerIndex) => {
      const nextVersionIndex = markers[markerIndex + 1]?.index ?? lines.length;
      const body: string[] = [];
      for (const line of lines.slice(marker.index + 1, nextVersionIndex)) {
        if (isAssistantSectionHeading(line) && !isVersionHeading(line)) break;
        body.push(line);
      }
      return {
        id: marker.id,
        label: marker.label,
        title: marker.title,
        body: body.join("\n").trim(),
      };
    })
    .filter((version) => version.body.length > 0)
    .slice(0, 3);
}

function parseGeneratedAssistantContent(raw: string): GeneratedAssistantContent {
  const text = asString(raw);
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const responseBlock = extractSectionBlock(lines, ["reponse au client"]);
  const versions = extractDraftVersions(lines);
  const fallbackVersion =
    responseBlock && versions.length === 0
      ? [
          {
            id: "v1",
            label: "V1",
            title: "Version proposée",
            body: responseBlock,
          },
        ]
      : [];

  return {
    summary: blockToItems(extractSectionBlock(lines, ["resume du dossier", "resume"])),
    versions: versions.length > 0 ? versions : fallbackVersion,
    paymentPlan: extractSectionBlock(lines, ["echeancier", "plan de paiement"]),
    complianceChecks: blockToItems(
      extractSectionBlock(lines, ["regles et conformite", "conformite"]),
      6,
    ),
    nextActions: blockToItems(
      extractSectionBlock(lines, ["prochaines actions suggerees", "prochaines actions"]),
      5,
    ),
    rawResponse: text,
    artifact: null,
    artifactCards: {},
    businessScores: [],
  };
}

function contentFromRecouvrementContactResponse(
  response: RecouvrementAssistantResponse,
): GeneratedAssistantContent {
  const cards = contactRuleCards(response);
  return {
    summary: cards.contactFrame,
    versions: [],
    paymentPlan: "",
    complianceChecks: [...cards.allowedItems, ...cards.validationItems],
    nextActions: cards.nextActions,
    rawResponse: response.visibleReply,
    artifact: response.artifact,
    artifactCards: cards,
    businessScores: response.businessScores ?? [],
  };
}

function contentFromScheduleProposal(
  proposal: ReturnType<typeof buildScheduleProposalDraft>,
): GeneratedAssistantContent {
  return {
    summary: proposal.cardUpdates.summary ?? proposal.cardUpdates.context ?? [],
    versions: [
      {
        id: "v1",
        label: "V1",
        title: "Message prudent",
        body: [
          "Bonjour M. D.,",
          "Une solution d'échelonnement peut être étudiée avec vous, sous réserve de validation et d'accord sur les modalités.",
          "Nous vous invitons à nous recontacter afin d'échanger sur une solution adaptée à votre situation.",
          "Cordialement,\nCrédit Aurore",
        ].join("\n\n"),
      },
    ],
    paymentPlan: (proposal.cardUpdates.paymentPlan ?? []).join("\n"),
    complianceChecks: proposal.cardUpdates.complianceChecks ?? [],
    nextActions: proposal.suggestedActions,
    rawResponse: proposal.visibleReply,
    artifact: proposal.artifact,
    artifactCards: proposal.cardUpdates,
    businessScores: [],
  };
}

function contentFromRecouvrementScheduleResponse(
  response: RecouvrementAssistantResponse,
): GeneratedAssistantContent {
  const updates = response.cardUpdates ?? {};
  const clientMessage =
    (updates.clientMessage ?? []).join("\n\n") ||
    [
      "Bonjour M. D.,",
      "Une solution d'échelonnement peut être étudiée avec vous, sous réserve de validation et d'accord sur les modalités.",
      "Nous vous invitons à nous recontacter afin d'échanger sur une solution adaptée à votre situation.",
      "Cordialement,\nCrédit Aurore",
    ].join("\n\n");

  return {
    summary: updates.summary ?? updates.context ?? [],
    versions: [
      {
        id: "v1",
        label: "V1",
        title: updates.scheduleVersionLabel?.[0] ?? "Message prudent",
        body: clientMessage,
      },
    ],
    paymentPlan: (updates.paymentPlan ?? updates.scheduleItems ?? []).join("\n"),
    complianceChecks: updates.complianceChecks ?? [],
    nextActions: response.suggestedActions ?? updates.nextActions ?? [],
    rawResponse: response.visibleReply,
    artifact: response.artifact,
    artifactCards: updates,
    businessScores: response.businessScores ?? [],
  };
}

function contentFromRecouvrementDraftResponse(
  response: RecouvrementAssistantResponse,
): GeneratedAssistantContent {
  const updates = response.cardUpdates ?? {};
  const clientMessage = (updates.clientMessage ?? []).join("\n\n");
  return {
    summary: updates.summary ?? updates.context ?? [],
    versions: [
      {
        id: "v1",
        label: "V1",
        title: updates.draftVersionLabel?.[0] ?? "Message client",
        body: clientMessage,
      },
    ],
    paymentPlan: (updates.paymentPlan ?? []).join("\n"),
    complianceChecks: updates.complianceChecks ?? [],
    nextActions: response.suggestedActions ?? updates.nextActions ?? [],
    rawResponse: response.visibleReply,
    artifact: response.artifact,
    artifactCards: updates,
    businessScores: response.businessScores ?? [],
  };
}

function contentFromCaseSummaryResponse(
  response: RecouvrementAssistantResponse,
): GeneratedAssistantContent {
  const updates = response.cardUpdates ?? {};
  return {
    summary: updates.summary ?? updates.context ?? [],
    versions: [],
    paymentPlan: "",
    complianceChecks: updates.complianceChecks ?? [],
    nextActions: response.suggestedActions ?? updates.nextActions ?? [],
    rawResponse: response.visibleReply,
    artifact: response.artifact,
    artifactCards: updates,
    businessScores: response.businessScores ?? [],
  };
}

function contentFromPaymentOptionsResponse(
  response: RecouvrementAssistantResponse,
): GeneratedAssistantContent {
  const updates = response.cardUpdates ?? {};
  return {
    summary: updates.summary ?? updates.context ?? [],
    versions: [],
    paymentPlan: (updates.paymentOptions ?? updates.options ?? updates.eligibilityNotes ?? []).join(
      "\n",
    ),
    complianceChecks: [...(updates.requiredValidation ?? []), ...(updates.complianceChecks ?? [])],
    nextActions: response.suggestedActions ?? updates.nextActions ?? [],
    rawResponse: response.visibleReply,
    artifact: response.artifact,
    artifactCards: updates,
    businessScores: response.businessScores ?? [],
  };
}

function contentFromArtifactActionResponse(
  response: RecouvrementAssistantResponse,
  previousContent: GeneratedAssistantContent,
): GeneratedAssistantContent {
  const updates = response.cardUpdates ?? {};
  return {
    ...previousContent,
    summary: updates.summary ?? previousContent.summary,
    complianceChecks: updates.complianceChecks ?? previousContent.complianceChecks,
    nextActions: response.suggestedActions ?? updates.nextActions ?? previousContent.nextActions,
    rawResponse: response.visibleReply,
    artifact: response.artifact,
    artifactCards: {
      ...previousContent.artifactCards,
      ...updates,
    },
    businessScores: response.businessScores ?? previousContent.businessScores,
  };
}

function artifactString(artifact: RecouvrementAssistantArtifact | null, key: string): string {
  const value = artifact?.content[key];
  return typeof value === "string" ? value : "";
}

function artifactStringList(artifact: RecouvrementAssistantArtifact | null, key: string): string[] {
  const value = artifact?.content[key];
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function buildAssistantHistory(thread: AssistantThreadMessage[]) {
  const stableMessages = thread.filter((message) => message.content.trim() && !message.streaming);
  return [
    { role: "user" as const, content: dossierContextForAssistant },
    ...stableMessages.map((message) => ({
      role: message.role,
      content: message.content,
    })),
  ];
}

function AssistantContextPanel({ compact = false }: { compact?: boolean }) {
  const items = compact
    ? [
        "Promesse de paiement non tenue le 12 juin.",
        "840,00 € · Retard de 32 jours",
        "Contact autorisé aujourd'hui de 8h à 20h",
      ]
    : contextItems;

  return (
    <section
      className={cn("rounded-[6px] border border-[#dfe2ec] bg-white", compact ? "p-4" : "p-5")}
    >
      <div className="mb-3 flex items-center justify-between gap-4">
        <h3 className="!font-sans !text-[#071044] font-bold text-sm">
          Contexte retenu par l'assistant
        </h3>
        <button
          type="button"
          className="inline-flex items-center gap-2 font-semibold text-[#6048ff] text-xs"
        >
          <PenLine className="h-4 w-4" />
          Modifier le contexte
        </button>
      </div>
      <div className={cn("grid gap-2 text-[#071044] text-xs", compact ? "" : "sm:grid-cols-2")}>
        {items.map((item) => (
          <div
            key={item}
            className={cn(
              "flex items-center gap-2 rounded-[5px] bg-[#fbfbfd] px-3",
              compact ? "min-h-7 text-[0.72rem]" : "min-h-8",
            )}
          >
            <CircleCheck className="h-4 w-4 shrink-0 text-[#071044]/70" />
            <span>{item}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function SkeletonLines({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {skeletonLineKeys.slice(0, rows).map((key, index) => (
        <span
          key={key}
          className={cn(
            "block h-3 rounded-full bg-[#eef0f7]",
            index === rows - 1 ? "w-2/3" : "w-full",
          )}
        />
      ))}
    </div>
  );
}

function AssistantThinkingIndicator({
  compact = false,
  label,
}: {
  compact?: boolean;
  label: string;
}) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-[6px] border border-[#d8d1ff] bg-[#f5f2ff] text-[#071044] shadow-[0_10px_22px_rgba(96,72,255,0.1)]",
        compact ? "px-3 py-2.5" : "mb-4 px-4 py-3",
      )}
    >
      <div className="absolute inset-y-0 left-0 w-1 bg-[#6048ff]" />
      <div className="flex items-center gap-3">
        <span className="relative grid h-9 w-9 shrink-0 place-items-center rounded-full bg-white text-[#6048ff] shadow-[0_6px_16px_rgba(96,72,255,0.16)]">
          <span className="recouvrement-thinking-ring absolute inset-0 rounded-full border border-[#b7aaff] opacity-40" />
          <Sparkles className="recouvrement-thinking-mark relative h-4 w-4" />
        </span>
        <div className="min-w-0">
          <p className="font-extrabold text-sm">Recouvrement réfléchit</p>
          <p className="mt-0.5 text-[#071044]/68 text-xs">{label}</p>
        </div>
        <div className="ml-auto flex items-end gap-1.5">
          {["thinking-dot-1", "thinking-dot-2", "thinking-dot-3"].map((dot, index) => (
            <span
              key={dot}
              className="recouvrement-thinking-dot block h-2 w-2 rounded-full bg-[#6048ff]"
              style={{ animationDelay: `${index * 180}ms` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function AssistantDraftPanel({
  compact = false,
  content,
  selectedVersionId,
  status,
  onSelectVersion,
}: {
  compact?: boolean;
  content: GeneratedAssistantContent;
  selectedVersionId: string;
  status: AssistantStatus;
  onSelectVersion: (versionId: string) => void;
}) {
  const paragraphClassName = compact ? "mt-3" : "mt-4";
  const selectedVersion =
    content.versions.find((version) => version.id === selectedVersionId) ?? content.versions[0];
  const draftParagraphs = (selectedVersion?.body ?? "")
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);

  return (
    <section className="rounded-[6px] border border-[#dfe2ec] bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="!font-sans !text-[#071044] font-bold text-sm">
          Réponse au client
          {selectedVersion ? (
            <span className="ml-2 font-semibold text-[#071044]/62 text-xs">
              {selectedVersion.title}
            </span>
          ) : null}
        </h3>
        <div className="flex shrink-0 items-center gap-1 rounded-[5px] border border-[#dfe2ec] bg-[#fbfbfd] p-1">
          {(status === "loading" && content.versions.length === 0
            ? ["v1", "v2", "v3"].map((id) => ({ id, label: id.toUpperCase() }))
            : content.versions
          ).map((version) => (
            <button
              key={version.id}
              type="button"
              disabled={status === "loading" || content.versions.length === 0}
              onClick={() => onSelectVersion(version.id)}
              className={cn(
                "h-7 min-w-9 rounded-[4px] px-2 font-bold text-[0.68rem] transition",
                selectedVersion?.id === version.id
                  ? "bg-[#6048ff] text-white shadow-[0_4px_10px_rgba(96,72,255,0.22)]"
                  : "text-[#071044]/70 hover:bg-white",
              )}
            >
              {version.label}
            </button>
          ))}
        </div>
      </div>
      <div
        className={cn(
          "rounded-[5px] border border-[#dfe2ec] bg-white text-[#071044]",
          compact
            ? "min-h-[188px] px-3 py-3 text-xs leading-5"
            : "min-h-[132px] px-4 py-3 text-sm leading-6",
        )}
      >
        {status === "loading" ? (
          <SkeletonLines rows={6} />
        ) : draftParagraphs.length > 0 ? (
          draftParagraphs.map((paragraph, index) => (
            <p key={paragraph} className={index === 0 ? undefined : paragraphClassName}>
              {paragraph}
            </p>
          ))
        ) : (
          <p className="text-[#071044]/60">
            Le chat Recouvrement n'a pas encore renvoyé de version exploitable.
          </p>
        )}
      </div>
    </section>
  );
}

function AssistantVerificationPanel({
  checks,
  status,
}: {
  checks: string[];
  status: AssistantStatus;
}) {
  return (
    <section className="rounded-[6px] border border-[#dfe2ec] bg-white p-4">
      <h3 className="mb-3 !font-sans !text-[#071044] font-bold text-sm">Règles et conformité</h3>
      <ul className="space-y-2.5 text-[#071044] text-xs">
        {status === "loading"
          ? loadingRows.map((row) => (
              <li key={row}>
                <SkeletonLines rows={1} />
              </li>
            ))
          : checks.map((item) => (
              <li key={item} className="flex items-center gap-3">
                <Check className="h-4 w-4 shrink-0 text-[#16843a]" />
                <span>{item}</span>
              </li>
            ))}
      </ul>
    </section>
  );
}

function AssistantContactRulePanel({
  compact = false,
  content,
  status,
}: {
  compact?: boolean;
  content: GeneratedAssistantContent;
  status: AssistantStatus;
}) {
  const cards = content.artifactCards;
  const decision = content.artifact?.content.decision;
  const reasonCodes = artifactStringList(content.artifact, "reason_codes");
  const isBlocked = decision === "blocked";
  const contactFrame = cards.contactFrame ?? content.summary;
  const allowedItems = cards.allowedItems ?? [];
  const validationItems = cards.validationItems ?? content.complianceChecks;
  const displayedContactFrame =
    isBlocked && !contactFrame.includes("Aucun appel préparé")
      ? [...contactFrame, "Aucun appel préparé"]
      : contactFrame;
  const sectionClassName = "rounded-[5px] border border-[#dfe2ec] bg-[#fbfbfd] p-4";
  const rows = compact ? loadingRows.slice(0, 2) : loadingRows;

  return (
    <>
      <section className={sectionClassName}>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <h3 className="!font-sans !text-[#071044] font-bold text-sm">
            Cadre de contact applicable
          </h3>
          {isBlocked ? (
            <>
              <span className="rounded-full bg-[#ffe8e5] px-2 py-0.5 font-bold text-[#c0362c] text-[0.64rem]">
                Action bloquée
              </span>
              {reasonCodes[0] ? (
                <span className="rounded-full border border-[#ffd2c9] bg-white px-2 py-0.5 font-bold text-[#a23b2a] text-[0.64rem]">
                  {reasonCodes[0]}
                </span>
              ) : null}
            </>
          ) : null}
        </div>
        <ul className="space-y-1.5 text-xs leading-5">
          {status === "loading"
            ? rows.map((row) => (
                <li key={row}>
                  <SkeletonLines rows={1} />
                </li>
              ))
            : displayedContactFrame.map((item) => <li key={item}>{item}</li>)}
        </ul>
      </section>
      <section className={sectionClassName}>
        <h3 className="mb-2 !font-sans !text-[#071044] font-bold text-sm">Ce qui est autorisé</h3>
        <ul className="space-y-1.5 text-xs leading-5">
          {status === "loading"
            ? rows.map((row) => (
                <li key={row}>
                  <SkeletonLines rows={1} />
                </li>
              ))
            : allowedItems.map((item) => <li key={item}>{item}</li>)}
        </ul>
      </section>
      <section className={sectionClassName}>
        <h3 className="mb-2 !font-sans !text-[#071044] font-bold text-sm">
          Ce qui nécessite validation ou action
        </h3>
        <ul className="space-y-1.5 text-xs leading-5">
          {status === "loading"
            ? rows.map((row) => (
                <li key={row}>
                  <SkeletonLines rows={1} />
                </li>
              ))
            : validationItems.map((item) => <li key={item}>{item}</li>)}
        </ul>
      </section>
    </>
  );
}

function footerIconForAction(action: string) {
  const normalized = normalizeAssistantText(action);
  if (normalized.includes("rappel") || normalized.includes("duree")) return CalendarDays;
  if (normalized.includes("email") || normalized.includes("message")) return Mail;
  if (normalized.includes("reporter")) return Clock3;
  if (normalized.includes("script") || normalized.includes("appel")) return Phone;
  if (normalized.includes("inserer") || normalized.includes("note")) return Folder;
  if (normalized.includes("copier")) return Copy;
  if (normalized.includes("validation") || normalized.includes("soumettre")) return Send;
  return PenLine;
}

function AssistantFooterActions({
  actions,
  compact = false,
  onAction,
}: {
  actions: string[];
  compact?: boolean;
  onAction: (action: string) => void;
}) {
  return (
    <div className={cn(compact ? "mb-4 flex flex-wrap gap-2" : "flex flex-wrap gap-3")}>
      {actions.map((action, index) => {
        const Icon = footerIconForAction(action);
        const primary = index === 0;
        return (
          <button
            key={action}
            type="button"
            onClick={() => onAction(action)}
            className={cn(
              "inline-flex h-10 items-center justify-center gap-2 rounded-[5px] px-3 font-bold text-xs transition",
              compact ? "min-w-[132px]" : "px-4",
              primary
                ? "bg-[linear-gradient(180deg,#e38a00,#cf7300)] text-white shadow-[0_10px_22px_rgba(217,119,0,0.22)] hover:bg-[#c96f00]"
                : "border border-[#dfe2ec] bg-white text-[#071044] hover:bg-[#f7f8fb]",
            )}
          >
            <Icon className="h-4 w-4" />
            {action}
          </button>
        );
      })}
    </div>
  );
}

function AssistantDrawer({
  mode,
  activeTab,
  content,
  error,
  inputValue,
  messages,
  selectedVersionId,
  status,
  thinkingLabel,
  onClose,
  onExpand,
  onInputChange,
  onRegenerate,
  onAction,
  onSelectVersion,
  onSendMessage,
  onSelectTab,
  onTogglePinned,
}: {
  mode: Exclude<AssistantMode, "closed">;
  activeTab: string;
  content: GeneratedAssistantContent;
  error: string | null;
  inputValue: string;
  messages: AssistantThreadMessage[];
  selectedVersionId: string;
  status: AssistantStatus;
  thinkingLabel: string;
  onClose: () => void;
  onExpand: () => void;
  onInputChange: (value: string) => void;
  onRegenerate: () => void;
  onAction: (action: string) => void;
  onSelectVersion: (versionId: string) => void;
  onSendMessage: () => void;
  onSelectTab: (tab: string) => void;
  onTogglePinned: () => void;
}) {
  const isPinned = mode === "pinned";
  const artifactFamily = artifactFamilyForArtifact(content.artifact);
  const hasContactRuleArtifact = content.artifact?.type === "contact_rule_v1";
  const hasMessageArtifact = artifactFamily === "message";
  const shouldShowDraftPanel =
    hasMessageArtifact ||
    artifactFamily === "schedule" ||
    (status === "loading" && artifactFamily !== "summary" && artifactFamily !== "payment_options");
  const hasStructuredArtifact = content.artifact !== null;
  const isBlockedContact =
    content.artifact?.type === "contact_rule_v1" && content.artifact.content.decision === "blocked";
  const contactStatus = artifactString(content.artifact, "contact_status");
  const contactReasonCode = artifactStringList(content.artifact, "reason_codes")[0];
  const footerActions = footerActionsForRecouvrementArtifact(content.artifact);
  const summary = content.summary.length > 0 ? content.summary : fallbackAssistantContent.summary;
  const checks =
    content.complianceChecks.length > 0 ? content.complianceChecks : verificationItems.slice(0, 4);
  const nextActions =
    content.nextActions.length > 0
      ? content.nextActions
      : ["Relire la proposition avant action.", "Insérer le brouillon après validation."];
  const initialPrompt =
    messages.find((message) => message.role === "user")?.content ??
    assistantPromptForTab(activeTab);
  const resultTitle = hasContactRuleArtifact
    ? isBlockedContact
      ? "Action de contact bloquée pour RC-2048."
      : "Règle de contact vérifiée pour RC-2048."
    : (content.artifact?.title ?? "Analyse du dossier RC-2048.");
  const verifyButtonLabel = hasContactRuleArtifact ? "Revérifier" : "Régénérer";
  const paymentPlanTitle =
    artifactFamily === "payment_options" ? "Options de paiement" : "Échéancier proposé";

  return (
    <aside
      aria-label="Assistant de traitement"
      aria-modal={isPinned ? undefined : true}
      role={isPinned ? "complementary" : "dialog"}
      className={cn(
        "fixed right-0 z-50 flex flex-col overflow-hidden border-[#dfe2ec] border-l bg-white text-[#071044] transition-[width,box-shadow,transform] duration-300 ease-out",
        "top-[90px] h-[calc(100vh-90px)] max-md:top-0 max-md:h-screen",
        isPinned
          ? "w-[496px] max-w-[calc(100vw-18px)] shadow-[-12px_0_36px_rgba(7,16,68,0.08)]"
          : "w-[704px] max-w-[calc(100vw-22px)] shadow-[-26px_0_70px_rgba(7,16,68,0.18)]",
      )}
    >
      <header
        className={cn(
          "shrink-0 border-[#dfe2ec] border-b bg-white px-6",
          isPinned ? "py-5" : "py-4",
        )}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2
              className={cn(
                "flex items-center gap-2 !font-sans !text-[#071044] font-extrabold tracking-[0]",
                isPinned ? "text-[0.94rem] leading-6" : "flex-wrap text-xl",
              )}
            >
              {!isPinned ? <Sparkles className="h-5 w-5 text-[#6048ff]" /> : null}
              <span className="whitespace-nowrap">Assistant de traitement</span>
              <span className="whitespace-nowrap font-semibold text-[#071044]/80">
                {isPinned ? "- RC-2048" : "RC-2048"}
              </span>
              <span
                className={cn(
                  "rounded-full bg-[#f0edff] font-bold text-[#6048ff]",
                  isPinned ? "px-1.5 py-0.5 text-[0.5rem]" : "px-2.5 py-1 text-[0.68rem]",
                )}
              >
                Contextualisé
              </span>
            </h2>
            {!isPinned ? (
              <p className="mt-1 text-[#071044]/70 text-sm">
                Contextualisé sur le dossier prioritaire
              </p>
            ) : null}
          </div>
          <div className={cn("flex shrink-0 items-center", isPinned ? "gap-1.5" : "gap-2")}>
            <button
              type="button"
              aria-label={isPinned ? "Détacher l'assistant" : "Épingler l'assistant"}
              onClick={onTogglePinned}
              className={cn(
                "grid place-items-center rounded-[5px] border border-[#dfe2ec] text-[#071044] transition hover:bg-[#f7f8fb]",
                isPinned ? "h-7 w-7" : "h-8 w-8",
              )}
            >
              {isPinned ? <Minimize2 className="h-4 w-4" /> : <Pin className="h-4 w-4" />}
            </button>
            <button
              type="button"
              aria-label="Agrandir l'assistant"
              onClick={onExpand}
              className={cn(
                "grid place-items-center rounded-[5px] border border-[#dfe2ec] text-[#071044] transition hover:bg-[#f7f8fb]",
                isPinned ? "h-7 w-7" : "h-8 w-8",
              )}
            >
              <Maximize2 className="h-4 w-4" />
            </button>
            <button
              type="button"
              aria-label="Fermer l'assistant"
              onClick={onClose}
              className={cn(
                "grid place-items-center rounded-[5px] text-[#071044] transition hover:bg-[#f7f8fb]",
                isPinned ? "h-7 w-7" : "h-8 w-8",
              )}
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>
        {isPinned ? (
          <div className="mt-5 flex gap-4 overflow-x-auto border-[#eceef5] border-b">
            {assistantTabs.map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => onSelectTab(tab)}
                className={cn(
                  "relative h-10 shrink-0 font-bold text-[0.72rem] transition",
                  activeTab === tab ? "text-[#6048ff]" : "text-[#071044]",
                )}
              >
                {tab}
                <span
                  className={cn(
                    "absolute right-0 bottom-0 left-0 h-0.5 rounded-full bg-[#6048ff] transition-opacity",
                    activeTab === tab ? "opacity-100" : "opacity-0",
                  )}
                />
              </button>
            ))}
          </div>
        ) : null}
      </header>

      {isPinned ? (
        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          <div className="space-y-4">
            {status === "loading" ? (
              <AssistantThinkingIndicator compact label={thinkingLabel} />
            ) : (
              <div className="flex items-center gap-2">
                <p className="min-w-0 flex-1 truncate font-bold text-[#071044] text-xs">
                  {resultTitle}
                </p>
                <ArtifactStatusBadge status={content.artifact?.status} />
              </div>
            )}
            <AssistantContextPanel compact />
            {hasContactRuleArtifact ? (
              <AssistantContactRulePanel compact content={content} status={status} />
            ) : shouldShowDraftPanel ? (
              <>
                <AssistantDraftPanel
                  compact
                  content={content}
                  selectedVersionId={selectedVersionId}
                  status={status}
                  onSelectVersion={onSelectVersion}
                />
                <AssistantVerificationPanel checks={checks} status={status} />
              </>
            ) : (
              <AssistantVerificationPanel checks={checks} status={status} />
            )}
            <section className="rounded-[6px] border border-[#dfe2ec] bg-white p-4">
              <h3 className="mb-3 !font-sans !text-[#071044] font-bold text-sm">
                Prochaines actions suggérées
              </h3>
              <ul className="space-y-2 text-[#071044] text-xs">
                {status === "loading"
                  ? loadingRows.slice(0, 2).map((row) => (
                      <li key={row}>
                        <SkeletonLines rows={1} />
                      </li>
                    ))
                  : nextActions.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </section>
          </div>
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          <section className="grid gap-3 rounded-[6px] border border-[#dfe2ec] bg-white p-4 md:grid-cols-[minmax(0,1fr)_120px_100px_168px]">
            <div className="flex items-center gap-3">
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-[#fbf0dd] font-bold text-[#d97700]">
                MD
              </span>
              <div>
                <p className="font-bold text-sm">M. D.</p>
                <p className="mt-1 rounded-[5px] bg-[#ffe8e5] px-2 py-1 font-semibold text-[#f23932] text-xs">
                  Promesse non tenue
                </p>
              </div>
            </div>
            <div>
              <p className="font-extrabold text-sm">840,00 €</p>
              <p className="mt-1 text-xs">Montant dû</p>
            </div>
            <div>
              <p className="font-extrabold text-sm">32 jours</p>
              <p className="mt-1 text-xs">Retard</p>
            </div>
            <div
              className={cn(
                "rounded-[5px] px-3 py-2 text-xs",
                isBlockedContact ? "bg-[#fff1ef] text-[#a23b2a]" : "bg-[#e9f7e9] text-[#145b2b]",
              )}
            >
              <p className="flex items-center gap-2 font-bold">
                {isBlockedContact ? <X className="h-4 w-4" /> : <CircleCheck className="h-4 w-4" />}
                {isBlockedContact ? "Action bloquée" : "Contact autorisé"}
              </p>
              <p className="mt-1">{isBlockedContact ? contactStatus : "8h - 20h"}</p>
              {isBlockedContact && contactReasonCode ? (
                <p className="mt-1 font-bold text-[0.62rem]">{contactReasonCode}</p>
              ) : null}
            </div>
          </section>

          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {assistantActions.map(({ label, Icon }) => {
              const tab = assistantTabForAction(label);
              return (
                <button
                  key={label}
                  type="button"
                  onClick={() => onSelectTab(tab)}
                  className={cn(
                    "flex min-h-12 items-center justify-center gap-2 rounded-[5px] border px-3 font-bold text-xs transition",
                    activeTab === tab
                      ? "border-[#b7aaff] bg-[#f4f1ff] text-[#6048ff]"
                      : "border-[#dfe2ec] bg-white text-[#071044] hover:bg-[#f7f8fb]",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </button>
              );
            })}
          </div>

          <div className="mt-5 ml-auto max-w-[430px] rounded-[6px] bg-[#f0edff] px-5 py-4 text-[#071044] text-sm leading-6 shadow-[0_8px_18px_rgba(96,72,255,0.08)]">
            {initialPrompt}
          </div>

          <article className="mt-5 rounded-[6px] border border-[#dfe2ec] bg-white p-5 shadow-[0_12px_28px_rgba(7,16,68,0.05)]">
            <div className="mb-4 flex items-center gap-3 text-sm">
              <Sparkles
                className={cn("h-5 w-5 text-[#6048ff]", status === "loading" && "animate-pulse")}
              />
              <p className="font-bold">{status === "loading" ? thinkingLabel : resultTitle}</p>
              {status !== "loading" && content.artifact ? (
                <ArtifactStatusBadge status={content.artifact.status} />
              ) : null}
              <button
                type="button"
                onClick={onRegenerate}
                className="ml-auto font-semibold text-[#6048ff] text-xs"
              >
                {verifyButtonLabel}
              </button>
            </div>
            {error ? (
              <div className="mb-4 rounded-[5px] border border-[#ffd2c9] bg-[#fff5f3] px-4 py-3 text-[#a23b2a] text-xs">
                {error}
              </div>
            ) : null}
            {hasStructuredArtifact && content.rawResponse && status !== "loading" ? (
              <div className="mb-4 rounded-[6px] bg-[#f0edff] px-4 py-3 text-[#071044] text-sm leading-6">
                {content.rawResponse}
              </div>
            ) : null}
            {status === "loading" ? <AssistantThinkingIndicator label={thinkingLabel} /> : null}
            <div className="grid gap-4">
              {hasContactRuleArtifact ? (
                <AssistantContactRulePanel content={content} status={status} />
              ) : (
                <>
                  <section className="rounded-[5px] border border-[#dfe2ec] bg-[#fbfbfd] p-4">
                    <h3 className="mb-2 !font-sans !text-[#071044] font-bold text-sm">
                      Résumé du dossier
                    </h3>
                    <ul className="space-y-1.5 text-xs leading-5">
                      {status === "loading"
                        ? loadingRows.map((row) => (
                            <li key={row}>
                              <SkeletonLines rows={1} />
                            </li>
                          ))
                        : summary.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  </section>
                  {shouldShowDraftPanel ? (
                    <AssistantDraftPanel
                      content={content}
                      selectedVersionId={selectedVersionId}
                      status={status}
                      onSelectVersion={onSelectVersion}
                    />
                  ) : null}
                  {content.paymentPlan || status === "loading" ? (
                    <section className="rounded-[5px] border border-[#dfe2ec] bg-[#fbfbfd] p-4">
                      <h3 className="mb-2 !font-sans !text-[#071044] font-bold text-sm">
                        {paymentPlanTitle}
                      </h3>
                      {status === "loading" ? (
                        <SkeletonLines rows={2} />
                      ) : (
                        <p className="whitespace-pre-wrap text-xs leading-5">
                          {content.paymentPlan}
                        </p>
                      )}
                    </section>
                  ) : null}
                  <section className="rounded-[5px] border border-[#dfe2ec] bg-[#fbfbfd] p-4">
                    <h3 className="mb-2 !font-sans !text-[#071044] font-bold text-sm">
                      Règles et conformité
                    </h3>
                    <ul className="space-y-1.5 text-xs leading-5">
                      {status === "loading"
                        ? loadingRows.map((row) => (
                            <li key={row}>
                              <SkeletonLines rows={1} />
                            </li>
                          ))
                        : checks.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  </section>
                </>
              )}
              <section className="rounded-[5px] border border-[#dfe2ec] bg-[#fbfbfd] p-4">
                <h3 className="mb-2 !font-sans !text-[#071044] font-bold text-sm">
                  Prochaines actions suggérées
                </h3>
                <ul className="space-y-1.5 text-xs leading-5">
                  {status === "loading"
                    ? loadingRows.slice(0, 2).map((row) => (
                        <li key={row}>
                          <SkeletonLines rows={1} />
                        </li>
                      ))
                    : nextActions.map((item) => <li key={item}>{item}</li>)}
                </ul>
              </section>
            </div>
          </article>
        </div>
      )}

      <footer className="shrink-0 border-[#dfe2ec] border-t bg-white px-6 py-4">
        {isPinned ? (
          <>
            <AssistantFooterActions actions={footerActions} compact onAction={onAction} />
            <div className="flex items-center justify-between gap-3 text-xs">
              <button
                type="button"
                onClick={onTogglePinned}
                className="inline-flex items-center gap-2 font-semibold text-[#071044]"
              >
                <ChevronRight className="h-4 w-4 rotate-180" />
                Réduire le panneau
              </button>
              <button
                type="button"
                onClick={onExpand}
                className="inline-flex items-center gap-2 font-semibold text-[#071044]"
              >
                Agrandir
                <Maximize2 className="h-4 w-4" />
              </button>
            </div>
            <p className="mt-3 text-[#071044]/55 text-[0.64rem]">
              L'assistant peut se tromper. Vérifiez toujours les informations avant action.
            </p>
          </>
        ) : (
          <>
            <AssistantFooterActions actions={footerActions} onAction={onAction} />
            <form
              className="mt-4 flex min-h-[56px] items-center gap-3 rounded-[5px] border border-[#b7aaff] bg-white px-4 shadow-[0_8px_18px_rgba(96,72,255,0.06)]"
              onSubmit={(event) => {
                event.preventDefault();
                onSendMessage();
              }}
            >
              <input
                aria-label="Question assistant"
                value={inputValue}
                onChange={(event) => onInputChange(event.target.value)}
                placeholder="Continuer avec le chat Recouvrement..."
                className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-[#071044]/55"
              />
              <button
                type="submit"
                aria-label="Envoyer la question"
                disabled={status === "loading" || inputValue.trim().length === 0}
                className="grid h-10 w-10 place-items-center rounded-[5px] bg-[#6048ff] text-white transition disabled:bg-[#c8bbff]"
              >
                <Send className="h-5 w-5" />
              </button>
            </form>
            <p className="mt-3 text-[#071044]/55 text-[0.68rem]">
              L'assistant peut se tromper. Vérifiez toujours les informations avant action.
            </p>
          </>
        )}
      </footer>
    </aside>
  );
}

export function RecouvrementProductExperience() {
  const locale = useLocale() as Locale;
  const [assistantMode, setAssistantMode] = useState<AssistantMode>("closed");
  const [activeAssistantTab, setActiveAssistantTab] = useState(defaultAssistantTab);
  const [assistantContent, setAssistantContent] =
    useState<GeneratedAssistantContent>(fallbackAssistantContent);
  const [assistantStatus, setAssistantStatus] = useState<AssistantStatus>("idle");
  const [assistantError, setAssistantError] = useState<string | null>(null);
  const [assistantThread, setAssistantThread] = useState<AssistantThreadMessage[]>([]);
  const [assistantInput, setAssistantInput] = useState("");
  const [selectedVersionId, setSelectedVersionId] = useState("v1");
  const [generationNonce, setGenerationNonce] = useState(0);
  const [thinkingStep, setThinkingStep] = useState(0);
  const [drawerStateModel, setDrawerStateModel] =
    useState<RecouvrementDrawerStateModel>(initialDrawerStateModel);
  const abortRef = useRef<AbortController | null>(null);
  const assistantThreadRef = useRef<AssistantThreadMessage[]>([]);
  const assistantContentRef = useRef<GeneratedAssistantContent>(fallbackAssistantContent);
  const drawerStateModelRef = useRef<RecouvrementDrawerStateModel>(initialDrawerStateModel);
  const skipNextAssistantAutoTurnRef = useRef(false);
  const conversationIdRef = useRef<string | null>(null);
  const isAssistantOpen = assistantMode !== "closed";
  const thinkingLabel =
    recouvrementThinkingSteps[thinkingStep % recouvrementThinkingSteps.length] ??
    "Recouvrement réfléchit";

  useEffect(() => {
    assistantThreadRef.current = assistantThread;
  }, [assistantThread]);

  useEffect(() => {
    assistantContentRef.current = assistantContent;
  }, [assistantContent]);

  useEffect(() => {
    drawerStateModelRef.current = drawerStateModel;
  }, [drawerStateModel]);

  useEffect(() => {
    if (!assistantContent.artifact) return;
    const family = artifactFamilyForArtifact(assistantContent.artifact);
    setDrawerStateModel((current) => {
      const history = [
        assistantContent.artifact as RecouvrementAssistantArtifact,
        ...current.artifactHistory.filter((item) => item.id !== assistantContent.artifact?.id),
      ].slice(0, 8);
      return {
        ...current,
        currentArtifact: assistantContent.artifact,
        artifactHistory: history,
        selectedArtifactFamily: family ?? current.selectedArtifactFamily,
      };
    });
  }, [assistantContent]);

  const openAssistant = (action = defaultAssistantTab) => {
    const nextTab = assistantTabForAction(action);
    const nextTask = assistantTaskForTab(nextTab);
    setDrawerStateModel((current) => ({
      ...current,
      currentTask: nextTask,
      selectedArtifactFamily: artifactFamilyForTask(nextTask),
      pendingAction: null,
    }));
    setActiveAssistantTab(nextTab);
    setAssistantMode("drawer");
  };
  const closeAssistant = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setAssistantMode("closed");
  };
  const expandAssistant = () => setAssistantMode("drawer");
  const togglePinnedAssistant = () =>
    setAssistantMode((currentMode) => (currentMode === "pinned" ? "drawer" : "pinned"));
  const regenerateAssistantContent = useCallback(() => {
    setGenerationNonce((nonce) => nonce + 1);
  }, []);

  const sendAssistantTurn = useCallback(
    (message: string, resetThread: boolean, options: AssistantTurnOptions = {}) => {
      const trimmedMessage = message.trim();
      if (!trimmedMessage) return;
      const currentModel = drawerStateModelRef.current;
      const currentArtifact = currentModel.currentArtifact ?? assistantContentRef.current.artifact;
      const currentTask =
        options.forcedTask ?? currentModel.currentTask ?? assistantTaskForTab(activeAssistantTab);
      const route = options.forcedTask
        ? routeRecouvrementTaskClick(options.forcedTask)
        : routeRecouvrementDrawerMessage(trimmedMessage, currentTask, currentArtifact);
      const usesStructuredBackend = route.useStructuredBackend;
      const usesStructuredScheduleBackend = route.backendIntent === "propose_schedule";
      const usesStructuredDraftBackend = route.backendIntent === "draft_reminder";
      const usesStructuredSummaryBackend = route.backendIntent === "summarize_case";
      const usesStructuredPaymentOptionsBackend = route.backendIntent === "explain_payment_options";
      const routedTab = assistantTabForTask(route.targetTask);
      if (!resetThread && routedTab !== activeAssistantTab) {
        skipNextAssistantAutoTurnRef.current = true;
        setActiveAssistantTab(routedTab);
      }
      setDrawerStateModel((current) => ({
        ...current,
        currentTask: route.targetTask,
        selectedArtifactFamily: artifactFamilyForTask(route.targetTask),
        pendingAction: options.pendingAction ?? null,
      }));

      const priorThread = resetThread
        ? []
        : assistantThreadRef.current.filter((item) => !item.streaming);
      const userMessage: AssistantThreadMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: trimmedMessage,
      };
      const assistantMessage: AssistantThreadMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "",
        streaming: true,
      };

      if (resetThread) {
        conversationIdRef.current = null;
        setAssistantContent(pendingContentForTask(route.targetTask));
        setSelectedVersionId("v1");
      }

      setAssistantInput("");
      setAssistantError(null);
      setAssistantStatus("loading");
      setAssistantThread([...priorThread, userMessage, assistantMessage]);

      const controller = new AbortController();
      abortRef.current?.abort();
      abortRef.current = controller;
      const loadingStartedAt = Date.now();
      const completeAfterThinkingMinimum = (callback: () => void) => {
        const remainingMs = Math.max(
          0,
          MIN_ASSISTANT_THINKING_MS - (Date.now() - loadingStartedAt),
        );
        window.setTimeout(() => {
          if (controller.signal.aborted) return;
          callback();
        }, remainingMs);
      };

      if (route.blockedReason === "requires_message_artifact") {
        const response = buildInvalidDraftEditResponse(currentArtifact);
        const parsed = contentFromArtifactActionResponse(response, assistantContentRef.current);
        completeAfterThinkingMinimum(() => {
          setAssistantContent(parsed);
          setSelectedVersionId(parsed.versions[0]?.id ?? "v1");
          setAssistantThread((current) =>
            current.map((item) =>
              item.id === assistantMessage.id
                ? { ...item, content: response.visibleReply, streaming: false }
                : item,
            ),
          );
          setAssistantStatus("ready");
        });
        return;
      }

      const runLegacyStream = () => {
        let rawResponse = "";

        return streamChat(
          {
            message: trimmedMessage,
            language: locale,
            conversation_id: resetThread ? undefined : (conversationIdRef.current ?? undefined),
            subject_id: getSubjectId(),
            history: buildAssistantHistory(priorThread),
            system_prompt_override: recouvrementDrawerSystemPrompt,
          },
          {
            signal: controller.signal,
            surface: "recouvrement",
            onStart: ({ conversation_id }) => {
              conversationIdRef.current = conversation_id;
            },
            onToken: (token) => {
              rawResponse += token;
              setAssistantThread((current) =>
                current.map((item) =>
                  item.id === assistantMessage.id
                    ? { ...item, content: item.content + token }
                    : item,
                ),
              );
            },
            onEnd: (envelope) => {
              const finalResponse = asString(envelope.final_response || rawResponse);
              const parsed = parseGeneratedAssistantContent(finalResponse);
              setAssistantContent(parsed);
              setSelectedVersionId(parsed.versions[0]?.id ?? "v1");
              setAssistantThread((current) =>
                current.map((item) =>
                  item.id === assistantMessage.id
                    ? { ...item, content: finalResponse, streaming: false }
                    : item,
                ),
              );
              setAssistantStatus("ready");
            },
            onError: (message) => {
              if (controller.signal.aborted) return;
              setAssistantError(message);
              setAssistantStatus("error");
              setAssistantThread((current) =>
                current.map((item) =>
                  item.id === assistantMessage.id
                    ? { ...item, content: message, streaming: false, error: true }
                    : item,
                ),
              );
            },
          },
        );
      };

      if (route.targetTask === "propose_schedule" && !usesStructuredScheduleBackend) {
        const proposal = buildScheduleProposalDraft(
          trimmedMessage,
          route.extractedSlots.durationMonths,
        );
        const parsed = contentFromScheduleProposal(proposal);
        completeAfterThinkingMinimum(() => {
          setAssistantContent(parsed);
          setSelectedVersionId(parsed.versions[0]?.id ?? "v1");
          setAssistantThread((current) =>
            current.map((item) =>
              item.id === assistantMessage.id
                ? { ...item, content: proposal.visibleReply, streaming: false }
                : item,
            ),
          );
          setAssistantStatus("ready");
        });
        return;
      }

      if (route.targetTask === "summary" && !usesStructuredBackend) {
        const summary = buildCaseSummaryDraft();
        const parsed = contentFromCaseSummaryResponse(summary);
        completeAfterThinkingMinimum(() => {
          setAssistantContent(parsed);
          setSelectedVersionId("v1");
          setAssistantThread((current) =>
            current.map((item) =>
              item.id === assistantMessage.id
                ? { ...item, content: summary.visibleReply, streaming: false }
                : item,
            ),
          );
          setAssistantStatus("ready");
        });
        return;
      }

      if (usesStructuredBackend) {
        const conversationId =
          resetThread || !conversationIdRef.current
            ? crypto.randomUUID()
            : conversationIdRef.current;
        conversationIdRef.current = conversationId;
        const turnId = crypto.randomUUID();

        void sendRecouvrementAssistantMessage({
          message: trimmedMessage,
          conversationId,
          turnId,
          assistantState: {
            activeTask: route.targetTask,
            activeTab: activeAssistantTab,
            caseId: "RC-2048",
            currentArtifact,
            currentActionContext: options.pendingAction
              ? {
                  action: options.pendingAction,
                  artifactId: currentArtifact?.id ?? null,
                  artifactFamily: artifactFamilyForArtifact(currentArtifact),
                }
              : null,
            history: buildAssistantHistory(priorThread),
          },
          signal: controller.signal,
        })
          .then((response) => {
            if (controller.signal.aborted) return;
            const parsed = usesStructuredScheduleBackend
              ? contentFromRecouvrementScheduleResponse(response)
              : usesStructuredDraftBackend
                ? contentFromRecouvrementDraftResponse(response)
                : usesStructuredSummaryBackend
                  ? contentFromCaseSummaryResponse(response)
                  : usesStructuredPaymentOptionsBackend
                    ? contentFromPaymentOptionsResponse(response)
                    : contentFromRecouvrementContactResponse(response);
            completeAfterThinkingMinimum(() => {
              setAssistantContent(parsed);
              setSelectedVersionId(parsed.versions[0]?.id ?? "v1");
              setDrawerStateModel((current) => ({
                ...current,
                pendingAction: null,
                lastSuccessfulBackendIntent:
                  route.backendIntent ?? current.lastSuccessfulBackendIntent,
              }));
              setAssistantThread((current) =>
                current.map((item) =>
                  item.id === assistantMessage.id
                    ? { ...item, content: response.visibleReply, streaming: false }
                    : item,
                ),
              );
              setAssistantStatus("ready");
            });
          })
          .catch((err) => {
            if (controller.signal.aborted) return;
            console.warn("[recouvrement-assistant] structured backend unavailable", err);
            if (usesStructuredDraftBackend) {
              const fallbackResponse = buildDraftBackendUnavailableFallback(currentArtifact);
              const parsed = contentFromRecouvrementDraftResponse(fallbackResponse);
              completeAfterThinkingMinimum(() => {
                setAssistantContent(parsed);
                setSelectedVersionId(parsed.versions[0]?.id ?? "v1");
                setAssistantThread((current) =>
                  current.map((item) =>
                    item.id === assistantMessage.id
                      ? { ...item, content: fallbackResponse.visibleReply, streaming: false }
                      : item,
                  ),
                );
                setAssistantStatus("ready");
              });
              return;
            }
            if (usesStructuredScheduleBackend) {
              const proposal = buildScheduleProposalDraft(
                trimmedMessage,
                route.extractedSlots.durationMonths,
              );
              const parsed = contentFromScheduleProposal(proposal);
              completeAfterThinkingMinimum(() => {
                setAssistantContent(parsed);
                setSelectedVersionId(parsed.versions[0]?.id ?? "v1");
                setAssistantThread((current) =>
                  current.map((item) =>
                    item.id === assistantMessage.id
                      ? { ...item, content: proposal.visibleReply, streaming: false }
                      : item,
                  ),
                );
                setAssistantStatus("ready");
              });
              return;
            }
            if (usesStructuredSummaryBackend) {
              const summary = buildCaseSummaryDraft();
              const parsed = contentFromCaseSummaryResponse(summary);
              completeAfterThinkingMinimum(() => {
                setAssistantContent(parsed);
                setSelectedVersionId("v1");
                setAssistantThread((current) =>
                  current.map((item) =>
                    item.id === assistantMessage.id
                      ? { ...item, content: summary.visibleReply, streaming: false }
                      : item,
                  ),
                );
                setAssistantStatus("ready");
              });
              return;
            }
            if (usesStructuredPaymentOptionsBackend) {
              const fallbackResponse = buildPaymentOptionsBackendUnavailableFallback();
              const parsed = contentFromPaymentOptionsResponse(fallbackResponse);
              completeAfterThinkingMinimum(() => {
                setAssistantContent(parsed);
                setSelectedVersionId("v1");
                setAssistantThread((current) =>
                  current.map((item) =>
                    item.id === assistantMessage.id
                      ? { ...item, content: fallbackResponse.visibleReply, streaming: false }
                      : item,
                  ),
                );
                setAssistantStatus("ready");
              });
              return;
            }
            const fallbackResponse = buildContactRuleBackendUnavailableFallback();
            const parsed = contentFromRecouvrementContactResponse(fallbackResponse);
            completeAfterThinkingMinimum(() => {
              setAssistantContent(parsed);
              setSelectedVersionId("v1");
              setAssistantError(fallbackResponse.visibleReply);
              setAssistantThread((current) =>
                current.map((item) =>
                  item.id === assistantMessage.id
                    ? { ...item, content: fallbackResponse.visibleReply, streaming: false }
                    : item,
                ),
              );
              setAssistantStatus("ready");
            });
          });
        return;
      }

      void runLegacyStream().catch((err) => {
        if (controller.signal.aborted) return;
        const message = err instanceof Error ? err.message : String(err);
        setAssistantError(message);
        setAssistantStatus("error");
        setAssistantThread((current) =>
          current.map((item) =>
            item.id === assistantMessage.id
              ? { ...item, content: message, streaming: false, error: true }
              : item,
          ),
        );
      });
    },
    [activeAssistantTab, locale],
  );

  const selectAssistantTab = useCallback(
    (tab: string) => {
      const nextTask = assistantTaskForTab(tab);
      setDrawerStateModel((current) => ({
        ...current,
        currentTask: nextTask,
        selectedArtifactFamily: artifactFamilyForTask(nextTask),
        pendingAction: null,
      }));
      if (tab === activeAssistantTab) {
        regenerateAssistantContent();
        return;
      }
      setActiveAssistantTab(tab);
    },
    [activeAssistantTab, regenerateAssistantContent],
  );

  const sendAssistantFollowUp = useCallback(() => {
    sendAssistantTurn(assistantInput, false);
  }, [assistantInput, sendAssistantTurn]);

  const handleAssistantAction = useCallback(
    (action: string) => {
      const normalized = normalizeAssistantText(action);
      const currentArtifact =
        drawerStateModelRef.current.currentArtifact ?? assistantContentRef.current.artifact;
      setDrawerStateModel((current) => ({
        ...current,
        pendingAction: action,
      }));

      const applyActionResponse = (response: RecouvrementAssistantResponse) => {
        const parsed = contentFromArtifactActionResponse(response, assistantContentRef.current);
        setAssistantContent(parsed);
        setSelectedVersionId(parsed.versions[0]?.id ?? "v1");
        setAssistantStatus("ready");
        setAssistantThread((current) => [
          ...current.filter((item) => !item.streaming),
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: response.visibleReply,
          },
        ]);
        setDrawerStateModel((current) => ({
          ...current,
          currentArtifact: response.artifact,
          artifactHistory: [...current.artifactHistory, response.artifact].slice(-8),
          pendingAction: null,
        }));
      };

      const runBackendArtifactAction = (
        actionName: string,
        fallback: () => RecouvrementAssistantResponse,
      ) => {
        if (!currentArtifact) return;
        const controller = new AbortController();
        abortRef.current?.abort();
        abortRef.current = controller;
        const loadingStartedAt = Date.now();
        const completeAfterThinkingMinimum = (callback: () => void) => {
          const remainingMs = Math.max(
            0,
            MIN_ASSISTANT_THINKING_MS - (Date.now() - loadingStartedAt),
          );
          window.setTimeout(() => {
            if (controller.signal.aborted) return;
            callback();
          }, remainingMs);
        };
        const conversationId = conversationIdRef.current ?? crypto.randomUUID();
        conversationIdRef.current = conversationId;
        setAssistantError(null);
        setAssistantStatus("loading");

        void sendRecouvrementAssistantAction({
          artifact: currentArtifact,
          actionName,
          conversationId,
          turnId: crypto.randomUUID(),
          signal: controller.signal,
        })
          .then((response) => {
            if (controller.signal.aborted) return;
            completeAfterThinkingMinimum(() => applyActionResponse(response));
          })
          .catch((err) => {
            if (controller.signal.aborted) return;
            console.warn("[recouvrement-assistant] structured action backend unavailable", err);
            completeAfterThinkingMinimum(() => applyActionResponse(fallback()));
          });
      };

      if (normalized.includes("inserer")) {
        runBackendArtifactAction("insert_artifact_in_case", () =>
          buildArtifactInsertionPreparedResponse(
            currentArtifact as RecouvrementAssistantArtifact,
            action,
          ),
        );
        return;
      }

      if (normalized.includes("soumettre") || normalized.includes("validation")) {
        runBackendArtifactAction("submit_for_validation", () =>
          buildArtifactPendingValidationResponse(
            currentArtifact as RecouvrementAssistantArtifact,
            action,
          ),
        );
        return;
      }

      if (normalized.includes("copier")) {
        if (!currentArtifact) return;
        const response: RecouvrementAssistantResponse = {
          visibleReply:
            "Contenu prêt à être copié depuis l'artefact courant. Aucun message envoyé.",
          artifact: currentArtifact,
          cardUpdates: {
            summary: assistantContentRef.current.summary,
            complianceChecks: [
              "Artefact courant conservé",
              "Aucun message envoyé",
              "Aucune action irréversible exécutée",
            ],
            nextActions: assistantContentRef.current.nextActions,
          },
          suggestedActions: assistantContentRef.current.nextActions,
          businessEvents: [],
          businessScores: [],
          decisions: {
            action: "copy_artifact_text",
            status: "prepared",
            artifact_id: currentArtifact.id,
          },
        };
        const parsed = contentFromArtifactActionResponse(response, assistantContentRef.current);
        setAssistantContent(parsed);
        setAssistantStatus("ready");
        setAssistantThread((current) => [
          ...current.filter((item) => !item.streaming),
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: response.visibleReply,
          },
        ]);
        setDrawerStateModel((current) => ({ ...current, pendingAction: null }));
        return;
      }

      if (normalized.includes("rappel") && currentArtifact?.type === "contact_rule_v1") {
        runBackendArtifactAction("prepare_reminder_tomorrow", () =>
          buildReminderPreparedResponse(currentArtifact),
        );
        return;
      }

      if (normalized.includes("message") || normalized.includes("email")) {
        sendAssistantTurn(action, false, { forcedTask: "draft_reminder", pendingAction: action });
        return;
      }

      if (
        normalized.includes("echeancier") ||
        normalized.includes("duree") ||
        normalized.includes("comparer")
      ) {
        sendAssistantTurn(action, false, { forcedTask: "propose_schedule", pendingAction: action });
        return;
      }

      if (
        normalized.includes("regle") ||
        normalized.includes("rappel") ||
        normalized.includes("reporter") ||
        normalized.includes("appel")
      ) {
        sendAssistantTurn(action, false, {
          forcedTask: "check_contact_rule",
          pendingAction: action,
        });
        return;
      }

      if (normalized.includes("relance") || normalized.includes("modifier")) {
        sendAssistantTurn(action, false, { forcedTask: "draft_reminder", pendingAction: action });
      }
    },
    [sendAssistantTurn],
  );

  useEffect(() => {
    if (assistantStatus !== "loading") {
      setThinkingStep(0);
      return;
    }
    const interval = window.setInterval(() => {
      setThinkingStep((step) => step + 1);
    }, 1350);
    return () => window.clearInterval(interval);
  }, [assistantStatus]);

  // biome-ignore lint/correctness/useExhaustiveDependencies: generationNonce intentionally retriggers a fresh assistant turn.
  useEffect(() => {
    if (!isAssistantOpen) return;
    if (skipNextAssistantAutoTurnRef.current) {
      skipNextAssistantAutoTurnRef.current = false;
      return;
    }
    sendAssistantTurn(assistantPromptForTab(activeAssistantTab), true, {
      forcedTask: assistantTaskForTab(activeAssistantTab),
    });
  }, [activeAssistantTab, generationNonce, isAssistantOpen, sendAssistantTurn]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  return (
    <div className="min-h-screen bg-[#c9ccd1] font-sans text-[#050816]">
      <div className="mx-auto min-h-screen max-w-[1718px] bg-white">
        <div className="flex min-h-screen flex-col">
          <header className="flex min-h-[69px] shrink-0 flex-wrap items-center gap-5 border-[#d0d0d0] border-b bg-white px-4 py-2 sm:px-6 lg:flex-nowrap lg:px-[23px]">
            <CreditAuroreLogo className="min-w-[250px] gap-[9px]" gradientIdPrefix="caRecLogo" />
            <label className="relative order-last block w-full max-w-[430px] md:order-none lg:ml-auto">
              <Search className="-translate-y-1/2 absolute top-1/2 left-4 h-5 w-5 text-[#050816]" />
              <input
                aria-label="Rechercher un dossier ou un client"
                placeholder="Rechercher un dossier, un client…"
                readOnly
                className="h-11 w-full cursor-default rounded-[4px] border border-[#d7d9e1] bg-white pr-4 pl-12 text-[#050816] text-sm outline-none transition placeholder:text-[#5d6275] focus:border-[#b99245] focus:ring-2 focus:ring-[#b99245]/20"
              />
            </label>
            <div className="flex items-center gap-4 sm:gap-6">
              <button
                type="button"
                aria-label="Aide"
                className="hidden flex-col items-center gap-1 rounded-[4px] text-[10.5px] outline-none transition focus-visible:ring-2 focus-visible:ring-[#b99245]/35 sm:flex"
              >
                <CircleHelp className="h-[22px] w-[22px]" />
                Aide
              </button>
              <button
                type="button"
                aria-label="Notifications, 3 nouvelles"
                className="relative flex flex-col items-center gap-1 rounded-[4px] text-[10.5px] outline-none transition focus-visible:ring-2 focus-visible:ring-[#b99245]/35"
              >
                <Bell className="h-[22px] w-[22px]" />
                <span className="-top-1 absolute right-1 grid h-4 min-w-4 place-items-center rounded-full bg-[#b99245] px-1 text-[#050816] text-[9px]">
                  3
                </span>
                Notifications
              </button>
              <button
                type="button"
                aria-label="Compte Julie Dubois, chargée de recouvrement"
                className="flex items-center gap-3 rounded-[4px] outline-none transition focus-visible:ring-2 focus-visible:ring-[#b99245]/35"
              >
                <span className="grid h-10 w-10 place-items-center rounded-full bg-[#fbf0dd] font-bold text-[#050816]">
                  JD
                </span>
                <span className="hidden text-left sm:block">
                  <span className="block font-bold text-sm">Julie Dubois</span>
                  <span className="block text-[#050816]/65 text-xs">Chargée de recouvrement</span>
                </span>
                <ChevronDown className="h-5 w-5" />
              </button>
            </div>
          </header>

          <div className="grid min-h-0 flex-1 lg:grid-cols-[258px_minmax(0,1fr)]">
            <aside className="hidden min-h-0 flex-col border-[#d8d8d8] border-r bg-white lg:flex">
              <div className="border-[#e2e2e6] border-b px-6 py-8">
                <p className="font-extrabold text-[#b99245] text-sm uppercase tracking-[0]">
                  Recouvrement
                </p>
                <p className="mt-2 text-[#565656] text-xs leading-5">
                  File interne et actions dossiers
                </p>
              </div>
              <nav className="flex flex-col gap-1 px-4 py-6" aria-label="Navigation recouvrement">
                {navigation.map(({ label, Icon, count, active }) => (
                  <button
                    key={label}
                    type="button"
                    className={cn(
                      "flex min-h-[52px] items-center gap-4 rounded-[5px] px-4 text-left font-bold text-[0.92rem] transition",
                      active
                        ? "bg-[#fbf0dd] text-[#050816] shadow-[inset_3px_0_0_#b99245]"
                        : "text-[#333] hover:bg-[#f5f4f2]",
                    )}
                  >
                    <Icon
                      className={cn(
                        "h-5 w-5 shrink-0",
                        active ? "fill-current text-[#b99245]" : "text-[#1d2334]",
                      )}
                    />
                    <span>{label}</span>
                    {count ? <CountBadge count={count} className="ml-auto" /> : null}
                  </button>
                ))}
              </nav>
              <div className="mt-auto border-[#e2e2e6] border-t px-6 py-7">
                <div className="flex items-start gap-3 text-[#050816] text-sm leading-5">
                  <LockKeyhole className="mt-0.5 h-5 w-5 shrink-0" />
                  <p>
                    Accès limité
                    <br />
                    aux dossiers assignés
                  </p>
                </div>
                <div className="mt-7 flex items-center gap-3 text-sm">
                  <span className="h-3 w-3 rounded-full bg-[#139b45]" />
                  En ligne
                </div>
              </div>
            </aside>

            <main className="min-h-0 overflow-y-auto bg-[radial-gradient(circle_at_62%_8%,rgba(231,235,246,0.58),transparent_32%),#fbfbfd]">
              <div className="px-4 py-10 sm:px-6 lg:py-11">
                <div className="mx-auto max-w-[1274px]">
                  <div className="mb-8">
                    <h1 className="!font-sans !text-[#050816] font-extrabold text-[2rem] leading-tight tracking-[0]">
                      Bonjour Julie,
                    </h1>
                    <p className="mt-2 text-[#071044] text-[1.12rem]">
                      Votre file du jour est prête.
                    </p>
                  </div>

                  <div
                    className={cn(
                      "grid gap-[31px]",
                      assistantMode === "pinned"
                        ? "xl:grid-cols-[minmax(0,1fr)] xl:pr-[520px]"
                        : "xl:grid-cols-[minmax(0,1fr)_352px]",
                    )}
                  >
                    <section className="min-w-0">
                      <section className={cn(cardClass, "p-6 sm:p-8")}>
                        <div className="mb-5">
                          <span className="inline-flex rounded-[4px] bg-[#fff3e4] px-3 py-1.5 font-bold text-[#d97700] text-xs uppercase">
                            À traiter maintenant
                          </span>
                        </div>
                        <div className="grid items-center gap-8 lg:grid-cols-[360px_minmax(0,1fr)_96px]">
                          <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:gap-7">
                            <span className="grid h-[78px] w-[78px] shrink-0 place-items-center rounded-full bg-[#fbf0dd] font-semibold text-[#d97700] text-[1.65rem] shadow-[inset_0_1px_0_rgba(255,255,255,0.9)]">
                              MD
                            </span>
                            <div className="min-w-0">
                              <div className="flex flex-nowrap items-center gap-3">
                                <h2 className="!font-sans !text-[#071044] font-bold text-[1.5rem] leading-8 tracking-[0]">
                                  RC-2048
                                </h2>
                                <span className="shrink-0 rounded-[6px] bg-[#ffe8e5] px-2.5 py-1 font-medium text-[#f23932] text-[0.68rem]">
                                  Promesse non tenue
                                </span>
                              </div>
                              <p className="mt-2 text-[0.9rem] leading-[1.2rem]">M. D.</p>
                              <div className="mt-3 flex items-center gap-5 font-semibold text-[0.94rem] leading-5">
                                <span>840,00 €</span>
                                <span className="h-1 w-1 rounded-full bg-[#071044]" />
                                <span className="font-medium">Retard 32 jours</span>
                              </div>
                              <div className="mt-4 inline-flex items-center gap-3 rounded-[5px] bg-[#e9f7e9] px-4 py-2 text-[#145b2b] text-[0.86rem] leading-[1.15rem]">
                                <CircleCheck className="h-4 w-4 shrink-0" />
                                <span>
                                  Contact autorisé aujourd'hui
                                  <br />
                                  de 8h à 20h
                                </span>
                              </div>
                            </div>
                          </div>

                          <div className="border-[#dfe2ec] border-t pt-6 lg:border-t-0 lg:border-l lg:pt-0 lg:pl-8">
                            <h3 className="mb-4 !font-sans !text-[#d97700] font-bold text-sm">
                              Pourquoi ce dossier ?
                            </h3>
                            <ul className="space-y-2.5 text-[0.78rem]">
                              {reasons.map((reason) => (
                                <li key={reason} className="flex items-start gap-3">
                                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-[#158d3c]" />
                                  <span className="leading-[1.15rem]">{reason}</span>
                                </li>
                              ))}
                            </ul>
                          </div>

                          <div className="relative hidden h-24 w-24 place-items-center rounded-full bg-[#fbf0dd] text-[#d97700] shadow-[inset_0_1px_0_rgba(255,255,255,0.9)] lg:grid">
                            <CalendarDays className="h-12 w-12" strokeWidth={1.8} />
                            <Phone
                              className="absolute right-[12px] bottom-[10px] h-6 w-6 rotate-[-18deg]"
                              strokeWidth={2.2}
                            />
                          </div>
                        </div>

                        <div className="mt-10 flex flex-col gap-5 border-[#e4e6ee] border-t pt-6 lg:flex-row lg:items-center lg:justify-between">
                          <div>
                            <p className="font-bold text-sm">Action recommandée</p>
                            <p className="mt-1 text-[0.9rem]">
                              Préparer un échéancier de remboursement.
                            </p>
                          </div>
                          <div className="flex flex-wrap items-center gap-3 lg:flex-nowrap">
                            <button
                              type="button"
                              className="inline-flex h-11 w-[196px] items-center justify-center gap-3 rounded-[8px] bg-[linear-gradient(180deg,#e38a00,#cf7300)] font-bold text-sm text-white shadow-[0_10px_22px_rgba(217,119,0,0.22)] transition hover:bg-[#c96f00]"
                            >
                              Préparer l'échéancier
                              <ChevronRight className="h-5 w-5" />
                            </button>
                            <button
                              type="button"
                              className="inline-flex h-11 w-[122px] items-center justify-center gap-3 rounded-[8px] border border-[#cfd4e3] bg-white font-semibold text-sm transition hover:bg-[#f7f8fb]"
                            >
                              Reporter
                              <Clock3 className="h-5 w-5" />
                            </button>
                            <button
                              type="button"
                              onClick={() => openAssistant("Préparer une relance")}
                              className="inline-flex h-11 w-[198px] items-center justify-center gap-2 rounded-lg px-1.5 font-semibold text-[#6048ff] text-[0.74rem] transition hover:bg-[#f4f1ff]"
                            >
                              <Sparkles className="h-4 w-4" />
                              Préparer avec l'assistant
                            </button>
                          </div>
                        </div>
                      </section>

                      <section className="relative mt-8 rounded-[6px] border border-[#c8bbff] bg-[linear-gradient(120deg,#fbfaff,#f9f7ff)] py-6 pr-6 pl-5 shadow-[0_14px_30px_rgba(96,72,255,0.055)]">
                        <AssistantCardBloom />
                        <div className="relative z-10 mb-6 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                          <div>
                            <h2 className="flex flex-wrap items-center gap-3 !font-sans !text-[#6048ff] font-bold text-sm uppercase tracking-[0]">
                              <Sparkles className="h-5 w-5" />
                              Assistant de traitement
                              <span className="rounded-full border border-[#c8bbff] bg-white px-2.5 py-1 font-bold text-[#6048ff] text-[0.68rem]">
                                RC-2048
                              </span>
                            </h2>
                            <p className="mt-2 max-w-[520px] text-[#071044] text-sm">
                              Aide contextualisée sur ce dossier prioritaire.
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => openAssistant()}
                            className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-[7px] border border-[#9d8cff] bg-white px-4 font-bold text-[#6048ff] text-xs shadow-[0_8px_18px_rgba(96,72,255,0.12)] transition hover:bg-[#f4f1ff]"
                          >
                            Ouvrir l'assistant complet
                            <ChevronRight className="h-4 w-4" />
                          </button>
                        </div>
                        <div className="relative z-10 grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
                          {assistantActions.map(({ label, description, Icon }) => (
                            <button
                              key={label}
                              type="button"
                              onClick={() => openAssistant(label)}
                              className="flex h-[112px] items-center gap-3 overflow-hidden rounded-[5px] border border-[#e2defd] bg-white px-3.5 py-3 text-left shadow-[0_8px_18px_rgba(96,72,255,0.035)] transition hover:border-[#b7aaff] hover:bg-[#fbfaff]"
                            >
                              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-[#f0edff] text-[#6048ff]">
                                <Icon className="h-5 w-5" />
                              </span>
                              <span className="min-w-0 flex-1">
                                <span className="block font-bold text-[0.76rem] leading-[1rem]">
                                  {label}
                                </span>
                                <span className="mt-1.5 block text-[0.66rem] leading-[0.98rem]">
                                  {description}
                                </span>
                              </span>
                              <ChevronRight className="ml-auto h-3.5 w-3.5 shrink-0" />
                            </button>
                          ))}
                        </div>
                      </section>

                      <section className="mt-10">
                        <h2 className="mb-5 !font-sans !text-[#050816] font-extrabold text-2xl leading-7">
                          À faire ensuite
                        </h2>
                        <div className="grid gap-6 md:grid-cols-3">
                          {nextItems.map(({ value, label, detail, Icon, accent }) => (
                            <button
                              key={label}
                              type="button"
                              className="flex h-[154px] flex-col rounded-[6px] border border-[#dfe2ec] bg-white p-6 text-left shadow-[0_2px_8px_rgba(0,0,0,0.055)] transition hover:border-[#d97700]/40 hover:shadow-[0_8px_20px_rgba(7,16,68,0.07)]"
                            >
                              <span className="flex items-center gap-4">
                                <span
                                  className={cn(
                                    "grid h-12 w-12 place-items-center rounded-full",
                                    accent === "orange"
                                      ? "bg-[#fff1dc] text-[#e48700]"
                                      : "bg-[#f0edff] text-[#6048ff]",
                                  )}
                                >
                                  <Icon className="h-6 w-6" />
                                </span>
                                <span className="font-bold text-[2.2rem] leading-none">
                                  {value}
                                </span>
                                <span className="font-bold text-sm">
                                  {label}
                                  <br />
                                  <span className="font-semibold">{detail}</span>
                                </span>
                              </span>
                              <span className="mt-auto flex items-center justify-end border-[#e4e6ee] border-t pt-3 font-semibold text-[#0047ff] text-sm">
                                Voir la liste
                                <ChevronRight className="ml-auto h-5 w-5 text-[#071044]" />
                              </span>
                            </button>
                          ))}
                        </div>
                      </section>

                      <section className="mt-10 flex min-h-[72px] flex-col items-start gap-3 rounded-[6px] border border-[#dfe2ec] bg-white px-6 py-4 shadow-[0_2px_8px_rgba(0,0,0,0.055)] sm:flex-row sm:items-center">
                        <Info className="mr-4 h-5 w-5" />
                        <span className="mr-6 font-bold">A noter aujourd'hui</span>
                        <span className="hidden h-8 w-px bg-[#dfe2ec] sm:block" />
                        <p className="text-sm text-[#071044]/80 sm:ml-6">
                          3 dossiers sont joignables entre 17h et 19h selon les règles de contact.
                        </p>
                        <button
                          type="button"
                          className="inline-flex items-center gap-3 font-semibold text-[#0047ff] text-sm sm:ml-auto"
                        >
                          Voir lesquels
                          <ChevronRight className="h-5 w-5" />
                        </button>
                      </section>
                    </section>

                    <aside
                      className={cn(
                        "space-y-8 xl:sticky xl:top-8 xl:self-start",
                        assistantMode === "pinned" && "xl:hidden",
                      )}
                    >
                      <section className={cn(cardClass, "overflow-hidden")}>
                        <div className="border-[#e4e6ee] border-b px-6 py-6">
                          <h2 className="!font-sans !text-[#050816] font-extrabold text-lg">
                            Actions rapides
                          </h2>
                          <p className="mt-1.5 text-[#5d6275] text-xs">
                            Actions générales sur la file du jour.
                          </p>
                        </div>
                        <div className="divide-y divide-[#e4e6ee]">
                          {quickActions.map(({ label, detail, Icon }) => (
                            <button
                              key={label}
                              type="button"
                              className="flex w-full items-center gap-4 px-6 py-5 text-left transition hover:bg-[#f7f8fb]"
                            >
                              <Icon className="h-6 w-6 shrink-0" />
                              <span>
                                <span className="block font-bold text-sm">{label}</span>
                                <span className="mt-1 block text-xs">{detail}</span>
                              </span>
                              <ChevronRight className="ml-auto h-5 w-5" />
                            </button>
                          ))}
                        </div>
                      </section>

                      <section className={cn(cardClass, "p-6")}>
                        <div className="mb-6 flex items-center justify-between">
                          <h2 className="!font-sans !text-[#050816] font-extrabold text-lg">
                            Cadre de contact
                          </h2>
                          <span className="rounded-full bg-[#e4f5dd] px-3 py-1 font-bold text-[#187434] text-xs">
                            RC-2048
                          </span>
                        </div>
                        <div className="mb-6 flex items-start gap-4 rounded-[5px] bg-[#edf9df] px-5 py-5 text-[#145b2b]">
                          <CircleCheck className="mt-0.5 h-5 w-5" />
                          <p className="font-semibold text-sm">
                            Contact autorisé aujourd'hui
                            <br />
                            <span className="font-medium">8h - 20h</span>
                          </p>
                        </div>
                        <div className="space-y-5 text-sm">
                          <div>
                            <p className="mb-2 font-bold">Canal conseillé</p>
                            <p className="flex items-center gap-3">
                              <Phone className="h-5 w-5" />
                              Appel sortant
                            </p>
                          </div>
                          <div>
                            <p className="mb-2 font-bold">Alternative</p>
                            <p className="flex items-center gap-3">
                              <Mail className="h-5 w-5" />
                              Email de confirmation
                            </p>
                          </div>
                        </div>
                      </section>

                      <button
                        type="button"
                        onClick={() => openAssistant("Vérifier une règle")}
                        className="flex w-full items-center gap-4 rounded-[6px] border border-[#f1d8ab] bg-[linear-gradient(90deg,#fff8ec,#fff2de)] p-6 text-left shadow-[0_2px_8px_rgba(0,0,0,0.05)] transition hover:bg-[#ffefcf]"
                      >
                        <Sparkles className="h-7 w-7 text-[#071044]" />
                        <span>
                          <span className="block font-bold text-sm">
                            Besoin d'aide sur un dossier ?
                          </span>
                          <span className="mt-1 block text-xs">
                            Consultez les règles applicables
                          </span>
                        </span>
                        <ChevronRight className="ml-auto h-5 w-5" />
                      </button>
                    </aside>
                  </div>
                </div>
              </div>
            </main>
          </div>
        </div>
      </div>
      {assistantMode === "drawer" ? (
        <button
          type="button"
          aria-label="Fermer l'assistant"
          onClick={closeAssistant}
          className="fixed inset-x-0 bottom-0 top-[90px] z-40 bg-[#050816]/38 backdrop-blur-[1px] transition-opacity max-md:top-0"
        />
      ) : null}
      {assistantMode !== "closed" ? (
        <AssistantDrawer
          mode={assistantMode}
          activeTab={activeAssistantTab}
          content={assistantContent}
          error={assistantError}
          inputValue={assistantInput}
          messages={assistantThread}
          selectedVersionId={selectedVersionId}
          status={assistantStatus}
          thinkingLabel={thinkingLabel}
          onAction={handleAssistantAction}
          onClose={closeAssistant}
          onExpand={expandAssistant}
          onInputChange={setAssistantInput}
          onRegenerate={regenerateAssistantContent}
          onSelectVersion={setSelectedVersionId}
          onSendMessage={sendAssistantFollowUp}
          onSelectTab={selectAssistantTab}
          onTogglePinned={togglePinnedAssistant}
        />
      ) : null}
      <DemoLauncherLink floating />
    </div>
  );
}
