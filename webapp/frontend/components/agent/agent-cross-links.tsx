"use client";

import type { Route } from "next";

import { Link } from "@/i18n/navigation";
import { agentPath } from "@/lib/agent-context";
import { useAgentId } from "@/lib/use-agent-id";

/**
 * P3 — "Liens utiles" cross-links for an AGENT instance page.
 *
 * Makes the control plane navigable + opposable: each instance page links its
 * **definition** (→ CONFIGURER catalogue), its **governance** (→ AGIR Release
 * Control), and its **linked data** (other AGENT surfaces). Presets per page keep
 * the links page-appropriate; all targets are real, deep-linkable routes.
 */
type AgentLinkPage =
  | "configurations"
  | "garde-fous"
  | "prompts"
  | "connaissances"
  | "console"
  | "historique";

const PRESETS: Record<
  AgentLinkPage,
  { configurer: { href: string; label: string }; data?: AgentLinkPage[] }
> = {
  configurations: {
    configurer: { href: "/configurer/parametres", label: "Définition · paramètres (CONFIGURER)" },
    data: ["prompts", "garde-fous"],
  },
  "garde-fous": {
    configurer: { href: "/configurer/garde-fous", label: "Définition · garde-fous (CONFIGURER)" },
    data: ["connaissances"],
  },
  prompts: {
    configurer: { href: "/configurer/parametres", label: "Définition · prompts (CONFIGURER)" },
    data: ["configurations"],
  },
  connaissances: {
    configurer: {
      href: "/configurer/sources-memoire",
      label: "Définition · sources & mémoire (CONFIGURER)",
    },
    data: ["garde-fous"],
  },
  console: {
    configurer: { href: "/configurer/modeles", label: "Définition · modèle (CONFIGURER)" },
    data: ["prompts"],
  },
  historique: {
    configurer: { href: "/configurer/parametres", label: "Définition · paramètres (CONFIGURER)" },
    data: ["console"],
  },
};

const DATA_LABEL: Record<AgentLinkPage, string> = {
  configurations: "Configurations",
  "garde-fous": "Garde-fous appliqués",
  prompts: "Prompts",
  connaissances: "Connaissances liées",
  console: "Console",
  historique: "Historique",
};

export function AgentCrossLinks({ page }: { page: AgentLinkPage }) {
  const agentId = useAgentId();
  const preset = PRESETS[page];
  const items: { href: Route; label: string }[] = [
    {
      href: `/agir/release-control?agent=${agentId}` as Route,
      label: "Gouvernance · Release Control",
    },
    { href: preset.configurer.href as Route, label: preset.configurer.label },
    ...(preset.data ?? []).map((d) => ({
      href: agentPath(agentId, d) as Route,
      label: DATA_LABEL[d],
    })),
  ];
  return (
    <section className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2">
      <span className="text-[10px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
        Liens utiles
      </span>
      {items.map((it) => (
        <Link
          key={it.label}
          href={it.href}
          className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface-2)] px-2 py-1 text-[11px] text-[var(--tessera-text)] transition-colors hover:border-[#7c5cf5]/50 hover:text-white"
        >
          {it.label} →
        </Link>
      ))}
    </section>
  );
}
