export type ArtifactStatusTone = "neutral" | "info" | "warning" | "success" | "danger";

export interface ArtifactStatusMeta {
  label: string;
  labelKey: `artifactStatus.${string}`;
  messageKey: string;
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
  draft: {
    label: "Brouillon",
    labelKey: "artifactStatus.draft",
    messageKey: "draft",
    tone: "neutral",
  },
  ready: { label: "Prêt", labelKey: "artifactStatus.ready", messageKey: "ready", tone: "neutral" },
  indicatif: {
    label: "Proposition indicative",
    labelKey: "artifactStatus.indicatif",
    messageKey: "indicatif",
    tone: "info",
  },
  insertion_prepared: {
    label: "Insertion proposée",
    labelKey: "artifactStatus.insertion_prepared",
    messageKey: "insertion_prepared",
    tone: "info",
  },
  pending_validation: {
    label: "Soumis à validation",
    labelKey: "artifactStatus.pending_validation",
    messageKey: "pending_validation",
    tone: "warning",
  },
  reminder_prepared: {
    label: "Rappel proposé",
    labelKey: "artifactStatus.reminder_prepared",
    messageKey: "reminder_prepared",
    tone: "info",
  },
  unavailable: {
    label: "Vérification indisponible",
    labelKey: "artifactStatus.unavailable",
    messageKey: "unavailable",
    tone: "warning",
  },
  blocked: {
    label: "Action bloquée",
    labelKey: "artifactStatus.blocked",
    messageKey: "blocked",
    tone: "danger",
  },
  inserted: {
    label: "Inséré dans le dossier",
    labelKey: "artifactStatus.inserted",
    messageKey: "inserted",
    tone: "success",
  },
  executed: {
    label: "Planifié (interne)",
    labelKey: "artifactStatus.executed",
    messageKey: "executed",
    tone: "success",
  },
};

export function artifactStatusMeta(status?: string | null): ArtifactStatusMeta {
  if (!status)
    return {
      label: "—",
      labelKey: "artifactStatus.unknown",
      messageKey: "unknown",
      tone: "neutral",
    };
  return (
    ARTIFACT_STATUS_LABELS[status] ?? {
      label: status,
      labelKey: "artifactStatus.unknown",
      messageKey: "unknown",
      tone: "neutral",
    }
  );
}
