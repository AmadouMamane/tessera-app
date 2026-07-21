export interface RecouvrementAssistantArtifact {
  id: string;
  type: string;
  task: string;
  title: string;
  status: string;
  content: Record<string, unknown>;
}

export interface RecouvrementAssistantResponse {
  visibleReply: string;
  artifact: RecouvrementAssistantArtifact;
  cardUpdates: Record<string, string[]>;
  suggestedActions: string[];
  decisions?: Record<string, unknown>;
  businessEvents?: Array<Record<string, unknown>>;
  businessScores?: Array<Record<string, unknown>>;
}

export interface SendRecouvrementAssistantMessageRequest {
  caseId?: string;
  message: string;
  assistantState?: Record<string, unknown>;
  conversationId?: string;
  turnId?: string;
  surface?: "dedicated-ui" | "cockpit-embedded";
  language?: "fr" | "en" | "de";
  signal?: AbortSignal;
}

export interface SendRecouvrementAssistantActionRequest {
  caseId?: string;
  artifact: RecouvrementAssistantArtifact;
  actionName: string;
  // NOTE no `requestedBy` (audit 2026-07-12, P0 F-1): the ledger attribution derives
  // from the verified operator assertion the BFF mints — the backend contract rejects
  // a body that still tries to assert an identity (422).
  conversationId?: string;
  turnId?: string;
  surface?: "dedicated-ui" | "cockpit-embedded";
  language?: "fr" | "en" | "de";
  signal?: AbortSignal;
}

const USER_SAFE_RECOUVREMENT_BACKEND_ERROR =
  "La vérification backend est indisponible. Aucune action n'a été exécutée.";

export class RecouvrementAssistantApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(USER_SAFE_RECOUVREMENT_BACKEND_ERROR);
    this.name = "RecouvrementAssistantApiError";
    this.status = status;
    this.detail = detail;
  }
}

export async function sendRecouvrementAssistantMessage({
  caseId = "RC-2048",
  message,
  assistantState,
  conversationId,
  turnId,
  surface = "dedicated-ui",
  language,
  signal,
}: SendRecouvrementAssistantMessageRequest): Promise<RecouvrementAssistantResponse> {
  const response = await fetch("/api/recouvrement-assistant/message", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      case_id: caseId,
      message,
      assistant_state: assistantState,
      conversation_id: conversationId,
      turn_id: turnId,
      surface,
      language,
    }),
    signal,
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new RecouvrementAssistantApiError(response.status, detail || "unknown error");
  }

  return (await response.json()) as RecouvrementAssistantResponse;
}

export async function sendRecouvrementAssistantAction({
  caseId = "RC-2048",
  artifact,
  actionName,
  conversationId,
  turnId,
  surface = "dedicated-ui",
  language,
  signal,
}: SendRecouvrementAssistantActionRequest): Promise<RecouvrementAssistantResponse> {
  const response = await fetch("/api/recouvrement-assistant/action", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      case_id: caseId,
      artifact,
      action_name: actionName,
      conversation_id: conversationId,
      turn_id: turnId,
      surface,
      language,
    }),
    signal,
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new RecouvrementAssistantApiError(response.status, detail || "unknown error");
  }

  return (await response.json()) as RecouvrementAssistantResponse;
}
