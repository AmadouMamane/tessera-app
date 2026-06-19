"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";

import { usePathname } from "@/i18n/navigation";
import { fetchFleet } from "@/lib/api/client";

/**
 * Global breadcrumb (P1) — `SUPER › Section › Page`, derived from the route and
 * rendered once by the AppShell so every cockpit page carries the same fil
 * d'Ariane. Pure presentation labels (not data): a static segment→label map keyed
 * by the URL, so the trail is deep-link-consistent with the active page.
 */

// First path segment → its super-section + section label.
const SECTION: Record<string, { super: string; label: string }> = {
  agents: { super: "AGENT", label: "Flotte" },
  agent: { super: "AGENT", label: "Agent" },
  "a-traiter": { super: "AGENT", label: "À traiter" },
  "a-faire": { super: "AGENT", label: "À faire" },
  surveiller: { super: "GOUVERNER", label: "Surveiller" },
  agir: { super: "GOUVERNER", label: "Agir" },
  prouver: { super: "GOUVERNER", label: "Prouver" },
  configurer: { super: "PLATEFORME", label: "Configurer" },
  admin: { super: "PLATEFORME", label: "Admin" },
};

// Leaf slug → page label (presentation only).
const PAGE: Record<string, string> = {
  synthese: "Synthèse",
  configurations: "Configurations",
  connaissances: "Connaissances",
  "garde-fous": "Garde-fous",
  prompts: "Prompts",
  evaluations: "Évaluations",
  console: "Console",
  historique: "Historique",
  "vue-ensemble": "Vue d'ensemble",
  "qualite-ia": "Qualité IA",
  "securite-privacy": "Sécurité & privacy",
  conformite: "Conformité",
  "fiabilite-cout": "Fiabilité & coût",
  observabilite: "Observabilité",
  amelioration: "Amélioration",
  "incidents-playbooks": "Incidents & playbooks",
  "replay-shadow": "Replay & shadow",
  "curation-eval-set": "Curation eval set",
  "release-control": "Release Control",
  automations: "Automations",
  "audit-logs": "Journal d'audit",
  "evidence-store": "Coffre de preuves",
  "signal-catalog": "Catalogue de signaux",
  modeles: "Modèles",
  connecteurs: "Connecteurs",
  politiques: "Politiques",
  "sources-memoire": "Sources & mémoire",
  parametres: "Paramètres",
  integrations: "Intégrations",
  utilisateurs: "Utilisateurs",
  "roles-acces": "Rôles & accès",
  "profil-systeme": "Profil système",
};

export function AppBreadcrumb() {
  const pathname = usePathname();
  const segs = pathname.split("/").filter(Boolean);
  const first = segs[0];
  const isAgentSub = first === "agents" && segs.length > 1;
  // Resolve the real agent name from the registry for an agent sub-page, so the
  // trail reads "AGENT › Support Client › …" — never the literal "Agent" or slug.
  const { data: fleet } = useQuery({
    queryKey: ["fleet-switcher"],
    queryFn: ({ signal }) => fetchFleet(signal),
    staleTime: 60_000,
    enabled: isAgentSub,
  });
  if (!first || !SECTION[first]) return null;
  const section = SECTION[first];
  const agentName = isAgentSub
    ? (fleet?.agents?.find((a) => a.id === segs[1])?.name ?? segs[1])
    : undefined;
  const sectionLabel = agentName ?? section.label;
  const leaf = segs[segs.length - 1];
  const pageLabel = leaf && leaf !== first ? PAGE[leaf] : undefined;

  return (
    <nav
      aria-label="breadcrumb"
      className="mb-2 flex flex-wrap items-center gap-1 text-[0.62rem] text-[var(--tessera-text-muted)]"
    >
      <span className="font-semibold uppercase tracking-wide">{section.super}</span>
      <ChevronRight className="h-3 w-3" />
      <span>{sectionLabel}</span>
      {pageLabel ? (
        <>
          <ChevronRight className="h-3 w-3" />
          <span className="text-[var(--tessera-text)]">{pageLabel}</span>
        </>
      ) : null}
    </nav>
  );
}
