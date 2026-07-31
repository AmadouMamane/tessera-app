"use client";

import { Plus } from "lucide-react";
import { useState } from "react";

import { proposeAgent } from "@/lib/api/client";

/**
 * Governed "+ Nouvel agent" action. An agent is a package approved as a unit
 * (ADR 0012), so this is not a runtime create: it records an audited proposal
 * (S1 event) feeding the propose -> review -> release flow. Rendered only for
 * operators (RBAC gated by the server page).
 */
export function NewAgentButton() {
  const [state, setState] = useState<"idle" | "pending" | "done" | "error">("idle");

  async function onClick() {
    const name = window.prompt("Nom du nouvel agent à proposer ?")?.trim();
    if (!name) return;
    setState("pending");
    try {
      await proposeAgent(name);
      setState("done");
    } catch {
      setState("error");
    }
  }

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={onClick}
        disabled={state === "pending"}
        className="flex h-9 items-center gap-2 rounded-md border border-[#7c5cf5] bg-[#6d4aed] px-3 text-xs font-medium text-white hover:bg-[#7c5cf5] disabled:opacity-60"
      >
        <Plus className="h-4 w-4" /> Nouvel agent
      </button>
      {state === "done" ? (
        <span className="text-[0.72rem] text-[var(--tessera-fg-success)]">
          Proposition enregistrée (revue requise)
        </span>
      ) : null}
      {state === "error" ? (
        <span className="text-[0.72rem] text-[var(--tessera-fg-danger)]">
          Échec de la proposition
        </span>
      ) : null}
    </div>
  );
}
