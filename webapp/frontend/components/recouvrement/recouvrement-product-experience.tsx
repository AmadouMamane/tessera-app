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
import { useCallback, useEffect, useRef, useState } from "react";

import { CreditAuroreLogo } from "@/components/brand/credit-aurore-logo";
import { cn } from "@/lib/cn";

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

export type AssistantTask =
  | "summary"
  | "draft_reminder"
  | "propose_schedule"
  | "explain_payment_options"
  | "check_rule"
  | "explain_priority";

export type AssistantIntent =
  | "summarize_case"
  | "draft_reminder"
  | "propose_schedule"
  | "explain_payment_options"
  | "check_contact_rule"
  | "explain_priority"
  | "adjust_existing_proposal"
  | "ask_for_validation"
  | "small_clarification";

export type AssistantAction =
  | "PREPARE_CLIENT_MESSAGE_FROM_SCHEDULE"
  | "COMPARE_SCHEDULE_OPTIONS"
  | "ADJUST_SCHEDULE_DURATION"
  | "SUBMIT_FOR_VALIDATION"
  | "INSERT_ARTIFACT_IN_CASE"
  | "COPY_ARTIFACT_TEXT"
  | "PREPARE_CALL_SCRIPT"
  | "REPORT_CONTACT"
  | "CHECK_CONTACT_RULE"
  | "DRAFT_REMINDER"
  | "PROPOSE_SCHEDULE"
  | "SUMMARIZE_CASE";

export type AssistantArtifactType =
  | "case_summary_v1"
  | "reminder_draft_v1"
  | "schedule_proposal"
  | "schedule_proposal_v2"
  | "client_message_artifact"
  | "contact_rule_v1"
  | "payment_options_v1"
  | "priority_explanation_v1";

export type AssistantArtifactStatus = "draft" | "inserted" | "pending_validation";

export interface CurrentRecouvrementCase {
  reference: string;
  client: string;
  amountDue: string;
  daysLate: number;
  missedPromise: string;
  contactWindow: string;
  contactWindowText: string;
  contactChannel: string;
  alternativeChannel: string;
}

export interface ConversationState {
  content: GeneratedAssistantContent;
  thread: AssistantThreadMessage[];
  currentArtifact: AssistantArtifact | null;
}

export interface RoutedUserTurn {
  intent: AssistantIntent;
  confidence: number;
  extractedSlots: Record<string, boolean | number | string | null>;
  targetTask: AssistantTask;
  visibleReply: string;
  cardUpdates: Partial<GeneratedAssistantContent>;
  suggestedActions: string[];
}

export interface AssistantArtifact {
  id: string;
  type: AssistantArtifactType;
  task: AssistantTask;
  title: string;
  status: AssistantArtifactStatus;
  content: GeneratedAssistantContent;
  sourceArtifactId?: string;
}

export interface TreatmentAssistantState {
  currentCase: CurrentRecouvrementCase;
  currentTask: AssistantTask;
  currentArtifact: AssistantArtifact | null;
  artifacts: AssistantArtifact[];
  content: GeneratedAssistantContent;
  thread: AssistantThreadMessage[];
}

export interface AssistantStateTransition {
  state: TreatmentAssistantState;
  visibleReply: string;
  artifact: AssistantArtifact;
  action?: AssistantAction;
  routedTurn?: RoutedUserTurn;
}

const assistantActions = [
  {
    label: "Résumer ce dossier",
    task: "summary" as const,
    description: "Obtenir les points clés en quelques secondes",
    prompt:
      "Résume uniquement le dossier RC-2048 : points clés, pourquoi il est prioritaire, et prochaines actions possibles. Ne rédige pas de relance dans ce tour.",
    Icon: FileText,
  },
  {
    label: "Rédiger une relance",
    task: "draft_reminder" as const,
    description: "Message personnalisé prêt à envoyer",
    prompt: "Prépare une relance amiable et propose un échéancier adapté à la situation.",
    Icon: PenLine,
  },
  {
    label: "Vérifier une règle",
    task: "check_rule" as const,
    description: "Contrôler la conformité en un clic",
    prompt:
      "Vérifie uniquement la règle de contact applicable à RC-2048 : plage autorisée, canal conseillé, alternative, et validations nécessaires. N'utilise pas de conditions générales externes.",
    Icon: ShieldCheck,
  },
  {
    label: "Proposer un échéancier",
    task: "propose_schedule" as const,
    description: "Simulation adaptée à la situation",
    prompt:
      "Propose un échéancier indicatif pour les 840,00 € de RC-2048 et indique les validations nécessaires. Ne crée pas l'échéancier sans validation.",
    Icon: CalendarDays,
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

const defaultAssistantTask: AssistantTask = "draft_reminder";

const assistantTabs: Array<{ label: string; task: AssistantTask }> = [
  { label: "Préparer une relance", task: "draft_reminder" },
  { label: "Proposer un échéancier", task: "propose_schedule" },
  { label: "Vérifier une règle", task: "check_rule" },
  { label: "Résumer", task: "summary" },
];

const contextItems = [
  "Dossier : RC-2048",
  "Client : M. D.",
  "Montant dû : 840,00 €",
  "Retard : 32 jours",
  "Promesse de paiement non tenue le 12 juin.",
  "Contact autorisé aujourd'hui de 8h à 20h",
];

const currentRecouvrementCase: CurrentRecouvrementCase = {
  reference: "RC-2048",
  client: "M. D.",
  amountDue: "840,00 €",
  daysLate: 32,
  missedPromise: "promesse de paiement non tenue le 12 juin",
  contactWindow: "8h–20h",
  contactWindowText: "8h et 20h",
  contactChannel: "appel sortant",
  alternativeChannel: "email de confirmation",
};

type AssistantMode = "closed" | "drawer" | "pinned" | "focus";
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
  context: string[];
  proposition: string;
  summary: string[];
  priorityReasons: string[];
  businessFactors: string[];
  recommendedAction: string;
  contactFrame: string[];
  allowedItems: string[];
  validationItems: string[];
  scheduleItems: string[];
  scheduleVersionLabel: string;
  clientMessage: string;
  paymentOptions: string[];
  paymentRecommendation: string;
  versions: DraftVersion[];
  paymentPlan: string;
  complianceChecks: string[];
  nextActions: string[];
  rawResponse: string;
}

const fallbackAssistantContent: GeneratedAssistantContent = {
  context: [],
  proposition: "",
  summary: [],
  priorityReasons: [],
  businessFactors: [],
  recommendedAction: "",
  contactFrame: [],
  allowedItems: [],
  validationItems: [],
  scheduleItems: [],
  scheduleVersionLabel: "",
  clientMessage: "",
  paymentOptions: [],
  paymentRecommendation: "",
  versions: [],
  paymentPlan: "",
  complianceChecks: [],
  nextActions: [],
  rawResponse: "",
};

export function createInitialTreatmentAssistantState(): TreatmentAssistantState {
  return {
    currentCase: currentRecouvrementCase,
    currentTask: defaultAssistantTask,
    currentArtifact: null,
    artifacts: [],
    content: fallbackAssistantContent,
    thread: [],
  };
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

const recouvrementThinkingSteps: Record<AssistantTask, string[]> = {
  summary: ["Analyse du contexte...", "Préparation du résumé...", "Identification des actions..."],
  draft_reminder: [
    "Analyse du contexte...",
    "Rédaction du brouillon...",
    "Vérification des règles...",
  ],
  propose_schedule: [
    "Analyse du contexte...",
    "Préparation de l'échéancier...",
    "Vérification des règles...",
  ],
  explain_payment_options: [
    "Analyse du contexte...",
    "Identification des options de règlement...",
    "Vérification des validations nécessaires...",
  ],
  check_rule: [
    "Analyse du contexte...",
    "Vérification des règles...",
    "Préparation des actions possibles...",
  ],
  explain_priority: [
    "Analyse du contexte...",
    "Identification des facteurs métier...",
    "Préparation de la recommandation...",
  ],
};

const defaultAssistantPrompt =
  "Prépare une relance amiable et propose un échéancier adapté à la situation.";

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

function AssistantCardBloom() {
  return (
    <svg
      className="pointer-events-none absolute top-[56px] right-[-15px] z-30 h-[78px] w-[28px]"
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
  return assistantTabForTask(assistantTaskForAction(action));
}

function assistantTaskForAction(action: string): AssistantTask {
  const normalized = normalizeAssistantText(action);
  if (normalized.includes("prioritaire") || normalized.includes("priorite")) {
    return "explain_priority";
  }
  if (normalized.includes("echeancier") || normalized.includes("mensualite")) {
    return "propose_schedule";
  }
  if (
    normalized.includes("regle") ||
    normalized.includes("contact") ||
    normalized.includes("appeler")
  ) {
    return "check_rule";
  }
  if (normalized.includes("resumer") || normalized.includes("resume")) {
    return "summary";
  }
  return "draft_reminder";
}

function assistantTabForTask(task: AssistantTask) {
  return assistantTabs.find((tab) => tab.task === task)?.label ?? "Préparer une relance";
}

function assistantPromptForTask(task: AssistantTask) {
  if (task === "explain_priority") {
    return "Explique pourquoi RC-2048 est prioritaire et recommande la prochaine action métier.";
  }
  if (task === "explain_payment_options") {
    return "Explique les options de règlement autorisées pour RC-2048, recommande l'option à préparer et liste les validations nécessaires.";
  }
  const action = assistantActions.find((item) => item.task === task);
  return action?.prompt ?? defaultAssistantPrompt;
}

function assistantResultLabel(task: AssistantTask) {
  if (task === "summary") return "Voici le résumé du dossier RC-2048.";
  if (task === "check_rule") {
    return "Voici la règle de contact applicable à RC-2048.";
  }
  if (task === "propose_schedule") {
    return "Voici une proposition d'échéancier pour RC-2048.";
  }
  if (task === "explain_payment_options") {
    return "Voici les options de règlement possibles pour RC-2048.";
  }
  if (task === "explain_priority") return "Voici pourquoi RC-2048 est prioritaire.";
  return "Voici une proposition adaptée au dossier RC-2048.";
}

function normalizeAssistantText(value: string) {
  return value
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

function applyAssistantCardUpdates(
  current: GeneratedAssistantContent,
  updates: Partial<GeneratedAssistantContent>,
) {
  return {
    ...current,
    ...updates,
    context: updates.context ?? current.context,
    summary: updates.summary ?? current.summary,
    priorityReasons: updates.priorityReasons ?? current.priorityReasons,
    businessFactors: updates.businessFactors ?? current.businessFactors,
    contactFrame: updates.contactFrame ?? current.contactFrame,
    allowedItems: updates.allowedItems ?? current.allowedItems,
    validationItems: updates.validationItems ?? current.validationItems,
    scheduleItems: updates.scheduleItems ?? current.scheduleItems,
    paymentOptions: updates.paymentOptions ?? current.paymentOptions,
    versions: updates.versions ?? current.versions,
    complianceChecks: updates.complianceChecks ?? current.complianceChecks,
    nextActions: updates.nextActions ?? current.nextActions,
  };
}

function artifactTaskForType(type: AssistantArtifactType): AssistantTask {
  if (type === "case_summary_v1") return "summary";
  if (type === "reminder_draft_v1") return "draft_reminder";
  if (
    type === "schedule_proposal" ||
    type === "schedule_proposal_v2" ||
    type === "client_message_artifact"
  ) {
    return "propose_schedule";
  }
  if (type === "contact_rule_v1") return "check_rule";
  if (type === "payment_options_v1") return "explain_payment_options";
  return "explain_priority";
}

function artifactTitleForType(type: AssistantArtifactType) {
  if (type === "case_summary_v1") return "Résumé du dossier — RC-2048";
  if (type === "reminder_draft_v1") return "Brouillon de relance — RC-2048";
  if (type === "schedule_proposal") return "Proposition d'échéancier — RC-2048";
  if (type === "schedule_proposal_v2") return "Proposition d'échéancier — Version 2";
  if (type === "client_message_artifact") return "Message client préparé — RC-2048";
  if (type === "contact_rule_v1") return "Cadre de contact — RC-2048";
  if (type === "payment_options_v1") return "Options de règlement — RC-2048";
  return "Priorité du dossier — RC-2048";
}

function createAssistantArtifact(
  type: AssistantArtifactType,
  content: GeneratedAssistantContent,
  state: TreatmentAssistantState,
  sourceArtifactId?: string,
): AssistantArtifact {
  const sequence = state.artifacts.filter((artifact) => artifact.type === type).length + 1;
  return {
    id: `${type}-${sequence}`,
    type,
    task: artifactTaskForType(type),
    title: artifactTitleForType(type),
    status: "draft",
    content,
    sourceArtifactId,
  };
}

function artifactTypeForRoute(route: RoutedUserTurn): AssistantArtifactType {
  if (route.intent === "summarize_case") return "case_summary_v1";
  if (route.intent === "draft_reminder") return "reminder_draft_v1";
  if (route.intent === "explain_payment_options") return "payment_options_v1";
  if (route.intent === "check_contact_rule") return "contact_rule_v1";
  if (route.intent === "explain_priority") return "priority_explanation_v1";
  if (route.intent === "propose_schedule" || route.intent === "adjust_existing_proposal") {
    return route.extractedSlots.requestedMonths ? "schedule_proposal_v2" : "schedule_proposal";
  }
  return statefulFallbackArtifactType(route.targetTask);
}

function statefulFallbackArtifactType(task: AssistantTask): AssistantArtifactType {
  if (task === "summary") return "case_summary_v1";
  if (task === "draft_reminder") return "reminder_draft_v1";
  if (task === "propose_schedule") return "schedule_proposal";
  if (task === "check_rule") return "contact_rule_v1";
  if (task === "explain_payment_options") return "payment_options_v1";
  return "priority_explanation_v1";
}

function updateAssistantStateWithArtifact(
  state: TreatmentAssistantState,
  artifact: AssistantArtifact,
): TreatmentAssistantState {
  const otherArtifacts = state.artifacts.filter((item) => item.id !== artifact.id);
  return {
    ...state,
    currentTask: artifact.task,
    currentArtifact: artifact,
    artifacts: [...otherArtifacts, artifact],
    content: artifact.content,
  };
}

function updateCurrentArtifactStatus(
  state: TreatmentAssistantState,
  status: AssistantArtifactStatus,
  visibleReply: string,
  action: AssistantAction,
): AssistantStateTransition {
  const currentArtifact =
    state.currentArtifact ??
    createAssistantArtifact(statefulFallbackArtifactType(state.currentTask), state.content, state);
  const artifact = { ...currentArtifact, status };
  return {
    state: updateAssistantStateWithArtifact(state, artifact),
    visibleReply,
    artifact,
    action,
  };
}

export function assistantActionFromLabel(
  label: string,
  state?: TreatmentAssistantState,
): AssistantAction {
  const normalized = normalizeAssistantText(label);
  if (normalized.includes("rediger un email") && state?.currentTask === "check_rule") {
    return "CHECK_CONTACT_RULE";
  }
  if (
    normalized.includes("preparer le message") ||
    normalized.includes("message client") ||
    normalized.includes("rediger un email")
  ) {
    return "PREPARE_CLIENT_MESSAGE_FROM_SCHEDULE";
  }
  if (normalized.includes("comparer")) return "COMPARE_SCHEDULE_OPTIONS";
  if (
    normalized.includes("ajuster") ||
    normalized.includes("changer l'option") ||
    normalized.includes("changer l option")
  ) {
    return "ADJUST_SCHEDULE_DURATION";
  }
  if (
    normalized.includes("soumettre") ||
    normalized.includes("validation") ||
    normalized.includes("escalader") ||
    normalized.includes("responsable")
  ) {
    return "SUBMIT_FOR_VALIDATION";
  }
  if (normalized.includes("inserer")) return "INSERT_ARTIFACT_IN_CASE";
  if (normalized.includes("copier")) return "COPY_ARTIFACT_TEXT";
  if (normalized.includes("script") || normalized.includes("appel")) return "PREPARE_CALL_SCRIPT";
  if (normalized.includes("reporter") || normalized.includes("rappel")) return "REPORT_CONTACT";
  if (normalized.includes("regle") || normalized.includes("contact")) return "CHECK_CONTACT_RULE";
  if (normalized.includes("relance") || normalized.includes("brouillon")) return "DRAFT_REMINDER";
  if (normalized.includes("echeancier") || normalized.includes("mensualite")) {
    return "PROPOSE_SCHEDULE";
  }
  if (normalized.includes("resume") || normalized.includes("resumer")) return "SUMMARIZE_CASE";
  return "INSERT_ARTIFACT_IN_CASE";
}

function formatEuroAmount(amount: number) {
  return amount.toLocaleString("fr-FR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function extractRequestedScheduleMonths(message: string) {
  const normalized = normalizeAssistantText(message);
  const match = normalized.match(/\b(\d{1,2})\s*(?:mois|mensualites?)\b/);
  if (!match) return null;

  const months = Number(match[1]);
  return Number.isInteger(months) && months >= 2 && months <= 84 ? months : null;
}

function extractRequestedContactTime(message: string) {
  const normalized = normalizeAssistantText(message);
  const match =
    normalized.match(/(?:^|[^\d])(\d{1,2})\s*(?:h|heures?)(?:\s*(\d{1,2}))?\b/) ??
    normalized.match(/(?:^|[^\d])(\d{1,2})[:.](\d{2})\b/) ??
    normalized.match(/\b(?:a|vers|pour)\s+(\d{1,2})(?:\s*(?:h|:)\s*(\d{1,2}))?\b/);

  if (!match) return null;

  const hour = Number(match[1]);
  const minute = match[2] ? Number(match[2]) : 0;
  if (!Number.isInteger(hour) || !Number.isInteger(minute)) return null;
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null;

  return {
    hour,
    minute,
    label: minute > 0 ? `${hour}h${String(minute).padStart(2, "0")}` : `${hour}h`,
  };
}

function isContactTimeAllowed(time: { hour: number; minute: number }) {
  const minutes = time.hour * 60 + time.minute;
  return minutes >= 8 * 60 && minutes <= 20 * 60;
}

function isScheduleSpreadRequest(message: string) {
  const normalized = normalizeAssistantText(message);
  return (
    normalized.includes("etaler") ||
    normalized.includes("repartir") ||
    normalized.includes("plusieurs mois") ||
    normalized.includes("sur plusieurs") ||
    normalized.includes("mensualite") ||
    normalized.includes("echelonnement")
  );
}

function isSchedulePaymentRequest(message: string) {
  const normalized = normalizeAssistantText(message);
  return (
    extractRequestedScheduleMonths(message) !== null ||
    isScheduleSpreadRequest(message) ||
    normalized.includes("echeancier") ||
    (normalized.includes("paiement") &&
      (normalized.includes("proposer") ||
        normalized.includes("proposition") ||
        normalized.includes("relance") ||
        normalized.includes("plan") ||
        normalized.includes("solution")))
  );
}

function isPaymentOptionsRequest(message: string) {
  const normalized = normalizeAssistantText(message);
  const asksHow =
    normalized.includes("comment") ||
    normalized.includes("quelles options") ||
    normalized.includes("quels moyens") ||
    normalized.includes("peut-il") ||
    normalized.includes("peut il");
  const paymentTerms =
    normalized.includes("regler") ||
    normalized.includes("payer") ||
    normalized.includes("paiement") ||
    normalized.includes("reglement") ||
    normalized.includes("solde") ||
    normalized.includes("echeance");

  return paymentTerms && (asksHow || normalized.includes("options"));
}

function isContactRuleRequest(message: string) {
  const normalized = normalizeAssistantText(message);
  return (
    normalized.includes("appeler") ||
    normalized.includes("joindre") ||
    normalized.includes("contact") ||
    normalized.includes("regle de contact") ||
    normalized.includes("verifier une regle") ||
    normalized.includes("cadre de contact")
  );
}

function routeUserTurn(
  message: string,
  currentCase: CurrentRecouvrementCase,
  currentTask: AssistantTask,
  conversationState: ConversationState,
): RoutedUserTurn {
  const normalized = normalizeAssistantText(message);
  const requestedContactTime = extractRequestedContactTime(message);
  const requestedMonths = extractRequestedScheduleMonths(message);
  const baseSlots = {
    caseReference: currentCase.reference,
    client: currentCase.client,
    amountDue: currentCase.amountDue,
    currentTask,
    hasExistingCards: Object.values(conversationState.content).some((value) =>
      Array.isArray(value) ? value.length > 0 : Boolean(value),
    ),
  };

  if (isContactRuleRequest(message)) {
    if (requestedContactTime !== null && !isContactTimeAllowed(requestedContactTime)) {
      return {
        intent: "check_contact_rule",
        confidence: 0.98,
        extractedSlots: {
          ...baseSlots,
          requestedHour: requestedContactTime.hour,
          requestedTime: requestedContactTime.label,
          contactAllowed: false,
        },
        targetTask: "check_rule",
        visibleReply: `Non, vous ne devez pas appeler ${currentCase.client} à ${requestedContactTime.label}. Le contact téléphonique est autorisé aujourd'hui uniquement entre ${currentCase.contactWindowText}. Je peux vous aider à planifier un rappel demain ou à préparer un ${currentCase.alternativeChannel}.`,
        cardUpdates: {
          context: contextItems,
          contactFrame: [
            `Dossier : ${currentCase.reference}`,
            `Client : ${currentCase.client}`,
            `Appel à ${requestedContactTime.label} : non autorisé`,
            `Plage autorisée : ${currentCase.contactWindow}`,
            `Canal conseillé : ${currentCase.contactChannel} pendant la plage autorisée`,
            `Alternative : ${currentCase.alternativeChannel}`,
          ],
          allowedItems: [
            `Vous pouvez contacter ${currentCase.client} aujourd'hui entre ${currentCase.contactWindowText}.`,
          ],
          validationItems: [
            `Un appel à ${requestedContactTime.label} n'est pas autorisé. Reportez le contact sur une plage autorisée ou utilisez un canal autorisé si applicable.`,
          ],
          nextActions: [
            "Planifier un rappel demain",
            "Rédiger un email de confirmation",
            "Reporter le contact",
            "Voir la règle de contact",
          ],
        },
        suggestedActions: [
          "Planifier un rappel demain",
          "Rédiger un email de confirmation",
          "Reporter le contact",
          "Voir la règle de contact",
        ],
      };
    }

    return {
      intent: "check_contact_rule",
      confidence: 0.94,
      extractedSlots: {
        ...baseSlots,
        requestedHour: requestedContactTime?.hour ?? null,
        requestedTime: requestedContactTime?.label ?? null,
        contactAllowed: true,
      },
      targetTask: "check_rule",
      visibleReply: `Vous pouvez contacter ${currentCase.client} aujourd'hui entre ${currentCase.contactWindowText}. Le canal conseillé est l'${currentCase.contactChannel}.`,
      cardUpdates: {
        context: contextItems,
        contactFrame: [
          `Dossier : ${currentCase.reference}`,
          `Client : ${currentCase.client}`,
          "Contact autorisé aujourd'hui",
          `Plage : ${currentCase.contactWindow}`,
          `Canal conseillé : ${currentCase.contactChannel}`,
          `Alternative : ${currentCase.alternativeChannel}`,
        ],
        allowedItems: [
          `Vous pouvez contacter ${currentCase.client} aujourd'hui entre ${currentCase.contactWindowText}. Le canal recommandé est l'${currentCase.contactChannel}.`,
        ],
        validationItems: [
          "Aucune validation supplémentaire n'est nécessaire pour ce contact aujourd'hui.",
        ],
        nextActions: [
          "Préparer un script d'appel",
          "Rédiger un email de confirmation",
          "Reporter le contact",
          "Voir la règle de contact",
        ],
      },
      suggestedActions: [
        "Préparer un script d'appel",
        "Rédiger un email de confirmation",
        "Reporter le contact",
        "Voir la règle de contact",
      ],
    };
  }

  if (
    requestedMonths !== null ||
    isScheduleSpreadRequest(message) ||
    isSchedulePaymentRequest(message)
  ) {
    const months = requestedMonths ?? 3;
    const monthlyAmount = formatEuroAmount(840 / months);
    const hasExplicitMonths = requestedMonths !== null;
    return {
      intent: "propose_schedule",
      confidence: hasExplicitMonths ? 0.96 : 0.88,
      extractedSlots: {
        ...baseSlots,
        requestedMonths: requestedMonths ?? null,
        monthlyAmount: hasExplicitMonths ? `${monthlyAmount} €` : null,
        scheduleCreated: false,
      },
      targetTask: "propose_schedule",
      visibleReply: hasExplicitMonths
        ? `Un échéancier sur ${months} mois représenterait environ ${monthlyAmount} € par mois pour un montant dû de ${currentCase.amountDue}. Cette durée nécessite validation avant proposition au client. L'échéancier n'a pas été créé.`
        : `Pour ${currentCase.reference}, une option indicative consiste à répartir les ${currentCase.amountDue} sur plusieurs mensualités, sous réserve d'accord du client et de validation interne. L'échéancier n'a pas été créé.`,
      cardUpdates: hasExplicitMonths
        ? {
            context: contextItems,
            paymentPlan: `Échéancier indicatif sur ${months} mois pour un montant dû de ${currentCase.amountDue}. La mensualité serait d'environ ${monthlyAmount} € par mois, sous réserve de validation interne et d'accord du client.`,
            scheduleItems: [
              `Montant dû : ${currentCase.amountDue}`,
              `Durée demandée : ${months} mois`,
              `Mensualité indicative : ${monthlyAmount} €`,
              "Statut : validation requise avant proposition",
              "Échéancier non créé",
            ],
            scheduleVersionLabel: "Version 2",
            clientMessage:
              "Une solution d'échelonnement peut être étudiée avec vous, sous réserve de validation et d'accord sur les modalités.",
            complianceChecks: [
              "Aucun échéancier créé dans ce tour.",
              "Durée à valider avant proposition au client.",
              "Accord du client requis avant mise en place.",
              "Validation interne requise avant création.",
            ],
            nextActions: [
              "Ajuster la durée",
              "Comparer avec 3 / 6 / 12 mois",
              "Préparer le message client",
              "Soumettre à validation",
            ],
          }
        : {
            context: contextItems,
            paymentPlan:
              "Options indicatives pour répartir les 840,00 € sur plusieurs mensualités, sous réserve d'accord client et de validation interne.",
            scheduleItems: [
              "3 mensualités de 280,00 €",
              "4 mensualités de 210,00 €",
              "6 mensualités de 140,00 €",
              "Statut : indicatif",
              "Validation requise avant création",
              "Échéancier non créé",
            ],
            scheduleVersionLabel: "Version 2",
            clientMessage:
              "Message à préparer après accord : présenter les options de mensualités à M. D. et préciser que la mise en place reste soumise à validation interne. Aucun échéancier n'a été créé.",
            complianceChecks: [
              "Aucun échéancier créé dans ce tour.",
              "Accord du client requis avant mise en place.",
              "Validation interne requise avant création.",
            ],
            nextActions: [
              "Ajuster la durée",
              "Comparer avec 3 / 6 / 12 mois",
              "Préparer le message client",
              "Soumettre à validation",
            ],
          },
      suggestedActions: [
        "Ajuster la durée",
        "Comparer avec 3 / 6 / 12 mois",
        "Préparer le message client",
        "Soumettre à validation",
      ],
    };
  }

  if (isPaymentOptionsRequest(message)) {
    return {
      intent: "explain_payment_options",
      confidence: 0.92,
      extractedSlots: {
        ...baseSlots,
        paymentQuestion: true,
        scheduleCreated: false,
      },
      targetTask: "explain_payment_options",
      visibleReply: `Pour ${currentCase.reference}, ${currentCase.client} peut régulariser le montant dû selon les options autorisées : paiement du solde, proposition d'échéancier ou échange avec un conseiller. Pour ce dossier, l'option à préparer est une proposition d'échéancier, sous réserve de validation et d'accord du client.`,
      cardUpdates: {
        context: contextItems,
        paymentOptions: [
          `Paiement du solde dû : ${currentCase.amountDue}`,
          "Proposition d'échéancier à valider",
          "Échange avec un conseiller pour confirmer la solution adaptée",
        ],
        paymentRecommendation:
          "Pour RC-2048, l'option à préparer est une proposition d'échéancier, sous réserve de validation interne et d'accord de M. D.",
        validationItems: [
          "Aucun échéancier créé dans ce tour.",
          "Validation interne requise avant proposition.",
          "Accord du client requis avant mise en place.",
        ],
        nextActions: [
          "Proposer un échéancier",
          "Comparer plusieurs durées",
          "Préparer le message client",
          "Soumettre à validation",
        ],
      },
      suggestedActions: [
        "Proposer un échéancier",
        "Comparer plusieurs durées",
        "Préparer le message client",
        "Soumettre à validation",
      ],
    };
  }

  if (normalized.includes("prioritaire") || normalized.includes("priorite")) {
    return {
      intent: "explain_priority",
      confidence: 0.86,
      extractedSlots: baseSlots,
      targetTask: "explain_priority",
      visibleReply:
        "RC-2048 est prioritaire en raison du retard de 32 jours, de la promesse de paiement non tenue et du contact autorisé aujourd'hui.",
      cardUpdates: {},
      suggestedActions: [
        "Préparer l'étape suivante",
        "Rédiger une relance",
        "Proposer un échéancier",
      ],
    };
  }

  if (normalized.includes("resume") || normalized.includes("resumer")) {
    return {
      intent: "summarize_case",
      confidence: 0.86,
      extractedSlots: baseSlots,
      targetTask: "summary",
      visibleReply:
        "Résumé mis à jour : RC-2048 reste prioritaire à cause du retard de 32 jours et de la promesse non tenue.",
      cardUpdates: {},
      suggestedActions: [
        "Rédiger une relance",
        "Proposer un échéancier",
        "Vérifier une règle de contact",
      ],
    };
  }

  if (
    normalized.includes("validation") ||
    normalized.includes("valider") ||
    normalized.includes("soumettre")
  ) {
    return {
      intent: "ask_for_validation",
      confidence: 0.78,
      extractedSlots: baseSlots,
      targetTask: currentTask,
      visibleReply:
        "Je peux préparer la soumission à validation, sans exécuter l'action. Les validations nécessaires restent à confirmer avant toute création ou envoi.",
      cardUpdates: {},
      suggestedActions: [
        "Soumettre à validation",
        "Insérer dans le dossier",
        "Préparer le message client",
      ],
    };
  }

  if (
    normalized.includes("modifier") ||
    normalized.includes("ajuste") ||
    normalized.includes("passe a") ||
    normalized.includes("empathique") ||
    normalized.includes("souple")
  ) {
    return {
      intent: "adjust_existing_proposal",
      confidence: 0.76,
      extractedSlots: baseSlots,
      targetTask: currentTask,
      visibleReply:
        "Je mets à jour la carte concernée en conservant le contexte stable de RC-2048.",
      cardUpdates: {},
      suggestedActions: ["Modifier", "Comparer les versions", "Soumettre à validation"],
    };
  }

  return {
    intent: "small_clarification",
    confidence: 0.45,
    extractedSlots: baseSlots,
    targetTask: currentTask,
    visibleReply: "Je garde le contexte RC-2048 et précise la carte active.",
    cardUpdates: {},
    suggestedActions: [],
  };
}

export function routeUserIntent(message: string, state: TreatmentAssistantState): RoutedUserTurn {
  return routeUserTurn(message, state.currentCase, state.currentTask, {
    content: state.content,
    thread: state.thread,
    currentArtifact: state.currentArtifact,
  });
}

function createArtifactTransition(
  state: TreatmentAssistantState,
  type: AssistantArtifactType,
  content: GeneratedAssistantContent,
  visibleReply: string,
  action?: AssistantAction,
  routedTurn?: RoutedUserTurn,
): AssistantStateTransition {
  const artifact = createAssistantArtifact(type, content, state, state.currentArtifact?.id);
  return {
    state: updateAssistantStateWithArtifact(state, artifact),
    visibleReply,
    artifact,
    action,
    routedTurn,
  };
}

export function handleUserMessage(
  message: string,
  state: TreatmentAssistantState,
): AssistantStateTransition {
  const routedTurn = routeUserIntent(message, state);
  const baseContent =
    routedTurn.targetTask === state.currentTask ? state.content : fallbackAssistantContent;
  const nextContent = applyAssistantCardUpdates(baseContent, routedTurn.cardUpdates);
  return createArtifactTransition(
    state,
    artifactTypeForRoute(routedTurn),
    nextContent,
    routedTurn.visibleReply,
    undefined,
    routedTurn,
  );
}

function scheduleMessageContentFromState(
  state: TreatmentAssistantState,
): GeneratedAssistantContent {
  return applyAssistantCardUpdates(fallbackAssistantContent, {
    context: contextItems,
    scheduleItems: [
      "3 mensualités de 280,00 €",
      `Total : ${state.currentCase.amountDue}`,
      "Statut : proposition indicative",
      "Validation requise avant création",
      "Aucun échéancier créé",
    ],
    clientMessage: [
      `Bonjour ${state.currentCase.client},`,
      "",
      `Nous souhaitons faire le point avec vous concernant le montant restant dû de ${state.currentCase.amountDue}.`,
      "",
      "Une solution d'échelonnement peut être étudiée avec vous, par exemple en plusieurs mensualités, sous réserve de validation et d'accord sur les modalités.",
      "",
      "Nous vous invitons à nous recontacter afin d'échanger sur une solution adaptée à votre situation.",
      "",
      "Cordialement,",
      "Crédit Aurore",
    ].join("\n"),
    complianceChecks: [
      "Ton clair et factuel",
      "Pas de pression injustifiée",
      "Aucun échéancier créé",
      "Validation requise avant mise en place",
      "Accord du client nécessaire",
    ],
    nextActions: [
      "Modifier le message",
      "Copier le message",
      "Insérer dans le dossier",
      "Soumettre à validation",
      "Changer l'option d'échéancier",
    ],
    rawResponse: "Message client préparé pour RC-2048.",
  });
}

function scheduleOptionsContentFromState(
  state: TreatmentAssistantState,
): GeneratedAssistantContent {
  return applyAssistantCardUpdates(fallbackAssistantContent, {
    context: contextItems,
    paymentPlan:
      "Options indicatives pour répartir les 840,00 € sur plusieurs mensualités, sous réserve d'accord client et de validation interne.",
    scheduleItems: [
      "3 mensualités de 280,00 €",
      "4 mensualités de 210,00 €",
      "6 mensualités de 140,00 €",
      "Statut : indicatif",
      "Validation requise avant création",
      "Échéancier non créé",
    ],
    scheduleVersionLabel: state.currentArtifact?.type === "schedule_proposal_v2" ? "Version 2" : "",
    clientMessage:
      "Une solution d'échelonnement peut être étudiée avec M. D., sous réserve de validation et d'accord sur les modalités.",
    complianceChecks: [
      "Aucun échéancier créé dans ce tour.",
      "Accord du client requis avant mise en place.",
      "Validation interne requise avant création.",
    ],
    nextActions: [
      "Ajuster la durée",
      "Comparer avec 3 / 6 / 12 mois",
      "Préparer le message client",
      "Soumettre à validation",
    ],
  });
}

function contactRuleContentFromState(state: TreatmentAssistantState): GeneratedAssistantContent {
  return applyAssistantCardUpdates(fallbackAssistantContent, {
    context: contextItems,
    contactFrame: [
      `Dossier : ${state.currentCase.reference}`,
      `Client : ${state.currentCase.client}`,
      "Contact autorisé aujourd'hui",
      `Plage : ${state.currentCase.contactWindow}`,
      `Canal conseillé : ${state.currentCase.contactChannel}`,
      `Alternative : ${state.currentCase.alternativeChannel}`,
    ],
    allowedItems: [
      `Vous pouvez contacter ${state.currentCase.client} aujourd'hui entre ${state.currentCase.contactWindowText}. Le canal recommandé est l'${state.currentCase.contactChannel}.`,
    ],
    validationItems: [
      "Aucune validation supplémentaire n'est nécessaire pour ce contact aujourd'hui.",
    ],
    nextActions: [
      "Préparer un script d'appel",
      "Rédiger un email de confirmation",
      "Reporter le contact",
      "Voir la règle de contact",
    ],
  });
}

function summaryContentFromState(_state: TreatmentAssistantState): GeneratedAssistantContent {
  return applyAssistantCardUpdates(fallbackAssistantContent, {
    context: contextItems,
    summary: [
      "Montant dû : 840,00 €",
      "Retard : 32 jours",
      "Promesse de paiement non tenue le 12 juin",
      "Contact autorisé aujourd'hui de 8h à 20h",
    ],
    priorityReasons: [
      "Retard significatif sur le dossier RC-2048",
      "Promesse de paiement non tenue",
      "Échéancier envisageable sous validation",
    ],
    nextActions: ["Rédiger une relance", "Proposer un échéancier", "Vérifier une règle de contact"],
  });
}

function reminderDraftContentFromState(_state: TreatmentAssistantState): GeneratedAssistantContent {
  return applyAssistantCardUpdates(fallbackAssistantContent, {
    context: contextItems,
    versions: [
      {
        id: "v1",
        label: "V1",
        title: "Version courte et factuelle",
        body: "Bonjour M. D.,\n\nNous souhaitons faire le point avec vous concernant le dossier RC-2048 et le montant restant dû de 840,00 €. Nous vous invitons à nous recontacter afin d'échanger sur une solution adaptée à votre situation.\n\nCordialement,\nCrédit Aurore",
      },
    ],
    complianceChecks: [
      "Ton clair et factuel",
      "Pas de pression injustifiée",
      "Aucun envoi effectué",
      "Validation requise avant insertion ou envoi",
    ],
    nextActions: [
      "Modifier le message",
      "Copier le message",
      "Insérer dans le dossier",
      "Soumettre à validation",
    ],
  });
}

export function handleAssistantAction(
  action: AssistantAction,
  state: TreatmentAssistantState,
): AssistantStateTransition {
  if (action === "PREPARE_CLIENT_MESSAGE_FROM_SCHEDULE") {
    return createArtifactTransition(
      state,
      "client_message_artifact",
      scheduleMessageContentFromState(state),
      "Message client préparé pour RC-2048. Il reste indicatif et doit être validé avant toute création d'échéancier.",
      action,
    );
  }
  if (action === "COMPARE_SCHEDULE_OPTIONS" || action === "ADJUST_SCHEDULE_DURATION") {
    return createArtifactTransition(
      state,
      "schedule_proposal_v2",
      scheduleOptionsContentFromState(state),
      action === "COMPARE_SCHEDULE_OPTIONS"
        ? "Options comparées pour RC-2048 : 3, 4 ou 6 mensualités restent indicatives et à valider."
        : "Options d'échéancier ajustées pour RC-2048. Aucun échéancier n'a été créé.",
      action,
    );
  }
  if (action === "CHECK_CONTACT_RULE") {
    return createArtifactTransition(
      state,
      "contact_rule_v1",
      contactRuleContentFromState(state),
      "Vous pouvez contacter M. D. aujourd'hui entre 8h et 20h. Le canal conseillé est l'appel sortant.",
      action,
    );
  }
  if (action === "PROPOSE_SCHEDULE") {
    return createArtifactTransition(
      state,
      "schedule_proposal",
      scheduleOptionsContentFromState(state),
      "Proposition d'échéancier préparée pour RC-2048. Elle reste indicative et non créée.",
      action,
    );
  }
  if (action === "SUMMARIZE_CASE") {
    return createArtifactTransition(
      state,
      "case_summary_v1",
      summaryContentFromState(state),
      "Résumé du dossier RC-2048 mis à jour.",
      action,
    );
  }
  if (action === "DRAFT_REMINDER") {
    return createArtifactTransition(
      state,
      "reminder_draft_v1",
      reminderDraftContentFromState(state),
      "Brouillon de relance préparé pour RC-2048. Aucun message n'a été envoyé.",
      action,
    );
  }
  if (action === "INSERT_ARTIFACT_IN_CASE") {
    return updateCurrentArtifactStatus(state, "inserted", "Message inséré dans RC-2048.", action);
  }
  if (action === "SUBMIT_FOR_VALIDATION") {
    return updateCurrentArtifactStatus(
      state,
      "pending_validation",
      "Soumission à validation préparée pour RC-2048. Aucun envoi automatique n'a été effectué.",
      action,
    );
  }

  const actionReplies: Record<AssistantAction, string> = {
    PREPARE_CLIENT_MESSAGE_FROM_SCHEDULE: "",
    COMPARE_SCHEDULE_OPTIONS: "",
    ADJUST_SCHEDULE_DURATION: "",
    SUBMIT_FOR_VALIDATION: "",
    INSERT_ARTIFACT_IN_CASE: "",
    COPY_ARTIFACT_TEXT: "Texte de l'artefact prêt à être copié.",
    PREPARE_CALL_SCRIPT: "Script d'appel préparé à partir du cadre de contact autorisé.",
    REPORT_CONTACT: "Report du contact préparé sur une plage autorisée.",
    CHECK_CONTACT_RULE: "",
    DRAFT_REMINDER: "",
    PROPOSE_SCHEDULE: "",
    SUMMARIZE_CASE: "",
  };

  const currentArtifact =
    state.currentArtifact ??
    createAssistantArtifact(statefulFallbackArtifactType(state.currentTask), state.content, state);
  return {
    state,
    visibleReply: actionReplies[action],
    artifact: currentArtifact,
    action,
  };
}

function AssistantContextPanel({
  compact = false,
  items,
}: {
  compact?: boolean;
  items?: string[];
}) {
  const displayItems =
    items && items.length > 0
      ? items
      : compact
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
        {displayItems.map((item) => (
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

function AssistantDraftPanel({
  compact = false,
  content,
  title = "Réponse au client",
  selectedVersionId,
  status,
  onSelectVersion,
}: {
  compact?: boolean;
  content: GeneratedAssistantContent;
  title?: string;
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
          {title}
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
        {status === "loading" && content.versions.length === 0 ? (
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
                <Info className="ml-auto h-3.5 w-3.5 shrink-0 text-[#071044]/55" />
              </li>
            ))}
      </ul>
    </section>
  );
}

function AssistantActionPanel({
  actions,
  disabled = false,
  onAction,
}: {
  actions: string[];
  disabled?: boolean;
  onAction: (action: string) => void;
}) {
  return (
    <section className="rounded-[6px] border border-[#dfe2ec] bg-white p-4">
      <h3 className="mb-3 !font-sans !text-[#071044] font-bold text-sm">Actions proposées</h3>
      <div className="flex flex-wrap gap-2">
        {actions.map((item) => (
          <button
            key={item}
            type="button"
            disabled={disabled}
            onClick={() => onAction(item)}
            className="inline-flex min-h-8 items-center rounded-[5px] border border-[#dfe2ec] bg-white px-3 font-semibold text-[#071044] text-xs transition hover:border-[#b7aaff] hover:bg-[#f7f5ff] disabled:cursor-not-allowed disabled:bg-[#f6f7fb] disabled:text-[#071044]/45"
          >
            {item}
          </button>
        ))}
      </div>
    </section>
  );
}

function assistantFooterActionsForTask(task: AssistantTask, content: GeneratedAssistantContent) {
  if (content.nextActions.includes("Modifier le message")) {
    return [
      { label: "Modifier le message", Icon: PenLine, primary: true },
      { label: "Copier le message", Icon: Copy },
      { label: "Insérer dans le dossier", Icon: Folder },
      { label: "Soumettre à validation", Icon: ShieldCheck },
    ];
  }
  if (task === "propose_schedule") {
    return [
      { label: "Ajuster la durée", Icon: CalendarDays, primary: true },
      { label: "Comparer les options", Icon: Clock3 },
      { label: "Préparer le message", Icon: Mail },
      { label: "Soumettre à validation", Icon: ShieldCheck },
    ];
  }
  if (task === "explain_payment_options") {
    return [
      { label: "Proposer un échéancier", Icon: CalendarDays, primary: true },
      { label: "Comparer les durées", Icon: Clock3 },
      { label: "Préparer le message", Icon: Mail },
      { label: "Soumettre à validation", Icon: ShieldCheck },
    ];
  }
  if (task === "check_rule") {
    if (isOutOfWindowContactContent(content)) {
      return [
        { label: "Planifier un rappel demain", Icon: Clock3, primary: true },
        { label: "Rédiger un email", Icon: Mail },
        { label: "Reporter le contact", Icon: Clock3 },
        { label: "Insérer la note dans le dossier", Icon: Folder },
      ];
    }
    return [
      { label: "Préparer un script d'appel", Icon: Phone, primary: true },
      { label: "Rédiger un email", Icon: Mail },
      { label: "Reporter le contact", Icon: Clock3 },
      { label: "Insérer la note dans le dossier", Icon: Folder },
    ];
  }

  return [
    { label: "Préparer un brouillon", Icon: PenLine, primary: true },
    { label: "Insérer dans le dossier", Icon: Folder },
    { label: "Copier le message", Icon: Copy },
  ];
}

function AssistantFooterActionButton({
  action,
  disabled,
  onAction,
}: {
  action: ReturnType<typeof assistantFooterActionsForTask>[number];
  disabled: boolean;
  onAction: (action: string) => void;
}) {
  const { Icon } = action;

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onAction(action.label)}
      className={cn(
        "inline-flex h-10 items-center justify-center gap-2 rounded-[5px] px-4 font-bold text-xs transition disabled:cursor-not-allowed",
        action.primary
          ? "bg-[linear-gradient(180deg,#e38a00,#cf7300)] text-white shadow-[0_10px_22px_rgba(217,119,0,0.22)] hover:bg-[#c96f00] disabled:bg-none disabled:bg-[#d8dbe6] disabled:text-white"
          : "border border-[#dfe2ec] bg-white text-[#071044] hover:bg-[#f7f8fb] disabled:bg-[#f6f7fb] disabled:text-[#071044]/45",
      )}
    >
      <Icon className="h-4 w-4" />
      {action.label}
    </button>
  );
}

function AssistantProgressLine({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 rounded-[6px] border border-[#e2defd] bg-[#fbfaff] px-4 py-3 text-[#6048ff] text-xs">
      <span className="h-2 w-2 animate-pulse rounded-full bg-[#6048ff]" />
      <span className="font-bold">{label}</span>
    </div>
  );
}

function assistantActionsForTask(task: AssistantTask, content: GeneratedAssistantContent) {
  const genericActions = ["Modifier", "Insérer dans le dossier", "Soumettre à validation"];
  const hasSpecificActions = content.nextActions.some((action) => !genericActions.includes(action));
  const withModelActions = (fallbacks: string[]) => {
    const modelActions = hasSpecificActions || task === "draft_reminder" ? content.nextActions : [];
    return Array.from(new Set([...modelActions, ...fallbacks])).slice(0, 5);
  };
  if (task === "summary") {
    return withModelActions([
      "Rédiger une relance",
      "Proposer un échéancier",
      "Vérifier une règle de contact",
    ]);
  }
  if (task === "propose_schedule") {
    const scheduleFallbacks = [
      "Ajuster la durée",
      "Comparer les options",
      "Préparer le message client",
      "Soumettre à validation",
      "Insérer dans le dossier",
    ];
    return hasSpecificActions ? content.nextActions.slice(0, 5) : scheduleFallbacks;
  }
  if (task === "explain_payment_options") {
    return content.nextActions.length > 0
      ? content.nextActions
      : [
          "Proposer un échéancier",
          "Comparer plusieurs durées",
          "Préparer le message client",
          "Soumettre à validation",
        ];
  }
  if (task === "check_rule") {
    if (isOutOfWindowContactContent(content)) {
      return [
        "Planifier un rappel demain",
        "Rédiger un email de confirmation",
        "Reporter le contact",
        "Voir la règle de contact",
      ];
    }
    return [
      "Préparer un script d'appel",
      "Rédiger un email de confirmation",
      "Reporter le contact",
      "Voir la règle de contact",
    ];
  }
  if (task === "explain_priority") {
    return withModelActions([
      "Préparer l'étape suivante",
      "Rédiger une relance",
      "Proposer un échéancier",
    ]);
  }
  return withModelActions([
    "Modifier",
    "Insérer dans le dossier",
    "Copier",
    "Soumettre à validation",
  ]);
}

function assistantActionsForArtifact(artifact: AssistantArtifact) {
  if (artifact.type === "client_message_artifact") {
    return [
      "Modifier le message",
      "Copier le message",
      "Insérer dans le dossier",
      "Soumettre à validation",
      "Changer l'option d'échéancier",
    ];
  }
  return assistantActionsForTask(artifact.task, artifact.content);
}

function verificationCompleteForTask(task: AssistantTask, content: GeneratedAssistantContent) {
  if (task === "summary") {
    return content.summary.length > 0 || content.proposition.length > 0;
  }
  if (task === "check_rule") {
    return content.allowedItems.length > 0 || content.validationItems.length > 0;
  }
  if (task === "explain_payment_options") {
    return content.paymentOptions.length > 0 || content.paymentRecommendation.length > 0;
  }
  if (task === "explain_priority") {
    return content.recommendedAction.length > 0 || content.priorityReasons.length > 0;
  }
  return content.complianceChecks.length > 0;
}

function isOutOfWindowContactContent(content: GeneratedAssistantContent) {
  return [...content.contactFrame, ...content.validationItems].some((item) =>
    normalizeAssistantText(item).includes("non autorise"),
  );
}

function AssistantTextCard({
  title,
  body,
  badges,
  items,
}: {
  title: string;
  body?: string;
  badges?: string[];
  items?: string[];
}) {
  const paragraphs = (body ?? "")
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);
  const listItems = items?.filter(Boolean) ?? [];

  if (paragraphs.length === 0 && listItems.length === 0) {
    return null;
  }

  return (
    <section className="rounded-[5px] border border-[#dfe2ec] bg-[#fbfbfd] p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h3 className="!font-sans !text-[#071044] font-bold text-sm">{title}</h3>
        {badges?.map((badge) => (
          <span
            key={badge}
            className="rounded-full border border-[#d8d1ff] bg-white px-2 py-0.5 font-bold text-[#6048ff] text-[0.64rem]"
          >
            {badge}
          </span>
        ))}
      </div>
      {listItems.length > 0 ? (
        <ul className="space-y-1.5 text-[#071044] text-xs leading-5">
          {listItems.map((item) => (
            <li key={item} className="flex items-start gap-2">
              <CircleCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#071044]/60" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {paragraphs.length > 0 ? (
        <div className="space-y-2 whitespace-pre-wrap text-[#071044] text-xs leading-5">
          {paragraphs.map((paragraph) => (
            <p key={paragraph}>{paragraph}</p>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function scheduleDurationFromContent(content: GeneratedAssistantContent) {
  const durationItem = content.scheduleItems.find((item) => /durée demandée/i.test(item));
  const durationMatch = durationItem?.match(/(\d{1,2})\s*mois/i);
  return durationMatch?.[1] ? `${durationMatch[1]} mois` : null;
}

function scheduleBadgesForContent(content: GeneratedAssistantContent) {
  const normalizedItems = content.scheduleItems.map(normalizeAssistantText);
  return [
    normalizedItems.some((item) => item.includes("validation requise"))
      ? "Validation requise"
      : null,
    normalizedItems.some((item) => item.includes("non cree")) ? "Non créé" : null,
  ].filter(Boolean) as string[];
}

function draftPanelTitleForContent(content: GeneratedAssistantContent) {
  const draftBody = content.versions[0]?.body ?? "";
  if (
    normalizeAssistantText(draftBody).includes("contactez") ||
    normalizeAssistantText(draftBody).includes("proposez")
  ) {
    return "Plan d'action proposé";
  }
  return "Brouillon de relance";
}

export interface ArtifactRenderState {
  compact?: boolean;
  selectedVersionId: string;
  status: AssistantStatus;
  thinkingLabel: string;
  onActionCommand: (action: string) => void;
  onSelectVersion: (versionId: string) => void;
}

function fallbackArtifactForTask(
  task: AssistantTask,
  content: GeneratedAssistantContent,
): AssistantArtifact {
  const type = statefulFallbackArtifactType(task);
  return {
    id: `current-${type}`,
    type,
    task,
    title: artifactTitleForType(type),
    status: "draft",
    content,
  };
}

export function renderArtifact(artifact: AssistantArtifact, state: ArtifactRenderState) {
  const task = artifact.task;
  const content = artifact.content;
  const compact = state.compact ?? false;
  const selectedVersionId = state.selectedVersionId;
  const status = state.status;
  const thinkingLabel = state.thinkingLabel;
  const onActionCommand = state.onActionCommand;
  const onSelectVersion = state.onSelectVersion;
  const isLoading = status === "loading";
  const context = content.context.length > 0 ? content.context : contextItems;
  const actionsReady = !isLoading && verificationCompleteForTask(task, content);
  const actions = assistantActionsForArtifact(artifact);
  const progress = isLoading ? <AssistantProgressLine label={thinkingLabel} /> : null;

  if (artifact.type === "client_message_artifact") {
    return (
      <div className="grid gap-4">
        <AssistantTextCard
          badges={["Validation requise", "Non créé"]}
          items={content.scheduleItems}
          title="Option retenue"
        />
        <AssistantTextCard body={content.clientMessage} title="Message client proposé" />
        <AssistantVerificationPanel checks={content.complianceChecks} status={status} />
        <AssistantActionPanel
          actions={actions}
          disabled={!actionsReady}
          onAction={onActionCommand}
        />
      </div>
    );
  }

  if (artifact.type === "schedule_proposal" || artifact.type === "schedule_proposal_v2") {
    const duration = scheduleDurationFromContent(content);
    const title = duration ? `Échéancier indicatif — ${duration}` : "Proposition d'échéancier";

    return (
      <div className="grid gap-4">
        <AssistantContextPanel compact={compact} items={context} />
        {progress}
        <AssistantTextCard
          badges={scheduleBadgesForContent(content)}
          body={content.paymentPlan}
          items={content.scheduleItems}
          title={title}
        />
        <AssistantTextCard body={content.clientMessage} title="Message client associé" />
        <AssistantVerificationPanel checks={content.complianceChecks} status={status} />
        <AssistantActionPanel
          actions={actions}
          disabled={!actionsReady}
          onAction={onActionCommand}
        />
      </div>
    );
  }

  if (artifact.type === "payment_options_v1") {
    return (
      <div className="grid gap-4">
        <AssistantTextCard items={content.paymentOptions} title="Options de règlement" />
        <AssistantTextCard
          body={content.paymentRecommendation}
          title="Option recommandée pour RC-2048"
        />
        <AssistantTextCard items={content.validationItems} title="Validations nécessaires" />
        <AssistantActionPanel
          actions={actions}
          disabled={!actionsReady}
          onAction={onActionCommand}
        />
      </div>
    );
  }

  if (artifact.type === "contact_rule_v1") {
    return (
      <div className="grid gap-4">
        <AssistantTextCard items={content.contactFrame} title="Cadre de contact applicable" />
        <AssistantTextCard items={content.allowedItems} title="Ce qui est autorisé" />
        <AssistantTextCard
          items={content.validationItems}
          title={
            isOutOfWindowContactContent(content)
              ? "Ce qui nécessite validation ou action"
              : "Ce qui nécessite validation"
          }
        />
        <AssistantActionPanel
          actions={actions}
          disabled={!actionsReady}
          onAction={onActionCommand}
        />
      </div>
    );
  }

  if (artifact.type === "case_summary_v1") {
    return (
      <div className="grid gap-4">
        <AssistantContextPanel compact={compact} items={context} />
        {progress}
        <AssistantTextCard items={content.summary} title="Résumé du dossier" />
        <AssistantTextCard items={content.priorityReasons} title="Pourquoi prioritaire" />
        <AssistantActionPanel
          actions={actions}
          disabled={!actionsReady}
          onAction={onActionCommand}
        />
      </div>
    );
  }

  if (artifact.type === "priority_explanation_v1") {
    return (
      <div className="grid gap-4">
        <AssistantTextCard items={content.priorityReasons} title="Raisons de priorité" />
        <AssistantTextCard items={content.businessFactors} title="Facteurs métier" />
        <AssistantTextCard body={content.recommendedAction} title="Prochaine action recommandée" />
        <AssistantActionPanel
          actions={actions}
          disabled={!actionsReady}
          onAction={onActionCommand}
        />
      </div>
    );
  }

  return (
    <div className="grid gap-4">
      <AssistantContextPanel compact={compact} items={context} />
      {progress}
      {content.versions.length > 0 ? (
        <AssistantDraftPanel
          compact={compact}
          content={content}
          title={draftPanelTitleForContent(content)}
          selectedVersionId={selectedVersionId}
          status={status}
          onSelectVersion={onSelectVersion}
        />
      ) : null}
      <AssistantVerificationPanel checks={content.complianceChecks} status={status} />
      <AssistantActionPanel actions={actions} disabled={!actionsReady} onAction={onActionCommand} />
    </div>
  );
}

function AssistantTaskContent({
  task,
  artifact,
  compact = false,
  content,
  selectedVersionId,
  status,
  thinkingLabel,
  onActionCommand,
  onSelectVersion,
}: {
  task: AssistantTask;
  artifact: AssistantArtifact | null;
  compact?: boolean;
  content: GeneratedAssistantContent;
  selectedVersionId: string;
  status: AssistantStatus;
  thinkingLabel: string;
  onActionCommand: (action: string) => void;
  onSelectVersion: (versionId: string) => void;
}) {
  return renderArtifact(artifact ?? fallbackArtifactForTask(task, content), {
    compact,
    selectedVersionId,
    status,
    thinkingLabel,
    onActionCommand,
    onSelectVersion,
  });
}

function AssistantDrawer({
  mode,
  activeTask,
  artifact,
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
  onActionCommand,
  onRegenerate,
  onSelectVersion,
  onSendMessage,
  onSelectTab,
  onTogglePinned,
}: {
  mode: Exclude<AssistantMode, "closed">;
  activeTask: AssistantTask;
  artifact: AssistantArtifact | null;
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
  onActionCommand: (action: string) => void;
  onRegenerate: () => void;
  onSelectVersion: (versionId: string) => void;
  onSendMessage: () => void;
  onSelectTab: (tab: string) => void;
  onTogglePinned: () => void;
}) {
  const isPinned = mode === "pinned";
  const isFocus = mode === "focus";
  const finalActionsDisabled =
    status === "loading" || !verificationCompleteForTask(activeTask, content);
  const footerActions = assistantFooterActionsForTask(activeTask, content);
  const reversedMessages = [...messages].reverse();
  const currentPrompt =
    reversedMessages.find((message) => message.role === "user")?.content ??
    assistantPromptForTask(activeTask);
  const latestAssistantReply = reversedMessages.find(
    (message) => message.role === "assistant" && !message.streaming && !message.error,
  )?.content;

  return (
    <aside
      aria-label="Assistant de traitement"
      aria-modal={isPinned ? undefined : true}
      role={isPinned ? "complementary" : "dialog"}
      className={cn(
        "fixed z-50 flex flex-col overflow-hidden border-[#dfe2ec] bg-white text-[#071044] transition-[width,box-shadow,transform] duration-300 ease-out",
        isFocus
          ? "top-[108px] right-8 bottom-6 left-[290px] rounded-[8px] border shadow-[0_28px_80px_rgba(7,16,68,0.22)] max-lg:left-6 max-md:inset-0 max-md:rounded-none"
          : cn(
              "right-0 top-[90px] h-[calc(100vh-90px)] border-l max-md:top-0 max-md:h-screen",
              isPinned
                ? "w-[496px] max-w-[calc(100vw-18px)] shadow-[-12px_0_36px_rgba(7,16,68,0.08)]"
                : "w-[704px] max-w-[calc(100vw-22px)] shadow-[-26px_0_70px_rgba(7,16,68,0.18)]",
            ),
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
              <span className="whitespace-nowrap font-semibold text-[#071044]/80">— RC-2048</span>
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
              aria-label={isFocus ? "Quitter le mode focus" : "Mode focus"}
              onClick={onExpand}
              className={cn(
                "inline-flex items-center justify-center gap-2 rounded-[5px] border border-[#dfe2ec] px-2 text-[#071044] transition hover:bg-[#f7f8fb]",
                isPinned ? "h-7 min-w-7" : "h-8 min-w-8",
              )}
            >
              {isFocus ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
              {!isPinned ? (
                <span className="hidden font-semibold text-xs sm:inline">
                  {isFocus ? "Réduire" : "Mode focus"}
                </span>
              ) : null}
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
                key={tab.task}
                type="button"
                onClick={() => onSelectTab(tab.label)}
                className={cn(
                  "relative h-10 shrink-0 font-bold text-[0.72rem] transition",
                  activeTask === tab.task ? "text-[#6048ff]" : "text-[#071044]",
                )}
              >
                {tab.label}
                <span
                  className={cn(
                    "absolute right-0 bottom-0 left-0 h-0.5 rounded-full bg-[#6048ff] transition-opacity",
                    activeTask === tab.task ? "opacity-100" : "opacity-0",
                  )}
                />
              </button>
            ))}
          </div>
        ) : null}
      </header>

      {isPinned ? (
        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          <AssistantTaskContent
            compact
            task={activeTask}
            artifact={artifact}
            content={content}
            selectedVersionId={selectedVersionId}
            status={status}
            onActionCommand={onActionCommand}
            onSelectVersion={onSelectVersion}
            thinkingLabel={thinkingLabel}
          />
        </div>
      ) : (
        <div className={cn("min-h-0 flex-1 overflow-y-auto px-6 py-5", isFocus && "px-8")}>
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
            <div className="rounded-[5px] bg-[#e9f7e9] px-3 py-2 text-[#145b2b] text-xs">
              <p className="flex items-center gap-2 font-bold">
                <CircleCheck className="h-4 w-4" />
                Contact autorisé
              </p>
              <p className="mt-1">8h - 20h</p>
            </div>
          </section>

          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {assistantActions.map(({ label, Icon }) => {
              const tab = assistantTabForAction(label);
              const task = assistantTaskForAction(label);
              return (
                <button
                  key={label}
                  type="button"
                  onClick={() => onSelectTab(tab)}
                  className={cn(
                    "flex min-h-12 items-center justify-center gap-2 rounded-[5px] border px-3 font-bold text-xs transition",
                    activeTask === task
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
            {currentPrompt}
          </div>

          <article className="mt-5 rounded-[6px] border border-[#dfe2ec] bg-white p-5 shadow-[0_12px_28px_rgba(7,16,68,0.05)]">
            <div className="mb-4 flex items-center gap-3 text-sm">
              <Sparkles
                className={cn("h-5 w-5 text-[#6048ff]", status === "loading" && "animate-pulse")}
              />
              <p className="font-bold leading-5">
                {status === "loading"
                  ? thinkingLabel
                  : (latestAssistantReply ?? assistantResultLabel(activeTask))}
              </p>
              <button
                type="button"
                onClick={onRegenerate}
                className="ml-auto font-semibold text-[#6048ff] text-xs"
              >
                Régénérer
              </button>
            </div>
            {error ? (
              <div className="mb-4 rounded-[5px] border border-[#ffd2c9] bg-[#fff5f3] px-4 py-3 text-[#a23b2a] text-xs">
                {error}
              </div>
            ) : null}
            <AssistantTaskContent
              task={activeTask}
              artifact={artifact}
              content={content}
              selectedVersionId={selectedVersionId}
              status={status}
              thinkingLabel={thinkingLabel}
              onActionCommand={onActionCommand}
              onSelectVersion={onSelectVersion}
            />
          </article>
        </div>
      )}

      <footer className="shrink-0 border-[#dfe2ec] border-t bg-white px-6 py-4">
        {isPinned ? (
          <>
            <div className="mb-4 grid gap-2 sm:grid-cols-2">
              {footerActions.map((action) => (
                <AssistantFooterActionButton
                  key={action.label}
                  action={action}
                  disabled={finalActionsDisabled}
                  onAction={onActionCommand}
                />
              ))}
            </div>
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
          </>
        ) : (
          <>
            <div className="flex flex-wrap gap-3">
              {footerActions.map((action) => (
                <AssistantFooterActionButton
                  key={action.label}
                  action={action}
                  disabled={finalActionsDisabled}
                  onAction={onActionCommand}
                />
              ))}
            </div>
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
                placeholder="Continuer avec l'assistant Recouvrement..."
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
  const [assistantMode, setAssistantMode] = useState<AssistantMode>("closed");
  const [activeAssistantTask, setActiveAssistantTask] =
    useState<AssistantTask>(defaultAssistantTask);
  const [assistantContent, setAssistantContent] =
    useState<GeneratedAssistantContent>(fallbackAssistantContent);
  const [assistantStatus, setAssistantStatus] = useState<AssistantStatus>("idle");
  const [assistantError, setAssistantError] = useState<string | null>(null);
  const [assistantThread, setAssistantThread] = useState<AssistantThreadMessage[]>([]);
  const [assistantInput, setAssistantInput] = useState("");
  const [assistantArtifact, setAssistantArtifact] = useState<AssistantArtifact | null>(null);
  const [assistantArtifacts, setAssistantArtifacts] = useState<AssistantArtifact[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState("v1");
  const [thinkingStep, setThinkingStep] = useState(0);
  const assistantThreadRef = useRef<AssistantThreadMessage[]>([]);
  const activeThinkingSteps = recouvrementThinkingSteps[activeAssistantTask];
  const thinkingLabel =
    activeThinkingSteps[thinkingStep % activeThinkingSteps.length] ?? "Analyse du contexte...";

  useEffect(() => {
    assistantThreadRef.current = assistantThread;
  }, [assistantThread]);

  const currentAssistantState = useCallback(
    (): TreatmentAssistantState => ({
      currentCase: currentRecouvrementCase,
      currentTask: activeAssistantTask,
      currentArtifact: assistantArtifact,
      artifacts: assistantArtifacts,
      content: assistantContent,
      thread: assistantThreadRef.current,
    }),
    [activeAssistantTask, assistantArtifact, assistantArtifacts, assistantContent],
  );

  const applyAssistantTransition = useCallback((transition: AssistantStateTransition) => {
    setActiveAssistantTask(transition.state.currentTask);
    setAssistantContent(transition.state.content);
    setAssistantArtifact(transition.state.currentArtifact);
    setAssistantArtifacts(transition.state.artifacts);
    setAssistantStatus("ready");
    setAssistantError(null);
    setSelectedVersionId(transition.artifact.content.versions[0]?.id ?? "v1");
  }, []);

  const appendHandledTurn = useCallback((userContent: string, assistantContent: string) => {
    const priorThread = assistantThreadRef.current.filter((item) => !item.streaming);
    setAssistantThread([
      ...priorThread,
      { id: crypto.randomUUID(), role: "user", content: userContent },
      { id: crypto.randomUUID(), role: "assistant", content: assistantContent },
    ]);
  }, []);

  const closeAssistant = () => {
    setAssistantMode("closed");
  };
  const expandAssistant = () =>
    setAssistantMode((currentMode) => (currentMode === "focus" ? "drawer" : "focus"));
  const togglePinnedAssistant = () =>
    setAssistantMode((currentMode) => (currentMode === "pinned" ? "drawer" : "pinned"));
  const regenerateAssistantContent = useCallback(() => {
    const state = currentAssistantState();
    const action = assistantActionFromLabel(assistantTabForTask(activeAssistantTask), state);
    const transition = handleAssistantAction(action, state);
    applyAssistantTransition(transition);
    appendHandledTurn("Régénérer", transition.visibleReply);
  }, [activeAssistantTask, appendHandledTurn, applyAssistantTransition, currentAssistantState]);

  const openAssistant = useCallback(
    (action = "Préparer une relance") => {
      const state = currentAssistantState();
      const transition = handleAssistantAction(assistantActionFromLabel(action, state), state);
      applyAssistantTransition(transition);
      appendHandledTurn(action, transition.visibleReply);
      if (assistantMode === "closed") setAssistantMode("drawer");
    },
    [appendHandledTurn, applyAssistantTransition, assistantMode, currentAssistantState],
  );

  const selectAssistantTab = useCallback(
    (tab: string) => {
      const state = currentAssistantState();
      const transition = handleAssistantAction(assistantActionFromLabel(tab, state), state);
      applyAssistantTransition(transition);
      appendHandledTurn(tab, transition.visibleReply);
    },
    [appendHandledTurn, applyAssistantTransition, currentAssistantState],
  );

  const sendAssistantActionCommand = useCallback(
    (action: string) => {
      const state = currentAssistantState();
      const transition = handleAssistantAction(assistantActionFromLabel(action, state), state);
      applyAssistantTransition(transition);
      appendHandledTurn(action, transition.visibleReply);
    },
    [appendHandledTurn, applyAssistantTransition, currentAssistantState],
  );

  const sendAssistantFollowUp = useCallback(() => {
    const trimmedInput = assistantInput.trim();
    if (!trimmedInput) return;
    const transition = handleUserMessage(trimmedInput, currentAssistantState());
    setAssistantInput("");
    applyAssistantTransition(transition);
    appendHandledTurn(trimmedInput, transition.visibleReply);
  }, [appendHandledTurn, applyAssistantTransition, assistantInput, currentAssistantState]);

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

  return (
    <div className="min-h-screen bg-[#c9ccd1] font-sans text-[#050816]">
      <div className="mx-auto min-h-screen max-w-[1718px] bg-white">
        <div className="flex min-h-screen flex-col">
          <header className="flex min-h-[90px] shrink-0 flex-wrap items-center gap-5 border-[#d0d0d0] border-b bg-white px-4 py-3 sm:px-6 lg:flex-nowrap lg:px-[23px]">
            <CreditAuroreLogo className="min-w-[250px] gap-[9px]" gradientIdPrefix="caRecLogo" />
            <label className="relative order-last block w-full max-w-[430px] md:order-none lg:ml-auto">
              <Search className="-translate-y-1/2 absolute top-1/2 left-4 h-5 w-5 text-[#050816]" />
              <input
                aria-label="Rechercher"
                placeholder="Rechercher un dossier, un client, ..."
                className="h-11 w-full rounded-[4px] border border-[#d7d9e1] bg-white pr-4 pl-12 text-[#050816] text-sm outline-none transition placeholder:text-[#5d6275] focus:border-[#b99245] focus:ring-2 focus:ring-[#b99245]/20"
              />
            </label>
            <div className="flex items-center gap-4 sm:gap-6">
              <button
                type="button"
                className="hidden flex-col items-center gap-1 text-[10.5px] sm:flex"
              >
                <CircleHelp className="h-[22px] w-[22px]" />
                Aide
              </button>
              <button
                type="button"
                className="relative flex flex-col items-center gap-1 text-[10.5px]"
              >
                <Bell className="h-[22px] w-[22px]" />
                <span className="-top-1 absolute right-1 grid h-4 min-w-4 place-items-center rounded-full bg-[#b99245] px-1 text-[#050816] text-[9px]">
                  3
                </span>
                Notifications
              </button>
              <button type="button" className="flex items-center gap-3">
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
                              onClick={() => openAssistant("Proposer un échéancier")}
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
                              Assistant de traitement — RC-2048
                              <span className="rounded-full border border-[#c8bbff] bg-white px-2.5 py-1 font-bold text-[#6048ff] text-[0.68rem]">
                                Contextualisé
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
                              onClick={() => openAssistant(label)}
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
      {assistantMode === "drawer" || assistantMode === "focus" ? (
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
          activeTask={activeAssistantTask}
          artifact={assistantArtifact}
          content={assistantContent}
          error={assistantError}
          inputValue={assistantInput}
          messages={assistantThread}
          selectedVersionId={selectedVersionId}
          status={assistantStatus}
          thinkingLabel={thinkingLabel}
          onClose={closeAssistant}
          onExpand={expandAssistant}
          onInputChange={setAssistantInput}
          onActionCommand={sendAssistantActionCommand}
          onRegenerate={regenerateAssistantContent}
          onSelectVersion={setSelectedVersionId}
          onSendMessage={sendAssistantFollowUp}
          onSelectTab={selectAssistantTab}
          onTogglePinned={togglePinnedAssistant}
        />
      ) : null}
    </div>
  );
}
