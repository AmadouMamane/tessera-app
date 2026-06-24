/**
 * Client-side conversation state.
 *
 * We keep the conversation in a Zustand store rather than React component
 * state so that the SSE callbacks (which live outside the render tree)
 * can update messages without prop-drilling and without re-rendering the
 * composer on every token.
 *
 * The store is intentionally kept lean — no persistence yet; reloading the
 * page resets the conversation. Persistence will be added when a
 * conversations API lands on the backend.
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
  turnId: string | null;
  messages: ChatMessage[];
  isStreaming: boolean;
  lastError: string | null;
  start: (conversationId: string, turnId: string) => void;
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
      turnId: null,
      messages: [],
      isStreaming: false,
      lastError: null,

      start: (conversationId, turnId) =>
        set({ conversationId, turnId, isStreaming: true, lastError: null }),

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
          return { messages: state.messages.slice(0, idx), conversationId: null };
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
          turnId: null,
          messages: [],
          isStreaming: false,
          lastError: null,
        }),
    }),
    { name: "tessera-chat" },
  ),
);
