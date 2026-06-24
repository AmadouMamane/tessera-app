/**
 * Client-side conversation history for the recouvrement console.
 *
 * The chat store keeps no persistence and the backend exposes no per-user
 * conversations API, so this is the ONLY honest history we can offer: the user's
 * OWN conversations, in their OWN browser (localStorage), scoped to this console.
 * It fabricates nothing — an empty store renders an honest empty sidebar. The
 * durable server transcript means a restored conversation can still be continued.
 */
import type { ChatMessage } from "@/lib/stores/chat-store";

const KEY = "tessera.recouvrement.conversations";
const MAX = 50;

export interface StoredConversation {
  id: string; // backend conversationId
  title: string;
  messages: ChatMessage[];
  updatedAt: number;
}

export function listConversations(): StoredConversation[] {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    return (parsed as StoredConversation[])
      .filter((c) => c && typeof c.id === "string" && Array.isArray(c.messages))
      .sort((a, b) => b.updatedAt - a.updatedAt);
  } catch {
    return [];
  }
}

function write(list: StoredConversation[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(list.slice(0, MAX)));
  } catch {
    // ignore quota / disabled storage
  }
}

/** Title from the first user message, trimmed for the sidebar. */
function deriveTitle(messages: ChatMessage[]): string {
  const firstUser = messages.find((m) => m.role === "user");
  const text = (firstUser?.content ?? "").replace(/\s+/g, " ").trim();
  return text.length > 60 ? `${text.slice(0, 60)}…` : text || "Conversation";
}

/** Upsert the active conversation (no-op without an id or any message). */
export function saveConversation(id: string | null, messages: ChatMessage[]): void {
  if (!id || messages.length === 0) return;
  const list = listConversations();
  const existing = list.find((c) => c.id === id);
  const entry: StoredConversation = {
    id,
    title: existing ? existing.title : deriveTitle(messages),
    messages,
    updatedAt: Date.now(),
  };
  write([entry, ...list.filter((c) => c.id !== id)]);
}

export function removeConversation(id: string): StoredConversation[] {
  const next = listConversations().filter((c) => c.id !== id);
  write(next);
  return next;
}
