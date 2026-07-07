export type ArtifactStatusTone = "neutral" | "info" | "warning" | "success" | "danger";

export interface ArtifactStatusMeta {
  label: string;
  tone: ArtifactStatusTone;
}

/**
 * Canonical French label + tone per backend artifact status (shared by the
 * Recouvrement drawer and the Cockpit business-run view so both surfaces use
 * the same words and colors). `insertion_prepared`/`reminder_prepared` are
 * proposal-stage states — distinct from the `inserted`/`executed` terminal
 * states recognised by src/tessera/recouvrement/scoring.py — never collapse
 * the two: doing so would visually claim a proposal has already executed.
 */
const ARTIFACT_STATUS_LABELS: Record<string, ArtifactStatusMeta> = {
  draft: { label: "Brouillon", tone: "neutral" },
  ready: { label: "Prêt", tone: "neutral" },
  indicatif: { label: "Proposition indicative", tone: "info" },
  insertion_prepared: { label: "Insertion proposée", tone: "info" },
  pending_validation: { label: "Soumis à validation", tone: "warning" },
  reminder_prepared: { label: "Rappel proposé", tone: "info" },
  unavailable: { label: "Vérification indisponible", tone: "warning" },
  blocked: { label: "Action bloquée", tone: "danger" },
  inserted: { label: "Inséré dans le dossier", tone: "success" },
  executed: { label: "Planifié", tone: "success" },
};

export function artifactStatusMeta(status?: string | null): ArtifactStatusMeta {
  if (!status) return { label: "—", tone: "neutral" };
  return ARTIFACT_STATUS_LABELS[status] ?? { label: status, tone: "neutral" };
}
