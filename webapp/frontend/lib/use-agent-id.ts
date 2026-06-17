"use client";

import { useParams } from "next/navigation";

import { DEFAULT_AGENT_ID } from "@/lib/agent-context";

/**
 * Read the active agent id from the route (`/agents/[agentId]/...`).
 *
 * Falls back to {@link DEFAULT_AGENT_ID} when rendered outside the AGENT
 * section (e.g. shared chrome like the sidebar), so callers never need to
 * special-case it. Client-only: call it from client components.
 */
export function useAgentId(): string {
  const params = useParams();
  const raw = params?.agentId;
  const value = Array.isArray(raw) ? raw[0] : raw;
  return value ?? DEFAULT_AGENT_ID;
}
