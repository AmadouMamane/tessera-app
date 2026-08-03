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
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useRef, useState } from "react";

import { CreditAuroreLogo } from "@/components/brand/credit-aurore-logo";
import { SyntheticNotice } from "@/components/cockpit/synthetic-notice";
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
import {
  type RecouvrementProductCopy,
  recouvrementProductCopy,
} from "@/components/recouvrement/recouvrement-product-copy";
import type { Locale } from "@/i18n/routing";
import {
  type RecouvrementAssistantArtifact,
  type RecouvrementAssistantResponse,
  sendRecouvrementAssistantAction,
  sendRecouvrementAssistantMessage,
} from "@/lib/api/recouvrement-assistant";
import { useQuery } from "@tanstack/react-query";

import { fetchRecouvrementQueue } from "@/lib/api/client";
import { streamChat } from "@/lib/api/sse";
import { cn } from "@/lib/cn";
import { type ArtifactStatusTone, artifactStatusMeta } from "@/lib/recouvrement/artifact-status";

// The counters derive from the REAL queue store (lot 9) — never invented.
const navigation = [
  { Icon: Home, active: true },
  { Icon: Folder },
  { Icon: Send, counterKey: "relance_a_valider" as const },
  { Icon: CalendarDays, counterKey: "echeancier_a_confirmer" as const },
  { Icon: ShieldCheck, counterKey: "situation_a_verifier" as const },
  { Icon: Clock3 },
];

const assistantActions = [
  { tab: "Résumer", Icon: FileText },
  { tab: "Préparer une relance", Icon: PenLine },
  { tab: "Vérifier une règle", Icon: ShieldCheck },
  { tab: "Proposer un échéancier", Icon: CalendarDays },
  { tab: "Options de paiement", Icon: CircleHelp },
];

const nextItems = [
  {
    counterKey: "relance_a_valider" as const,
    Icon: Send,
    accent: "orange",
  },
  {
    counterKey: "echeancier_a_confirmer" as const,
    Icon: CalendarDays,
    accent: "violet",
  },
  {
    counterKey: "situation_a_verifier" as const,
    Icon: ShieldCheck,
    accent: "violet",
  },
];

const quickActions = [FileText, CalendarDays, FileText, Users, Clock3];

const cardClass = "rounded-md border border-[#dcdee6] bg-white shadow-[0_2px_8px_rgba(0,0,0,0.06)]";

const defaultAssistantTab = "Préparer une relance";

const assistantTabs = [
  defaultAssistantTab,
  "Proposer un échéancier",
  "Options de paiement",
  "Vérifier une règle",
  "Résumer",
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

function pendingContentForTask(
  task: RecouvrementDrawerTask,
  copy: RecouvrementProductCopy,
): GeneratedAssistantContent {
  if (task === "check_contact_rule") {
    return {
      ...pendingContactRuleContent,
      artifact: pendingContactRuleContent.artifact
        ? {
            ...pendingContactRuleContent.artifact,
            title: `${copy.ui.contactFrameworkShort} — RC-2048`,
          }
        : null,
    };
  }
  if (task === "explain_payment_options") {
    return {
      ...fallbackAssistantContent,
      artifact: {
        id: "RC-2048-payment-options-pending",
        type: "payment_options_v1",
        task: "explain_payment_options",
        title: `${copy.ui.paymentOptions} — RC-2048`,
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
        title: `${copy.ui.proposedSchedule} — RC-2048`,
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
        title: `${copy.tabs[4]} — RC-2048`,
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
      title: `${copy.tabs[0]} — RC-2048`,
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

const MIN_ASSISTANT_THINKING_MS = 1800;

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
  const t = useTranslations("artifactStatus");
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
      {t(meta.messageKey)}
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

function assistantPromptForTab(activeTab: string, copy: RecouvrementProductCopy) {
  const index = assistantActions.findIndex((item) => item.tab === activeTab);
  return copy.actions[index]?.[2] ?? copy.defaultPrompt;
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
    "case summary",
    "summary",
    "customer reply",
    "rules and compliance",
    "compliance",
    "suggested next actions",
    "next actions",
    "payment plan",
    "vorgangszusammenfassung",
    "zusammenfassung",
    "kundenantwort",
    "regeln und konformitat",
    "konformitat",
    "vorgeschlagene nachste aktionen",
    "nachste aktionen",
    "ratenplan",
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
      /^(?:(?:Réponse au client|Customer reply|Kundenantwort)\s*[-–—:]?\s*)?(?:Version\s*)?V?\s*([123])\b\s*[-–—:]?\s*(.*)$/i,
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

function parseGeneratedAssistantContent(
  raw: string,
  copy: RecouvrementProductCopy,
): GeneratedAssistantContent {
  const text = asString(raw);
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const responseBlock = extractSectionBlock(lines, [
    "reponse au client",
    "customer reply",
    "kundenantwort",
  ]);
  const versions = extractDraftVersions(lines);
  const fallbackVersion =
    responseBlock && versions.length === 0
      ? [
          {
            id: "v1",
            label: "V1",
            title: copy.ui.versionProposed,
            body: responseBlock,
          },
        ]
      : [];

  return {
    summary: blockToItems(
      extractSectionBlock(lines, [
        "resume du dossier",
        "resume",
        "case summary",
        "summary",
        "vorgangszusammenfassung",
        "zusammenfassung",
      ]),
    ),
    versions: versions.length > 0 ? versions : fallbackVersion,
    paymentPlan: extractSectionBlock(lines, [
      "echeancier",
      "plan de paiement",
      "payment plan",
      "ratenplan",
    ]),
    complianceChecks: blockToItems(
      extractSectionBlock(lines, [
        "regles et conformite",
        "conformite",
        "rules and compliance",
        "compliance",
        "regeln und konformitat",
        "konformitat",
      ]),
      6,
    ),
    nextActions: blockToItems(
      extractSectionBlock(lines, [
        "prochaines actions suggerees",
        "prochaines actions",
        "suggested next actions",
        "next actions",
        "vorgeschlagene nachste aktionen",
        "nachste aktionen",
      ]),
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
  locale: Locale,
): GeneratedAssistantContent {
  const cards = contactRuleCards(response, locale);
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
  copy: RecouvrementProductCopy,
): GeneratedAssistantContent {
  return {
    summary: proposal.cardUpdates.summary ?? proposal.cardUpdates.context ?? [],
    versions: [
      {
        id: "v1",
        label: "V1",
        title: copy.ui.prudentMessage,
        body: [
          copy.ui.scheduleGreeting,
          copy.ui.scheduleOffer,
          copy.ui.scheduleInvite,
          copy.ui.scheduleSignoff,
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
  copy: RecouvrementProductCopy,
): GeneratedAssistantContent {
  const updates = response.cardUpdates ?? {};
  const clientMessage =
    (updates.clientMessage ?? []).join("\n\n") ||
    [
      copy.ui.scheduleGreeting,
      copy.ui.scheduleOffer,
      copy.ui.scheduleInvite,
      copy.ui.scheduleSignoff,
    ].join("\n\n");

  return {
    summary: updates.summary ?? updates.context ?? [],
    versions: [
      {
        id: "v1",
        label: "V1",
        title: updates.scheduleVersionLabel?.[0] ?? copy.ui.prudentMessage,
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
  copy: RecouvrementProductCopy,
): GeneratedAssistantContent {
  const updates = response.cardUpdates ?? {};
  const clientMessage = (updates.clientMessage ?? []).join("\n\n");
  return {
    summary: updates.summary ?? updates.context ?? [],
    versions: [
      {
        id: "v1",
        label: "V1",
        title: updates.draftVersionLabel?.[0] ?? copy.ui.customerMessage,
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

function buildAssistantHistory(thread: AssistantThreadMessage[], copy: RecouvrementProductCopy) {
  const stableMessages = thread.filter((message) => message.content.trim() && !message.streaming);
  return [
    { role: "user" as const, content: copy.dossierContext },
    ...stableMessages.map((message) => ({
      role: message.role,
      content: message.content,
    })),
  ];
}

function AssistantContextPanel({ compact = false }: { compact?: boolean }) {
  const copy = recouvrementProductCopy(useLocale() as Locale);
  const items = compact ? copy.contextCompact : copy.context;

  return (
    <section className={cn("rounded-md border border-[#dfe2ec] bg-white", compact ? "p-4" : "p-5")}>
      <div className="mb-3 flex items-center justify-between gap-4">
        <h3 className="!font-sans !text-[#071044] font-bold text-sm">{copy.ui.retainedContext}</h3>
        <button
          type="button"
          className="inline-flex items-center gap-2 font-semibold text-[#6048ff] text-xs"
        >
          <PenLine className="h-4 w-4" />
          {copy.ui.editContext}
        </button>
      </div>
      <div className={cn("grid gap-2 text-[#071044] text-xs", compact ? "" : "sm:grid-cols-2")}>
        {items.map((item) => (
          <div
            key={item}
            className={cn(
              "flex items-center gap-2 rounded-sm bg-[#fbfbfd] px-3",
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
  const locale = useLocale() as Locale;
  const copy = recouvrementProductCopy(locale);
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-md border border-[#d8d1ff] bg-[#f5f2ff] text-[#071044] shadow-[0_10px_22px_rgba(96,72,255,0.1)]",
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
          <p className="font-extrabold text-sm">{copy.ui.thinking}</p>
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
  const copy = recouvrementProductCopy(useLocale() as Locale);
  const paragraphClassName = compact ? "mt-3" : "mt-4";
  const selectedVersion =
    content.versions.find((version) => version.id === selectedVersionId) ?? content.versions[0];
  const draftParagraphs = (selectedVersion?.body ?? "")
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);

  return (
    <section className="rounded-md border border-[#dfe2ec] bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="!font-sans !text-[#071044] font-bold text-sm">
          {copy.ui.customerReply}
          {selectedVersion ? (
            <span className="ml-2 font-semibold text-[#071044]/62 text-xs">
              {selectedVersion.title}
            </span>
          ) : null}
        </h3>
        <div className="flex shrink-0 items-center gap-1 rounded-sm border border-[#dfe2ec] bg-[#fbfbfd] p-1">
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
                "h-7 min-w-9 rounded-sm px-2 font-bold text-[0.68rem] transition",
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
          "rounded-sm border border-[#dfe2ec] bg-white text-[#071044]",
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
          <p className="text-[#071044]/60">{copy.ui.noDraft}</p>
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
  const copy = recouvrementProductCopy(useLocale() as Locale);
  return (
    <section className="rounded-md border border-[#dfe2ec] bg-white p-4">
      <h3 className="mb-3 !font-sans !text-[#071044] font-bold text-sm">{copy.ui.rules}</h3>
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
  const copy = recouvrementProductCopy(useLocale() as Locale);
  const cards = content.artifactCards;
  const decision = content.artifact?.content.decision;
  const reasonCodes = artifactStringList(content.artifact, "reason_codes");
  const isBlocked = decision === "blocked";
  const contactFrame = cards.contactFrame ?? content.summary;
  const allowedItems = cards.allowedItems ?? [];
  const validationItems = cards.validationItems ?? content.complianceChecks;
  const displayedContactFrame =
    isBlocked && !contactFrame.includes(copy.ui.noCall)
      ? [...contactFrame, copy.ui.noCall]
      : contactFrame;
  const sectionClassName = "rounded-sm border border-[#dfe2ec] bg-[#fbfbfd] p-4";
  const rows = compact ? loadingRows.slice(0, 2) : loadingRows;

  return (
    <>
      <section className={sectionClassName}>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <h3 className="!font-sans !text-[#071044] font-bold text-sm">
            {copy.ui.contactFramework}
          </h3>
          {isBlocked ? (
            <>
              <span className="rounded-full bg-[#ffe8e5] px-2 py-0.5 font-bold text-[#c0362c] text-[0.64rem]">
                {copy.ui.blocked}
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
        <h3 className="mb-2 !font-sans !text-[#071044] font-bold text-sm">{copy.ui.allowed}</h3>
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
          {copy.ui.requiresApproval}
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
  if (/rappel|duree|reminder|duration|callback|ruckruf|laufzeit/.test(normalized))
    return CalendarDays;
  if (/email|message|nachricht/.test(normalized)) return Mail;
  if (/reporter|reschedule|postpone|verschieben/.test(normalized)) return Clock3;
  if (/script|appel|call|anruf/.test(normalized)) return Phone;
  if (/inserer|insert|einfugen|note|notiz/.test(normalized)) return Folder;
  if (/copier|copy|kopieren/.test(normalized)) return Copy;
  if (/validation|soumettre|submit|approval|freigabe|einreichen/.test(normalized)) return Send;
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
              "inline-flex h-10 items-center justify-center gap-2 rounded-sm px-3 font-bold text-xs transition",
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
  synthetic,
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
  synthetic: boolean;
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
  const locale = useLocale() as Locale;
  const copy = recouvrementProductCopy(locale);
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
  const footerActions = footerActionsForRecouvrementArtifact(content.artifact, locale);
  const summary = content.summary.length > 0 ? content.summary : fallbackAssistantContent.summary;
  const checks =
    content.complianceChecks.length > 0 ? content.complianceChecks : copy.verification.slice(0, 4);
  const nextActions =
    content.nextActions.length > 0
      ? content.nextActions
      : [copy.ui.fallbackAction1, copy.ui.fallbackAction2];
  const initialPrompt =
    messages.find((message) => message.role === "user")?.content ??
    assistantPromptForTab(activeTab, copy);
  const resultTitle = hasContactRuleArtifact
    ? isBlockedContact
      ? copy.ui.blockedResult
      : copy.ui.verifiedResult
    : (content.artifact?.title ?? copy.ui.analysisResult);
  const verifyButtonLabel = hasContactRuleArtifact ? copy.ui.recheck : copy.ui.regenerate;
  const paymentPlanTitle =
    artifactFamily === "payment_options" ? copy.ui.paymentOptions : copy.ui.proposedSchedule;

  return (
    <aside
      aria-label={copy.ui.assistant}
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
              <span className="whitespace-nowrap">{copy.ui.assistant}</span>
              <span className="whitespace-nowrap font-semibold text-[#071044]/80">
                {isPinned ? "- RC-2048" : "RC-2048"}
              </span>
              <span
                className={cn(
                  "rounded-full bg-[#f0edff] font-bold text-[#6048ff]",
                  isPinned ? "px-1.5 py-0.5 text-[0.5rem]" : "px-2.5 py-1 text-[0.68rem]",
                )}
              >
                {copy.ui.contextualized}
              </span>
            </h2>
            {!isPinned ? (
              <p className="mt-1 text-[#071044]/70 text-sm">{copy.ui.priorityContext}</p>
            ) : null}
          </div>
          <div className={cn("flex shrink-0 items-center", isPinned ? "gap-1.5" : "gap-2")}>
            <button
              type="button"
              aria-label={isPinned ? copy.ui.detach : copy.ui.pin}
              onClick={onTogglePinned}
              className={cn(
                "grid place-items-center rounded-sm border border-[#dfe2ec] text-[#071044] transition hover:bg-[#f7f8fb]",
                isPinned ? "h-7 w-7" : "h-8 w-8",
              )}
            >
              {isPinned ? <Minimize2 className="h-4 w-4" /> : <Pin className="h-4 w-4" />}
            </button>
            <button
              type="button"
              aria-label={copy.ui.expand}
              onClick={onExpand}
              className={cn(
                "grid place-items-center rounded-sm border border-[#dfe2ec] text-[#071044] transition hover:bg-[#f7f8fb]",
                isPinned ? "h-7 w-7" : "h-8 w-8",
              )}
            >
              <Maximize2 className="h-4 w-4" />
            </button>
            <button
              type="button"
              aria-label={copy.ui.close}
              onClick={onClose}
              className={cn(
                "grid place-items-center rounded-sm text-[#071044] transition hover:bg-[#f7f8fb]",
                isPinned ? "h-7 w-7" : "h-8 w-8",
              )}
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>
        {isPinned ? (
          <div className="mt-5 flex gap-4 overflow-x-auto border-[#eceef5] border-b">
            {assistantTabs.map((tab, index) => (
              <button
                key={tab}
                type="button"
                onClick={() => onSelectTab(tab)}
                className={cn(
                  "relative h-10 shrink-0 font-bold text-[0.72rem] transition",
                  activeTab === tab ? "text-[#6048ff]" : "text-[#071044]",
                )}
              >
                {copy.tabs[index]}
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

      {synthetic ? (
        <div className="shrink-0 border-[#eceef5] border-b bg-[#fffdf7] px-6 pt-2">
          <SyntheticNotice signalId="assistant" compact />
        </div>
      ) : null}

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
            <section className="rounded-md border border-[#dfe2ec] bg-white p-4">
              <h3 className="mb-3 !font-sans !text-[#071044] font-bold text-sm">
                {copy.ui.suggestedActions}
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
          <section className="grid gap-3 rounded-md border border-[#dfe2ec] bg-white p-4 md:grid-cols-[minmax(0,1fr)_120px_100px_168px]">
            <div className="flex items-center gap-3">
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-[#fbf0dd] font-bold text-[#d97700]">
                MD
              </span>
              <div>
                <p className="font-bold text-sm">M. D.</p>
                <p className="mt-1 rounded-sm bg-[#ffe8e5] px-2 py-1 font-semibold text-[#f23932] text-xs">
                  {copy.ui.brokenPromise}
                </p>
              </div>
            </div>
            <div>
              <p className="font-extrabold text-sm">840,00 €</p>
              <p className="mt-1 text-xs">{copy.ui.amountDue}</p>
            </div>
            <div>
              <p className="font-extrabold text-sm">32 {copy.ui.days}</p>
              <p className="mt-1 text-xs">{copy.ui.delay}</p>
            </div>
            <div
              className={cn(
                "rounded-sm px-3 py-2 text-xs",
                isBlockedContact ? "bg-[#fff1ef] text-[#a23b2a]" : "bg-[#e9f7e9] text-[#145b2b]",
              )}
            >
              <p className="flex items-center gap-2 font-bold">
                {isBlockedContact ? <X className="h-4 w-4" /> : <CircleCheck className="h-4 w-4" />}
                {isBlockedContact ? copy.ui.blocked : copy.ui.contactAllowed}
              </p>
              <p className="mt-1">{isBlockedContact ? contactStatus : "8h - 20h"}</p>
              {isBlockedContact && contactReasonCode ? (
                <p className="mt-1 font-bold text-[0.62rem]">{contactReasonCode}</p>
              ) : null}
            </div>
          </section>

          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {assistantActions.map(({ tab, Icon }, index) => {
              const label = copy.actions[index]?.[0] ?? copy.tabs[0];
              return (
                <button
                  key={tab}
                  type="button"
                  onClick={() => onSelectTab(tab)}
                  className={cn(
                    "flex min-h-12 items-center justify-center gap-2 rounded-sm border px-3 font-bold text-xs transition",
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

          <div className="mt-5 ml-auto max-w-[430px] rounded-md bg-[#f0edff] px-5 py-4 text-[#071044] text-sm leading-6 shadow-[0_8px_18px_rgba(96,72,255,0.08)]">
            {initialPrompt}
          </div>

          <article className="mt-5 rounded-md border border-[#dfe2ec] bg-white p-5 shadow-[0_12px_28px_rgba(7,16,68,0.05)]">
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
              <div className="mb-4 rounded-sm border border-[#ffd2c9] bg-[#fff5f3] px-4 py-3 text-[#a23b2a] text-xs">
                {error}
              </div>
            ) : null}
            {hasStructuredArtifact && content.rawResponse && status !== "loading" ? (
              <div className="mb-4 rounded-md bg-[#f0edff] px-4 py-3 text-[#071044] text-sm leading-6">
                {content.rawResponse}
              </div>
            ) : null}
            {status === "loading" ? <AssistantThinkingIndicator label={thinkingLabel} /> : null}
            <div className="grid gap-4">
              {hasContactRuleArtifact ? (
                <AssistantContactRulePanel content={content} status={status} />
              ) : (
                <>
                  <section className="rounded-sm border border-[#dfe2ec] bg-[#fbfbfd] p-4">
                    <h3 className="mb-2 !font-sans !text-[#071044] font-bold text-sm">
                      {copy.tabs[4]}
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
                    <section className="rounded-sm border border-[#dfe2ec] bg-[#fbfbfd] p-4">
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
                  <section className="rounded-sm border border-[#dfe2ec] bg-[#fbfbfd] p-4">
                    <h3 className="mb-2 !font-sans !text-[#071044] font-bold text-sm">
                      {copy.ui.rules}
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
              <section className="rounded-sm border border-[#dfe2ec] bg-[#fbfbfd] p-4">
                <h3 className="mb-2 !font-sans !text-[#071044] font-bold text-sm">
                  {copy.ui.suggestedActions}
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
                {copy.ui.reducePanel}
              </button>
              <button
                type="button"
                onClick={onExpand}
                className="inline-flex items-center gap-2 font-semibold text-[#071044]"
              >
                {copy.ui.grow}
                <Maximize2 className="h-4 w-4" />
              </button>
            </div>
            <p className="mt-3 text-[#071044]/55 text-[0.64rem]">{copy.ui.disclaimer}</p>
          </>
        ) : (
          <>
            <AssistantFooterActions actions={footerActions} onAction={onAction} />
            <form
              className="mt-4 flex min-h-[56px] items-center gap-3 rounded-sm border border-[#b7aaff] bg-white px-4 shadow-[0_8px_18px_rgba(96,72,255,0.06)]"
              onSubmit={(event) => {
                event.preventDefault();
                onSendMessage();
              }}
            >
              <input
                aria-label={copy.ui.assistantQuestion}
                value={inputValue}
                onChange={(event) => onInputChange(event.target.value)}
                placeholder={copy.ui.continueChat}
                className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-[#071044]/55"
              />
              <button
                type="submit"
                aria-label={copy.ui.sendQuestion}
                disabled={status === "loading" || inputValue.trim().length === 0}
                className="grid h-10 w-10 place-items-center rounded-sm bg-[#6048ff] text-white transition disabled:bg-[#c8bbff]"
              >
                <Send className="h-5 w-5" />
              </button>
            </form>
            <p className="mt-3 text-[#071044]/55 text-[0.68rem]">{copy.ui.disclaimer}</p>
          </>
        )}
      </footer>
    </aside>
  );
}

export function RecouvrementProductExperience() {
  const locale = useLocale() as Locale;
  const copy = recouvrementProductCopy(locale);
  const dateLocale = locale === "fr" ? "fr-FR" : locale === "de" ? "de-DE" : "en-GB";
  // The REAL case queue (lot 9): counters, the notification badge and the
  // priority dossier all derive from the durable store — never invented.
  const { data: queue } = useQuery({
    queryKey: ["recouvrement-queue"],
    queryFn: ({ signal }) => fetchRecouvrementQueue(signal),
    staleTime: 30_000,
  });
  const counters = queue?.counters ?? null;
  const priorityCase =
    queue?.cases.find((c) => c.status === "relance_a_valider") ?? queue?.cases[0] ?? null;
  const reasons = priorityCase
    ? [
        ...(priorityCase.missed_promise_date
          ? [
              copy.ui.missedPromise.replace(
                "{date}",
                new Date(priorityCase.missed_promise_date).toLocaleDateString(dateLocale, {
                  day: "numeric",
                  month: "long",
                }),
              ),
            ]
          : []),
        copy.ui.significantDelay.replace("{days}", String(priorityCase.days_late)),
        copy.ui.schedulePossible,
        copy.ui.contactWindow
          .replace("{start}", priorityCase.contact_window_start)
          .replace("{end}", priorityCase.contact_window_end),
      ]
    : [];
  const [assistantMode, setAssistantMode] = useState<AssistantMode>("closed");
  const [activeAssistantTab, setActiveAssistantTab] = useState(defaultAssistantTab);
  const [assistantContent, setAssistantContent] =
    useState<GeneratedAssistantContent>(fallbackAssistantContent);
  const [assistantStatus, setAssistantStatus] = useState<AssistantStatus>("idle");
  const [assistantSynthetic, setAssistantSynthetic] = useState(false);
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
  const thinkingLabel = copy.thinking[thinkingStep % copy.thinking.length] ?? copy.ui.thinking;

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
        setAssistantContent(pendingContentForTask(route.targetTask, copy));
        setSelectedVersionId("v1");
      }

      setAssistantInput("");
      setAssistantError(null);
      setAssistantSynthetic(false);
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
        setAssistantSynthetic(true);
        const response = buildInvalidDraftEditResponse(currentArtifact, locale);
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
            history: buildAssistantHistory(priorThread, copy),
            system_prompt_override: copy.systemPrompt,
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
              const parsed = parseGeneratedAssistantContent(finalResponse, copy);
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
          locale,
        );
        const parsed = contentFromScheduleProposal(proposal, copy);
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
        const summary = buildCaseSummaryDraft(locale);
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
          language: locale,
          assistantState: {
            activeTask: route.targetTask,
            activeTab: activeAssistantTab,
            // DECLARED, not guessed — and minted only by `routeRecouvrementTaskClick`, i.e.
            // only when the operator pressed a named button. The agent honours it and never
            // re-classifies the prompt. Free text carries none: there the classifier answers.
            declaredIntent: route.declaredIntent,
            caseId: "RC-2048",
            currentArtifact,
            currentActionContext: options.pendingAction
              ? {
                  action: options.pendingAction,
                  artifactId: currentArtifact?.id ?? null,
                  artifactFamily: artifactFamilyForArtifact(currentArtifact),
                }
              : null,
            history: buildAssistantHistory(priorThread, copy),
          },
          signal: controller.signal,
        })
          .then((response) => {
            if (controller.signal.aborted) return;
            // ADR 0026 — interrogate the THING. The parser follows the artifact the agent
            // ACTUALLY returned, never the family the click hoped for. When the two
            // disagreed (a "Résumer" click answered with a reminder draft) the drawer read
            // a message artifact through the summary parser and rendered an empty panel:
            // the visible half of the bug the declared intent fixes at the source.
            const returnedFamily = artifactFamilyForArtifact(response.artifact);
            const family = returnedFamily ?? artifactFamilyForTask(route.targetTask);
            const parsed =
              family === "schedule"
                ? contentFromRecouvrementScheduleResponse(response, copy)
                : family === "message"
                  ? contentFromRecouvrementDraftResponse(response, copy)
                  : family === "summary"
                    ? contentFromCaseSummaryResponse(response)
                    : family === "payment_options"
                      ? contentFromPaymentOptionsResponse(response)
                      : contentFromRecouvrementContactResponse(response, locale);
            completeAfterThinkingMinimum(() => {
              setAssistantContent(parsed);
              setSelectedVersionId(parsed.versions[0]?.id ?? "v1");
              setDrawerStateModel((current) => ({
                ...current,
                // Same reason: the selector highlights the family that is on screen.
                selectedArtifactFamily: family,
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
            setAssistantSynthetic(true);
            if (usesStructuredDraftBackend) {
              const fallbackResponse = buildDraftBackendUnavailableFallback(
                currentArtifact,
                locale,
              );
              const parsed = contentFromRecouvrementDraftResponse(fallbackResponse, copy);
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
                locale,
              );
              const parsed = contentFromScheduleProposal(proposal, copy);
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
              const summary = buildCaseSummaryDraft(locale);
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
              const fallbackResponse = buildPaymentOptionsBackendUnavailableFallback(locale);
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
            const fallbackResponse = buildContactRuleBackendUnavailableFallback(locale);
            const parsed = contentFromRecouvrementContactResponse(fallbackResponse, locale);
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
    [activeAssistantTab, copy, locale],
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
        setAssistantSynthetic(false);
        setAssistantStatus("loading");

        void sendRecouvrementAssistantAction({
          artifact: currentArtifact,
          actionName,
          conversationId,
          turnId: crypto.randomUUID(),
          language: locale,
          signal: controller.signal,
        })
          .then((response) => {
            if (controller.signal.aborted) return;
            completeAfterThinkingMinimum(() => applyActionResponse(response));
          })
          .catch((err) => {
            if (controller.signal.aborted) return;
            console.warn("[recouvrement-assistant] structured action backend unavailable", err);
            setAssistantSynthetic(true);
            completeAfterThinkingMinimum(() => applyActionResponse(fallback()));
          });
      };

      if (/inserer|insert|einfugen/.test(normalized)) {
        runBackendArtifactAction("insert_artifact_in_case", () =>
          buildArtifactInsertionPreparedResponse(
            currentArtifact as RecouvrementAssistantArtifact,
            action,
            locale,
          ),
        );
        return;
      }

      if (/soumettre|validation|submit|approval|einreichen|freigabe/.test(normalized)) {
        runBackendArtifactAction("submit_for_validation", () =>
          buildArtifactPendingValidationResponse(
            currentArtifact as RecouvrementAssistantArtifact,
            action,
            locale,
          ),
        );
        return;
      }

      if (/copier|copy|kopieren/.test(normalized)) {
        if (!currentArtifact) return;
        const response: RecouvrementAssistantResponse = {
          visibleReply: copy.ui.copyReady,
          artifact: currentArtifact,
          cardUpdates: {
            summary: assistantContentRef.current.summary,
            complianceChecks: [
              copy.ui.artifactKept,
              copy.ui.noMessage,
              copy.ui.noIrreversibleAction,
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

      if (
        /rappel|reminder|callback|ruckruf/.test(normalized) &&
        currentArtifact?.type === "contact_rule_v1"
      ) {
        runBackendArtifactAction("prepare_reminder_tomorrow", () =>
          buildReminderPreparedResponse(currentArtifact, locale),
        );
        return;
      }

      if (/message|email|nachricht/.test(normalized)) {
        sendAssistantTurn(action, false, { forcedTask: "draft_reminder", pendingAction: action });
        return;
      }

      if (
        /echeancier|duree|comparer|payment plan|duration|compare|ratenplan|laufzeit|vergleichen/.test(
          normalized,
        )
      ) {
        sendAssistantTurn(action, false, { forcedTask: "propose_schedule", pendingAction: action });
        return;
      }

      if (
        /regle|rappel|reporter|appel|rule|reminder|callback|reschedule|call|regel|ruckruf|verschieben|anruf/.test(
          normalized,
        )
      ) {
        sendAssistantTurn(action, false, {
          forcedTask: "check_contact_rule",
          pendingAction: action,
        });
        return;
      }

      if (/relance|modifier|reminder|edit|mahnung|andern/.test(normalized)) {
        sendAssistantTurn(action, false, { forcedTask: "draft_reminder", pendingAction: action });
      }
    },
    [copy, locale, sendAssistantTurn],
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
    sendAssistantTurn(assistantPromptForTab(activeAssistantTab, copy), true, {
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
                aria-label={copy.ui.searchAria}
                placeholder={copy.ui.searchPlaceholder}
                readOnly
                className="h-11 w-full cursor-default rounded-sm border border-[#d7d9e1] bg-white pr-4 pl-12 text-[#050816] text-sm outline-none transition placeholder:text-[#5d6275] focus:border-[#b99245] focus:ring-2 focus:ring-[#b99245]/20"
              />
            </label>
            <div className="flex items-center gap-4 sm:gap-6">
              <button
                type="button"
                aria-label={copy.ui.help}
                className="hidden flex-col items-center gap-1 rounded-sm text-[10.5px] outline-none transition focus-visible:ring-2 focus-visible:ring-[#b99245]/35 sm:flex"
              >
                <CircleHelp className="h-[22px] w-[22px]" />
                {copy.ui.help}
              </button>
              <button
                type="button"
                aria-label={
                  counters
                    ? copy.ui.notificationsAria.replace("{count}", String(counters.open))
                    : copy.ui.notifications
                }
                className="relative flex flex-col items-center gap-1 rounded-sm text-[10.5px] outline-none transition focus-visible:ring-2 focus-visible:ring-[#b99245]/35"
              >
                <Bell className="h-[22px] w-[22px]" />
                {counters && counters.open > 0 ? (
                  <span className="-top-1 absolute right-1 grid h-4 min-w-4 place-items-center rounded-full bg-[#b99245] px-1 text-[#050816] text-[9px]">
                    {counters.open}
                  </span>
                ) : null}
                {copy.ui.notifications}
              </button>
              <button
                type="button"
                aria-label={copy.ui.accountAria}
                className="flex items-center gap-3 rounded-sm outline-none transition focus-visible:ring-2 focus-visible:ring-[#b99245]/35"
              >
                <span className="grid h-10 w-10 place-items-center rounded-full bg-[#fbf0dd] font-bold text-[#050816]">
                  JD
                </span>
                <span className="hidden text-left sm:block">
                  <span className="block font-bold text-sm">Julie Dubois</span>
                  <span className="block text-[#050816]/65 text-xs">{copy.ui.role}</span>
                </span>
                <ChevronDown className="h-5 w-5" />
              </button>
            </div>
          </header>

          <div className="grid min-h-0 flex-1 lg:grid-cols-[258px_minmax(0,1fr)]">
            <aside className="hidden min-h-0 flex-col border-[#d8d8d8] border-r bg-white lg:flex">
              <div className="border-[#e2e2e6] border-b px-6 py-8">
                <p className="font-extrabold text-[#b99245] text-sm uppercase tracking-[0]">
                  {copy.ui.area}
                </p>
                <p className="mt-2 text-[#565656] text-xs leading-5">{copy.ui.areaSubtitle}</p>
              </div>
              <nav className="flex flex-col gap-1 px-4 py-6" aria-label={copy.ui.navAria}>
                {navigation.map(({ Icon, counterKey, active }, index) => (
                  <button
                    key={copy.nav[index]}
                    type="button"
                    className={cn(
                      "flex min-h-[52px] items-center gap-4 rounded-sm px-4 text-left font-bold text-[0.92rem] transition",
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
                    <span>{copy.nav[index]}</span>
                    {counterKey && counters ? (
                      <CountBadge count={counters[counterKey]} className="ml-auto" />
                    ) : null}
                  </button>
                ))}
              </nav>
              <div className="mt-auto border-[#e2e2e6] border-t px-6 py-7">
                <div className="flex items-start gap-3 text-[#050816] text-sm leading-5">
                  <LockKeyhole className="mt-0.5 h-5 w-5 shrink-0" />
                  <p>
                    {copy.ui.limitedAccess.split("\n").map((line) => (
                      <span className="block" key={line}>
                        {line}
                      </span>
                    ))}
                  </p>
                </div>
                <div className="mt-7 flex items-center gap-3 text-sm">
                  <span className="h-3 w-3 rounded-full bg-[#139b45]" />
                  {copy.ui.online}
                </div>
              </div>
            </aside>

            <main className="min-h-0 overflow-y-auto bg-[radial-gradient(circle_at_62%_8%,rgba(231,235,246,0.58),transparent_32%),#fbfbfd]">
              <div className="px-4 py-10 sm:px-6 lg:py-11">
                <div className="mx-auto max-w-[1274px]">
                  <div className="mb-8">
                    <h1 className="!font-sans !text-[#050816] font-extrabold text-[2rem] leading-tight tracking-[0]">
                      {copy.ui.greeting}
                    </h1>
                    <p className="mt-2 text-[#071044] text-[1.12rem]">{copy.ui.queueReady}</p>
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
                          <span className="inline-flex rounded-sm bg-[#fff3e4] px-3 py-1.5 font-bold text-[#d97700] text-xs uppercase">
                            {copy.ui.now}
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
                                <span className="shrink-0 rounded-md bg-[#ffe8e5] px-2.5 py-1 font-medium text-[#f23932] text-[0.68rem]">
                                  {copy.ui.brokenPromise}
                                </span>
                              </div>
                              <p className="mt-2 text-[0.9rem] leading-[1.2rem]">M. D.</p>
                              <div className="mt-3 flex items-center gap-5 font-semibold text-[0.94rem] leading-5">
                                <span>840,00 €</span>
                                <span className="h-1 w-1 rounded-full bg-[#071044]" />
                                <span className="font-medium">
                                  {copy.ui.delay} {priorityCase?.days_late ?? "—"} {copy.ui.days}
                                </span>
                              </div>
                              <div className="mt-4 inline-flex items-center gap-3 rounded-sm bg-[#e9f7e9] px-4 py-2 text-[#145b2b] text-[0.86rem] leading-[1.15rem]">
                                <CircleCheck className="h-4 w-4 shrink-0" />
                                <span>
                                  {copy.ui.contactWindow
                                    .replace("{start}", priorityCase?.contact_window_start ?? "—")
                                    .replace("{end}", priorityCase?.contact_window_end ?? "—")}
                                </span>
                              </div>
                            </div>
                          </div>

                          <div className="border-[#dfe2ec] border-t pt-6 lg:border-t-0 lg:border-l lg:pt-0 lg:pl-8">
                            <h3 className="mb-4 !font-sans !text-[#d97700] font-bold text-sm">
                              {copy.ui.why}
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
                            <p className="font-bold text-sm">{copy.ui.recommendedAction}</p>
                            <p className="mt-1 text-[0.9rem]">{copy.ui.prepareScheduleSentence}</p>
                          </div>
                          <div className="flex flex-wrap items-center gap-3 lg:flex-nowrap">
                            <button
                              type="button"
                              className="inline-flex h-11 w-[196px] items-center justify-center gap-3 rounded-lg bg-[linear-gradient(180deg,#e38a00,#cf7300)] font-bold text-sm text-white shadow-[0_10px_22px_rgba(217,119,0,0.22)] transition hover:bg-[#c96f00]"
                            >
                              {copy.ui.prepareSchedule}
                              <ChevronRight className="h-5 w-5" />
                            </button>
                            <button
                              type="button"
                              className="inline-flex h-11 w-[122px] items-center justify-center gap-3 rounded-lg border border-[#cfd4e3] bg-white font-semibold text-sm transition hover:bg-[#f7f8fb]"
                            >
                              {copy.ui.postpone}
                              <Clock3 className="h-5 w-5" />
                            </button>
                            <button
                              type="button"
                              onClick={() => openAssistant("Préparer une relance")}
                              className="inline-flex h-11 w-[198px] items-center justify-center gap-2 rounded-lg px-1.5 font-semibold text-[#6048ff] text-[0.74rem] transition hover:bg-[#f4f1ff]"
                            >
                              <Sparkles className="h-4 w-4" />
                              {copy.ui.prepareWithAssistant}
                            </button>
                          </div>
                        </div>
                      </section>

                      <section className="relative mt-8 rounded-md border border-[#c8bbff] bg-[linear-gradient(120deg,#fbfaff,#f9f7ff)] py-6 pr-6 pl-5 shadow-[0_14px_30px_rgba(96,72,255,0.055)]">
                        <AssistantCardBloom />
                        <div className="relative z-10 mb-6 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                          <div>
                            <h2 className="flex flex-wrap items-center gap-3 !font-sans !text-[#6048ff] font-bold text-sm uppercase tracking-[0]">
                              <Sparkles className="h-5 w-5" />
                              {copy.ui.assistant}
                              <span className="rounded-full border border-[#c8bbff] bg-white px-2.5 py-1 font-bold text-[#6048ff] text-[0.68rem]">
                                RC-2048
                              </span>
                            </h2>
                            <p className="mt-2 max-w-[520px] text-[#071044] text-sm">
                              {copy.ui.assistantHelp}
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => openAssistant()}
                            className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-md border border-[#9d8cff] bg-white px-4 font-bold text-[#6048ff] text-xs shadow-[0_8px_18px_rgba(96,72,255,0.12)] transition hover:bg-[#f4f1ff]"
                          >
                            {copy.ui.openAssistant}
                            <ChevronRight className="h-4 w-4" />
                          </button>
                        </div>
                        <div className="relative z-10 grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
                          {assistantActions.map(({ tab, Icon }, index) => (
                            <button
                              key={tab}
                              type="button"
                              onClick={() => openAssistant(tab)}
                              className="flex h-[112px] items-center gap-3 overflow-hidden rounded-sm border border-[#e2defd] bg-white px-3.5 py-3 text-left shadow-[0_8px_18px_rgba(96,72,255,0.035)] transition hover:border-[#b7aaff] hover:bg-[#fbfaff]"
                            >
                              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-[#f0edff] text-[#6048ff]">
                                <Icon className="h-5 w-5" />
                              </span>
                              <span className="min-w-0 flex-1">
                                <span className="block font-bold text-[0.76rem] leading-[1rem]">
                                  {copy.actions[index]?.[0]}
                                </span>
                                <span className="mt-1.5 block text-[0.66rem] leading-[0.98rem]">
                                  {copy.actions[index]?.[1]}
                                </span>
                              </span>
                              <ChevronRight className="ml-auto h-3.5 w-3.5 shrink-0" />
                            </button>
                          ))}
                        </div>
                      </section>

                      <section className="mt-10">
                        <h2 className="mb-5 !font-sans !text-[#050816] font-extrabold text-2xl leading-7">
                          {copy.ui.nextTitle}
                        </h2>
                        <div className="grid gap-6 md:grid-cols-3">
                          {nextItems.map(({ counterKey, Icon, accent }, index) => (
                            <button
                              key={counterKey}
                              type="button"
                              className="flex h-[154px] flex-col rounded-md border border-[#dfe2ec] bg-white p-6 text-left shadow-[0_2px_8px_rgba(0,0,0,0.055)] transition hover:border-[#d97700]/40 hover:shadow-[0_8px_20px_rgba(7,16,68,0.07)]"
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
                                  {counters ? counters[counterKey] : "—"}
                                </span>
                                <span className="font-bold text-sm">
                                  {copy.next[index]?.[0]}
                                  <br />
                                  <span className="font-semibold">{copy.next[index]?.[1]}</span>
                                </span>
                              </span>
                              <span className="mt-auto flex items-center justify-end border-[#e4e6ee] border-t pt-3 font-semibold text-[#0047ff] text-sm">
                                {copy.ui.viewList}
                                <ChevronRight className="ml-auto h-5 w-5 text-[#071044]" />
                              </span>
                            </button>
                          ))}
                        </div>
                      </section>

                      <section className="mt-10 flex min-h-[72px] flex-col items-start gap-3 rounded-md border border-[#dfe2ec] bg-white px-6 py-4 shadow-[0_2px_8px_rgba(0,0,0,0.055)] sm:flex-row sm:items-center">
                        <Info className="mr-4 h-5 w-5" />
                        <span className="mr-6 font-bold">{copy.ui.todayNote}</span>
                        <span className="hidden h-8 w-px bg-[#dfe2ec] sm:block" />
                        <p className="text-sm text-[#071044]/80 sm:ml-6">
                          {copy.ui.reachableCases}
                        </p>
                        <button
                          type="button"
                          className="inline-flex items-center gap-3 font-semibold text-[#0047ff] text-sm sm:ml-auto"
                        >
                          {copy.ui.viewWhich}
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
                            {copy.ui.quickActions}
                          </h2>
                          <p className="mt-1.5 text-[#5d6275] text-xs">{copy.ui.quickSubtitle}</p>
                        </div>
                        <div className="divide-y divide-[#e4e6ee]">
                          {quickActions.map((Icon, index) => (
                            <button
                              key={copy.quick[index]?.[0]}
                              type="button"
                              className="flex w-full items-center gap-4 px-6 py-5 text-left transition hover:bg-[#f7f8fb]"
                            >
                              <Icon className="h-6 w-6 shrink-0" />
                              <span>
                                <span className="block font-bold text-sm">
                                  {copy.quick[index]?.[0]}
                                </span>
                                <span className="mt-1 block text-xs">{copy.quick[index]?.[1]}</span>
                              </span>
                              <ChevronRight className="ml-auto h-5 w-5" />
                            </button>
                          ))}
                        </div>
                      </section>

                      <section className={cn(cardClass, "p-6")}>
                        <div className="mb-6 flex items-center justify-between">
                          <h2 className="!font-sans !text-[#050816] font-extrabold text-lg">
                            {copy.ui.contactFrameworkShort}
                          </h2>
                          <span className="rounded-full bg-[#e4f5dd] px-3 py-1 font-bold text-[#187434] text-xs">
                            RC-2048
                          </span>
                        </div>
                        <div className="mb-6 flex items-start gap-4 rounded-sm bg-[#edf9df] px-5 py-5 text-[#145b2b]">
                          <CircleCheck className="mt-0.5 h-5 w-5" />
                          <p className="font-semibold text-sm">
                            {copy.ui.contactAllowedToday}
                            <br />
                            <span className="font-medium">8h - 20h</span>
                          </p>
                        </div>
                        <div className="space-y-5 text-sm">
                          <div>
                            <p className="mb-2 font-bold">{copy.ui.recommendedChannel}</p>
                            <p className="flex items-center gap-3">
                              <Phone className="h-5 w-5" />
                              {copy.ui.outboundCall}
                            </p>
                          </div>
                          <div>
                            <p className="mb-2 font-bold">{copy.ui.alternative}</p>
                            <p className="flex items-center gap-3">
                              <Mail className="h-5 w-5" />
                              {copy.ui.confirmationEmail}
                            </p>
                          </div>
                        </div>
                      </section>

                      <button
                        type="button"
                        onClick={() => openAssistant("Vérifier une règle")}
                        className="flex w-full items-center gap-4 rounded-md border border-[#f1d8ab] bg-[linear-gradient(90deg,#fff8ec,#fff2de)] p-6 text-left shadow-[0_2px_8px_rgba(0,0,0,0.05)] transition hover:bg-[#ffefcf]"
                      >
                        <Sparkles className="h-7 w-7 text-[#071044]" />
                        <span>
                          <span className="block font-bold text-sm">{copy.ui.needHelp}</span>
                          <span className="mt-1 block text-xs">{copy.ui.consultRules}</span>
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
          aria-label={copy.ui.close}
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
          synthetic={assistantSynthetic}
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
