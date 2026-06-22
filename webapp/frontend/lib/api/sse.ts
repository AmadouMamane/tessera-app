/**
 * SSE client for the agent's `/chat` endpoint.
 *
 * The FastAPI route emits one `turn.start`, optional `turn.draft` events,
 * a `turn.end` envelope, and `turn.error` on failure. We use
 * `@microsoft/fetch-event-source` rather than the native `EventSource`
 * because (a) we need to POST a body, (b) we need fine-grained abort
 * control, and (c) the native API does not surface non-200 status codes
 * usefully.
 */
import { fetchEventSource } from "@microsoft/fetch-event-source";

import { getStoredModel } from "@/lib/models";

import {
  type ChatEndEvent,
  ChatEndEventSchema,
  ChatErrorEventSchema,
  ChatStartEventSchema,
  ChatTokenEventSchema,
} from "./schemas";

export interface ChatTurnRequest {
  message: string;
  conversation_id?: string;
  /**
   * Stable long-term-memory identity key (ADR 0007). Persisted per browser so
   * the agent can recall durable facts across separate conversations.
   */
  subject_id?: string;
  language?: "fr" | "de" | "en";
  history?: Array<{ role: "user" | "assistant"; content: string }>;
  /** Optional chat-model override; defaults to the Settings picker choice. */
  model?: string;
  /** Sandbox console: replace the system prompt for this turn only. */
  system_prompt_override?: string;
  /** Sandbox console: guard categories disabled for this turn (e.g. ["prompt_injection"]). */
  guard_overrides?: string[];
}

export interface ChatTurnCallbacks {
  onStart?: (event: { conversation_id: string; turn_id: string }) => void;
  onToken?: (token: string) => void;
  onEnd?: (envelope: ChatEndEvent) => void;
  onError?: (message: string) => void;
}

export interface StreamChatOptions extends ChatTurnCallbacks {
  signal?: AbortSignal;
  /**
   * Originating client surface. A privileged surface passes its hint so the BFF
   * can — only for the right verified next-auth session — forward an operator
   * assertion (ADR 0010 Phase B/C): `"console"` → cockpit-embedded (the cockpit
   * operator console), `"recouvrement"` → dedicated-ui (recouvrement's business
   * console). It is a hint, not a privilege: without the right session the BFF
   * ignores it and the turn stays on the customer widget. The widget omits it.
   */
  surface?: "console" | "recouvrement";
}

/**
 * Open an SSE connection to `/api/chat` and dispatch parsed events to the
 * provided callbacks. Resolves once the server closes the stream.
 */
export async function streamChat(
  payload: ChatTurnRequest,
  { signal, surface, onStart, onToken, onEnd, onError }: StreamChatOptions = {},
): Promise<void> {
  const model = payload.model ?? getStoredModel();
  await fetchEventSource("/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      ...(surface ? { "X-Tessera-Client-Surface": surface } : {}),
    },
    body: JSON.stringify(model ? { ...payload, model } : payload),
    signal,
    openWhenHidden: true,
    onopen: async (response) => {
      if (!response.ok) {
        if (response.status === 429) {
          const header = Number(response.headers.get("Retry-After"));
          // Fall back to the configured 20/hour window (3600s) if the header
          // is absent.
          const seconds = Number.isFinite(header) && header > 0 ? header : 3600;
          throw new Error(rateLimitMessage(seconds, payload.language));
        }
        const text = await response.text().catch(() => "");
        throw new Error(`chat stream returned ${response.status}: ${text || "unknown error"}`);
      }
    },
    onmessage(event) {
      const data = safeParseJson(event.data);
      if (data === undefined) return;
      switch (event.event) {
        case "turn.start": {
          const parsed = ChatStartEventSchema.safeParse(data);
          if (parsed.success) onStart?.(parsed.data);
          return;
        }
        case "turn.token": {
          const parsed = ChatTokenEventSchema.safeParse(data);
          if (parsed.success) onToken?.(parsed.data.token);
          return;
        }
        case "turn.end": {
          const parsed = ChatEndEventSchema.safeParse(data);
          if (parsed.success) onEnd?.(parsed.data);
          return;
        }
        case "turn.error": {
          const parsed = ChatErrorEventSchema.safeParse(data);
          if (parsed.success) onError?.(parsed.data.error);
          return;
        }
        default:
          return;
      }
    },
    onerror(err) {
      onError?.(err instanceof Error ? err.message : String(err));
      throw err; // let fetchEventSource stop retrying
    },
  });
}

/**
 * Human-readable, localized message for a 429 rate-limit response. The wait is
 * derived from the server's `Retry-After` (seconds) and rounded up to the
 * nearest hour/minute so the user sees the exact reset window.
 */
function rateLimitMessage(seconds: number, language: ChatTurnRequest["language"]): string {
  const lang = language ?? "fr";
  const duration = formatDuration(seconds, lang);
  switch (lang) {
    case "de":
      return `Sie haben Ihr zulässiges Anfragenlimit erreicht. Bitte warten Sie ${duration}, bis Ihr Kontingent zurückgesetzt wird.`;
    case "en":
      return `You've reached your allowed request limit. Please wait ${duration} for your quota to reset.`;
    default:
      return `Vous avez atteint votre limite autorisée de requêtes. Veuillez patienter ${duration} pour la réinitialisation de votre quota.`;
  }
}

function formatDuration(seconds: number, lang: NonNullable<ChatTurnRequest["language"]>): string {
  const units = {
    fr: {
      hour: ["heure", "heures"],
      minute: ["minute", "minutes"],
      second: ["seconde", "secondes"],
    },
    de: {
      hour: ["Stunde", "Stunden"],
      minute: ["Minute", "Minuten"],
      second: ["Sekunde", "Sekunden"],
    },
    en: { hour: ["hour", "hours"], minute: ["minute", "minutes"], second: ["second", "seconds"] },
  }[lang];
  const plural = (n: number, [one, many]: string[]) => `${n} ${n > 1 ? many : one}`;
  if (seconds >= 3600) return plural(Math.ceil(seconds / 3600), units.hour);
  if (seconds >= 60) return plural(Math.ceil(seconds / 60), units.minute);
  return plural(Math.max(1, Math.ceil(seconds)), units.second);
}

function safeParseJson(raw: string): unknown {
  if (!raw) return undefined;
  try {
    return JSON.parse(raw);
  } catch {
    return undefined;
  }
}
