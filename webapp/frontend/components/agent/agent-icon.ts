import { Banknote, Bot, Headset, type LucideIcon, UserPlus } from "lucide-react";

/**
 * The single agent-icon system. One recognisable glyph per agent (so an agent is
 * identifiable at a glance), but from ONE library with an identical treatment —
 * line style, weight, size and colour are set uniformly by the caller, never
 * per agent. Differentiate agents by the GLYPH, never by style; a status is never
 * encoded here (use status chips). Unknown agents fall back to a neutral mark.
 */
const AGENT_GLYPH: Record<string, LucideIcon> = {
  "support-client": Headset,
  onboarding: UserPlus,
  recouvrement: Banknote,
};

/** The lucide glyph identifying `agentId` (neutral `Bot` fallback). */
export function agentIcon(agentId: string): LucideIcon {
  return AGENT_GLYPH[agentId] ?? Bot;
}
