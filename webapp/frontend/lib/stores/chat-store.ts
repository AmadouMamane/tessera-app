/**
 * Client-side conversation state.
 *
 * We keep the conversation in a Zustand store rather than React component
 * state so that the SSE callbacks (which live outside the render tree)
 * can update messages without prop-drilling and without re-rendering the
 * composer on every token.
 *
 * The store itself is intentionally kept lean and in-memory. Surfaces that need
 * continuity add it on top via the durable transcript API: the recouvrement
 * console lists "Récents" and the produit widget persists its own conversation
 * id (localStorage) and resumes it through `loadConversation` after a reload.
 */
import { create } from "zustand";
import { devtools } from "zustand/middleware";

import type { ChatCitation } from "@/lib/api/schemas";

export type MessageRole = "user" | "assistant" | "system";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: number;
  citations?: ChatCitation[];
  needsEscalation?: boolean;
  confidence?: number | null;
}

interface ChatState {
  conversationId: string | null;
  /**
   * Signed capability letting THIS browser re-read THIS conversation (audit 2026-07-12, F-4).
   * Minted by the agent at `turn.start`. The transcript read is no longer granted by knowing
   * a conversation id — the id was never secret — so the widget must keep the capability to
   * resume after a reload.
   */
  resumeToken: string | null;
  turnId: string | null;
  messages: ChatMessage[];
  isStreaming: boolean;
  lastError: string | null;
  start: (conversationId: string, turnId: string, resumeToken?: string) => void;
  loadConversation: (conversationId: string, messages: ChatMessage[]) => void;
  appendUser: (content: string) => ChatMessage;
  startAssistant: (turnId: string) => void;
  appendToken: (token: string) => void;
  finalizeAssistant: (message: Omit<ChatMessage, "createdAt" | "role">) => void;
  setError: (message: string) => void;
  setStreaming: (streaming: boolean) => void;
  truncateFromMessage: (messageId: string) => void;
  removeLastExchange: () => void;
  reset: () => void;
}

function id(): string {
  return globalThis.crypto?.randomUUID() ?? Math.random().toString(36).slice(2);
}

export const useChatStore = create<ChatState>()(
  devtools(
    (set) => ({
      conversationId: null,
      resumeToken: null,
      turnId: null,
      messages: [],
      isStreaming: false,
      lastError: null,

      start: (conversationId, turnId, resumeToken) =>
        set((state) => ({
          conversationId,
          turnId,
          isStreaming: true,
          lastError: null,
          // Keep the one we already hold if this turn did not carry a fresh one, so a
          // mid-conversation turn never drops the capability that resumes it.
          resumeToken: resumeToken ?? state.resumeToken,
        })),

      // Resume a "Récents" conversation: load its persisted transcript and keep
      // its id so the next turn continues the SAME conversation server-side.
      loadConversation: (conversationId, messages) =>
        set({
          conversationId,
          turnId: null,
          messages,
          isStreaming: false,
          lastError: null,
        }),

      appendUser: (content) => {
        const message: ChatMessage = {
          id: id(),
          role: "user",
          content,
          createdAt: Date.now(),
        };
        set((state) => ({ messages: [...state.messages, message] }));
        return message;
      },

      // Add an empty assistant bubble as soon as the first token arrives.
      startAssistant: (turnId) =>
        set((state) => ({
          messages: [
            ...state.messages,
            { id: turnId, role: "assistant", content: "", createdAt: Date.now() },
          ],
        })),

      // Append a token to the last assistant message (in-place mutation via
      // object replacement so Zustand detects the change).
      appendToken: (token) =>
        set((state) => {
          const messages = [...state.messages];
          const last = messages[messages.length - 1];
          if (last?.role === "assistant") {
            messages[messages.length - 1] = { ...last, content: last.content + token };
          }
          return { messages };
        }),

      finalizeAssistant: (payload) =>
        set((state) => {
          const messages = [...state.messages];
          const lastIdx = messages.findLastIndex((m) => m.role === "assistant");
          const existing = lastIdx !== -1 ? messages[lastIdx] : undefined;
          if (existing) {
            // Streaming path: replace the in-progress bubble with final metadata.
            messages[lastIdx] = { ...existing, ...payload, role: "assistant" };
          } else {
            // Non-streaming path (injection block, no tokens emitted).
            messages.push({ ...payload, role: "assistant", createdAt: Date.now() });
          }
          return { messages, isStreaming: false };
        }),

      setError: (lastError) => set({ lastError, isStreaming: false }),

      setStreaming: (isStreaming) => set({ isStreaming }),

      // Removes the given message and everything after it so an inline edit can re-send.
      // Also resets conversationId so the backend starts a clean branch.
      truncateFromMessage: (messageId) =>
        set((state) => {
          const idx = state.messages.findIndex((m) => m.id === messageId);
          if (idx === -1) return {};
          // The capability goes with the id it authorized: a clean branch is a new
          // conversation, and holding a token for the abandoned one grants nothing.
          return {
            messages: state.messages.slice(0, idx),
            conversationId: null,
            resumeToken: null,
          };
        }),

      // Removes the last [user, assistant] pair so sendMessage can re-send cleanly.
      removeLastExchange: () =>
        set((state) => {
          const msgs = [...state.messages];
          const lastAsstIdx = msgs.findLastIndex((m) => m.role === "assistant");
          if (lastAsstIdx === -1) return {};
          msgs.splice(lastAsstIdx, 1);
          const lastUserIdx = msgs.findLastIndex((m) => m.role === "user");
          if (lastUserIdx !== -1) msgs.splice(lastUserIdx, 1);
          return { messages: msgs };
        }),

      reset: () =>
        set({
          conversationId: null,
          resumeToken: null,
          turnId: null,
          messages: [],
          isStreaming: false,
          lastError: null,
        }),
    }),
    { name: "tessera-chat" },
  ),
);
