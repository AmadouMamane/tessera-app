"use client";

import {
  AlertTriangle,
  BadgeCheck,
  CheckCircle2,
  Copy,
  FileText,
  GitBranch,
  ListChecks,
  ShieldCheck,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type {
  BusinessEvent,
  BusinessScore,
  RecouvrementRun,
  RecouvrementRunArtifact,
  RecouvrementRunsResponse,
  RecouvrementSensitiveAction,
} from "@/lib/api/schemas";
import { artifactStatusMeta } from "@/lib/recouvrement/artifact-status";

type BadgeTone = "neutral" | "gold" | "success" | "warning" | "danger" | "info" | "navy";

const SCORE_ORDER = [
  "contact_window_compliance",
  "action_blocking_correctness",
  "artifact_governance",
  "validation_required_compliance",
  "client_message_safety",
  "payment_option_safety",
  "action_governance",
  "no_uncontrolled_external_effect",
  "recouvrement_trace_completeness",
  "amount_consistency",
];

const IMPORTANT_EVENTS = new Set([
  "intent.routed",
  "slots.extracted",
  "business_rule.checked",
  "policy.decision_made",
  "artifact.created",
  "artifact.status_changed",
  "validation.requested",
  "action.prepared",
  "action.blocked",
  "message.generated",
]);

const ID_LABELS = new Set(["Conversation", "Tour"]);

function valueLabel(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "oui" : "non";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  if (Array.isArray(value)) return value.map(valueLabel).join(", ");
  return String(value);
}

function scoreLabel(score: BusinessScore): string {
  if (typeof score.score === "number") return `${Math.round(score.score * 100)}%`;
  return "—";
}

function scoreTone(score: BusinessScore): BadgeTone {
  if (typeof score.score !== "number") return "neutral";
  if (score.score >= 1) return "success";
  if (score.score <= 0) return "warning";
  return "info";
}

function scoreReasonLabel(score: BusinessScore): string {
  if (score.status === "not_applicable") return "aucune règle applicable";
  if (score.status === "unknown") return "pas encore mesuré";
  const labels: Record<string, string> = {
    action_artifact_missing: "action sans artefact lié",
    action_missing_no_external_effect_flag: "flag effet externe absent",
    artifact_actions_traceable: "actions traçables",
    no_external_effect_preserved: "effet externe maîtrisé",
    sensitive_artifacts_traceable: "artefacts traçables",
    validation_requested_pending_or_declared: "validation tracée",
  };
  return labels[score.reason] ?? score.reason.replaceAll("_", " ");
}

function shortId(value: string | null | undefined): string {
  if (!value) return "—";
  return value.length <= 8 ? value : value.slice(0, 8);
}

function copyValue(value: string | null | undefined) {
  if (!value || typeof navigator === "undefined") return;
  void navigator.clipboard?.writeText(value);
}

function relativeTime(value: string | null | undefined): string {
  if (!value) return "date inconnue";
  const stamp = Date.parse(value);
  if (Number.isNaN(stamp)) return "date inconnue";
  const minutes = Math.max(0, Math.round((Date.now() - stamp) / 60_000));
  if (minutes < 1) return "à l'instant";
  if (minutes < 60) return `il y a ${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `il y a ${hours} h`;
  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(stamp));
}

function uniqueCodes(codes: string[]): string[] {
  return Array.from(new Set(codes.filter(Boolean).map((code) => code.toUpperCase())));
}

function codeLabel(code: string): string {
  const labels: Record<string, string> = {
    AMOUNT_CONSISTENT: "Montant cohérent",
    CLIENT_AGREEMENT_REQUIRED: "Accord client requis",
    MESSAGE_NOT_SENT: "Aucun message envoyé",
    MESSAGE_SAFE: "Message sûr",
    NO_EXTERNAL_EFFECT: "Aucun effet externe",
    OUTSIDE_CONTACT_WINDOW: "Hors fenêtre de contact",
    PAYMENT_LINK_NOT_CREATED: "Lien de paiement non créé",
    PAYMENT_LINK_NOT_SENT: "Lien de paiement non envoyé",
    PAYMENT_NOT_INITIATED: "Paiement non initié",
    SCHEDULE_NOT_CREATED: "Aucun échéancier créé",
    SNAPSHOT_ONLY: "Instantané uniquement",
    UNAUTHORIZED_SURFACE: "Surface non autorisée",
    VALIDATION_REQUIRED: "Validation interne requise",
  };
  return labels[code] ?? code.replaceAll("_", " ").toLowerCase();
}

function eventTone(event: BusinessEvent): string {
  if (event.event_name === "action.blocked" || event.decision === "blocked") {
    return "border-red-500/35 bg-red-500/10 text-red-200";
  }
  if (
    event.event_name === "validation.requested" ||
    event.decision === "validation_required" ||
    event.artifact_status === "pending_validation"
  ) {
    return "border-amber-400/35 bg-amber-400/10 text-amber-100";
  }
  if (event.event_name.includes("artifact") || event.event_name.includes("message")) {
    return "border-sky-400/30 bg-sky-400/10 text-sky-100";
  }
  return "border-[var(--tessera-border)] bg-[var(--tessera-surface)] text-[var(--tessera-text)]";
}

function actionLabel(action: string | null | undefined): string {
  if (!action) return "Action";
  const labels: Record<string, string> = {
    insert_artifact_in_case: "Insérer dans le dossier",
    prepare_client_message: "Préparer le message client",
    prepare_outbound_call: "Préparer un appel sortant",
    prepare_reminder_tomorrow: "Planifier un rappel demain",
    prepare_schedule_proposal: "Préparer l'échéancier",
    submit_for_validation: "Soumettre à validation",
  };
  return labels[action] ?? action.replaceAll("_", " ");
}

function runTitle(run: RecouvrementRun): string {
  const artifact = run.artifacts[0];
  if (artifact?.artifact_type === "contact_rule_v1") return "Règle de contact";
  if (artifact?.artifact_type === "schedule_proposal_v2") return "Échéancier indicatif";
  if (artifact?.artifact_type === "client_message_artifact") return "Message client";
  if (artifact?.artifact_type === "reminder_draft_v1") return "Brouillon de relance";
  if (artifact?.artifact_type === "case_summary_v1") return "Résumé du dossier";
  if (artifact?.artifact_type === "payment_options_v1") return "Options de paiement";
  if (run.sensitive_actions[0]?.action_name)
    return actionLabel(run.sensitive_actions[0].action_name);
  return "Exécution métier";
}

function runHeading(run: RecouvrementRun): string {
  return `${runTitle(run)} · ${run.case_id ?? "dossier"} · ${relativeTime(run.started_at)}`;
}

function scoreSort(a: BusinessScore, b: BusinessScore): number {
  const ai = SCORE_ORDER.indexOf(a.metric);
  const bi = SCORE_ORDER.indexOf(b.metric);
  return (ai === -1 ? SCORE_ORDER.length : ai) - (bi === -1 ? SCORE_ORDER.length : bi);
}

/**
 * Generic workflow-runs panel (ADR 0017 Phase A) — renders ANY agent's business runs
 * from the ADR 0016 envelope + grammar. Agent-specific copy comes in through props;
 * the schema type names still say "Recouvrement" transitionally (renamed with the
 * Phase C dissolution of the hardcoded tab).
 */
export function WorkflowRunsPanel({
  data,
  loading,
  title = "Exécutions métier",
  loadingLabel = "Chargement des exécutions métier...",
  emptyTitle = "Aucune exécution métier observée",
  emptyHint = "Lancez un tour dans la surface produit de l'agent pour voir apparaître les faits métier, artefacts, scores et actions gouvernées.",
}: {
  data: RecouvrementRunsResponse | undefined;
  loading: boolean;
  title?: string;
  loadingLabel?: string;
  emptyTitle?: string;
  emptyHint?: string;
}) {
  const runs = data?.runs ?? [];
  const [selectedTurnId, setSelectedTurnId] = useState<string | null>(null);
  const selected = runs.find((run) => run.turn_id === selectedTurnId) ?? runs[0] ?? null;

  if (loading && runs.length === 0) {
    return (
      <Card>
        <CardContent className="flex min-h-[220px] items-center justify-center text-sm text-[var(--tessera-text-muted)]">
          {loadingLabel}
        </CardContent>
      </Card>
    );
  }

  if (!selected) {
    return (
      <Card>
        <CardContent className="flex min-h-[260px] flex-col items-center justify-center gap-2 text-center">
          <ShieldCheck className="h-7 w-7 text-[var(--tessera-green)]" />
          <p className="text-sm font-semibold">{emptyTitle}</p>
          <p className="max-w-[34rem] text-xs text-[var(--tessera-text-muted)]">{emptyHint}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <section className="flex min-w-0 flex-col gap-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <GitBranch className="h-4 w-4 shrink-0 text-[var(--tessera-green)]" />
          <h2 className="text-sm font-semibold">{title}</h2>
        </div>
        <Badge tone="neutral">{runs.length} runs</Badge>
      </div>

      <div className="grid min-w-0 gap-2.5 lg:grid-cols-[260px_minmax(0,1fr)]">
        <RunsList runs={runs} selected={selected} onSelect={setSelectedTurnId} />

        <div className="flex min-w-0 flex-col gap-2.5">
          <RunContext run={selected} />
          <TimelinePanel run={selected} />
        </div>
      </div>

      <div className="grid min-w-0 gap-2.5 md:grid-cols-2 xl:grid-cols-4">
        <ArtifactsPanel artifacts={selected.artifacts} />
        <DecisionPanel run={selected} />
        <SensitiveActionsPanel run={selected} />
        <ScoresPanel scores={selected.scores} />
      </div>
    </section>
  );
}

function RunsList({
  runs,
  selected,
  onSelect,
}: {
  runs: RecouvrementRun[];
  selected: RecouvrementRun;
  onSelect: (turnId: string) => void;
}) {
  return (
    <Card className="min-w-0">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          Runs <span className="text-[var(--tessera-text-muted)]">↕</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex max-h-[620px] flex-col gap-1.5 overflow-y-auto">
        {runs.map((run) => (
          <div
            key={run.turn_id}
            className={`rounded-lg border px-2.5 py-2 text-left transition-colors ${
              run.turn_id === selected.turn_id
                ? "border-[var(--tessera-green)]/60 bg-[var(--tessera-green)]/10"
                : "border-[var(--tessera-border)] bg-[var(--tessera-surface)]/40 hover:bg-[var(--tessera-muted)]"
            }`}
          >
            <button
              type="button"
              className="block w-full text-left"
              onClick={() => onSelect(run.turn_id)}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="min-w-0 text-[0.76rem] font-semibold leading-snug">
                  {runHeading(run)}
                </span>
                <span className="rounded bg-[var(--tessera-bg)] px-1.5 py-0.5 font-mono text-[0.58rem] text-[var(--tessera-text-muted)]">
                  {run.event_count}
                </span>
              </div>
            </button>
            <IdChip value={run.turn_id} className="mt-1" />
            <div className="mt-1 flex flex-wrap gap-1">
              {uniqueCodes(run.decisions.flatMap((decision) => decision.reason_codes))
                .slice(0, 2)
                .map((reason) => (
                  <CodeBadge key={reason} code={reason} />
                ))}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function RunContext({ run }: { run: RecouvrementRun }) {
  const sensitiveActions = run.sensitive_actions ?? [];
  const contextFields: { label: string; value: unknown }[] = [
    { label: "Agent", value: run.agent_id },
    { label: "Parcours", value: run.workflow_id },
    { label: "Surface", value: run.surface },
    { label: "Dossier", value: run.case_id },
    { label: "Conversation", value: run.conversation_id },
    { label: "Tour", value: run.turn_id },
  ];
  const hasUnsafeExternalEffect = sensitiveActions.some(
    (action) => action.no_external_effect === false,
  );
  const allSensitiveActionsSafe =
    sensitiveActions.length > 0 &&
    sensitiveActions.every((action) => action.no_external_effect === true);
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span>Contexte de l'exécution</span>
          <Badge
            tone={
              hasUnsafeExternalEffect ? "danger" : allSensitiveActionsSafe ? "success" : "neutral"
            }
          >
            {hasUnsafeExternalEffect
              ? "Effet externe détecté"
              : allSensitiveActionsSafe
                ? "Effets externes contrôlés"
                : "Observation"}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-2 text-[0.72rem] sm:grid-cols-2 xl:grid-cols-6">
        {contextFields.map(({ label, value }) => (
          <ContextFact key={label} label={label} value={value} />
        ))}
      </CardContent>
    </Card>
  );
}

function TimelinePanel({ run }: { run: RecouvrementRun }) {
  const events = run.timeline.filter((event) => IMPORTANT_EVENTS.has(event.event_name));
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <ListChecks className="h-4 w-4 text-sky-300" />
          Chronologie métier
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-1.5">
        {events.length === 0 ? (
          <p className="text-xs text-[var(--tessera-text-muted)]">Aucun événement clé.</p>
        ) : (
          events.map((event) => (
            <div
              key={`${event.event_name}-${event.timestamp}-${event.node_name}`}
              className={`rounded-lg border px-2.5 py-2 ${eventTone(event)}`}
            >
              <div className="grid gap-0.5">
                <span className="font-mono text-[0.68rem] font-semibold leading-snug">
                  {event.event_name}
                </span>
                <span className="font-mono text-[0.58rem] opacity-70">
                  {event.node_name ?? "node"}
                </span>
              </div>
              <div className="mt-1 flex flex-wrap gap-1">
                {event.decision ? <Badge tone="neutral">{event.decision}</Badge> : null}
                {uniqueCodes(event.reason_codes)
                  .slice(0, 4)
                  .map((reason) => (
                    <CodeBadge key={reason} code={reason} />
                  ))}
                {event.artifact_status ? (
                  <Badge tone="neutral">{event.artifact_status}</Badge>
                ) : null}
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function ArtifactsPanel({ artifacts }: { artifacts: RecouvrementRunArtifact[] }) {
  const tArtifactStatus = useTranslations("artifactStatus");
  return (
    <Card className="min-w-0">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <FileText className="h-4 w-4 text-amber-300" />
          Artefacts
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-1.5">
        {artifacts.length === 0 ? (
          <p className="text-xs text-[var(--tessera-text-muted)]">Aucun artefact typé.</p>
        ) : (
          artifacts.map((artifact) => (
            <ArtifactCard
              key={artifact.artifact_id}
              artifact={artifact}
              tArtifactStatus={tArtifactStatus}
            />
          ))
        )}
      </CardContent>
    </Card>
  );
}

function ArtifactCard({
  artifact,
  tArtifactStatus,
}: {
  artifact: RecouvrementRunArtifact;
  tArtifactStatus: ReturnType<typeof useTranslations>;
}) {
  const statusMeta = artifactStatusMeta(artifact.artifact_status);
  const statusLabel = tArtifactStatus.has(statusMeta.messageKey)
    ? tArtifactStatus(statusMeta.messageKey)
    : statusMeta.label;
  return (
    <div className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]/45 p-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[0.74rem] font-semibold leading-snug">
          {artifact.title ?? artifact.artifact_type}
        </span>
        <Badge tone={statusMeta.tone}>{statusLabel}</Badge>
      </div>
      <IdChip value={artifact.artifact_id} className="mt-1" />
      <div className="mt-2 grid gap-1.5 text-[0.66rem]">
        <Fact label="Type" value={artifact.artifact_type} />
        <Fact label="Generation" value={artifact.generation_mode} />
        <Fact label="Template" value={artifact.template_id} />
        <Fact label="Version" value={artifact.template_version} />
        <SafetyFact label="Message envoyé" flag={artifact.no_message_sent} />
        <SafetyFact label="Paiement initié" flag={artifact.no_payment_initiated} />
        <SafetyFact label="Lien paiement créé" flag={artifact.no_payment_link_created} />
        <SafetyFact label="Lien paiement envoyé" flag={artifact.no_payment_link_sent} />
        <SafetyFact label="Échéancier créé" flag={artifact.no_schedule_created} />
        <SafetyFact
          label="Effet externe"
          flag={artifact.no_external_effect}
          trueLabel="aucun"
          falseLabel="réel"
        />
      </div>
    </div>
  );
}

function DecisionPanel({ run }: { run: RecouvrementRun }) {
  return (
    <Card className="min-w-0">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <ShieldCheck className="h-4 w-4 text-[var(--tessera-green)]" />
          Décisions
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-1.5">
        {run.decisions.length === 0 ? (
          <p className="text-xs text-[var(--tessera-text-muted)]">Aucune décision.</p>
        ) : (
          run.decisions.map((decision) => (
            <div
              key={`${decision.event_name}-${decision.decision}-${decision.rule_id}`}
              className="rounded-lg border border-[var(--tessera-border)] p-2 text-[0.68rem]"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold">{decision.decision ?? decision.event_name}</span>
                <EffectBadge flag={decision.no_external_effect} />
              </div>
              <div className="mt-1 flex flex-wrap gap-1">
                {decision.rule_id ? <CodeBadge code={decision.rule_id} /> : null}
                {decision.action_name ? (
                  <Badge tone="neutral">{actionLabel(decision.action_name)}</Badge>
                ) : null}
                {uniqueCodes(decision.reason_codes).map((reason) => (
                  <CodeBadge key={reason} code={reason} />
                ))}
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function SensitiveActionsPanel({ run }: { run: RecouvrementRun }) {
  return (
    <Card className="min-w-0">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <AlertTriangle className="h-4 w-4 text-amber-300" />
          Actions sensibles
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-1.5">
        {run.sensitive_actions.length === 0 ? (
          <p className="text-xs text-[var(--tessera-text-muted)]">Aucune action sensible.</p>
        ) : (
          run.sensitive_actions.map((action) => (
            <SensitiveActionCard key={actionKey(action)} action={action} />
          ))
        )}
      </CardContent>
    </Card>
  );
}

function SensitiveActionCard({ action }: { action: RecouvrementSensitiveAction }) {
  return (
    <div className="rounded-lg border border-[var(--tessera-border)] p-2 text-[0.68rem]">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold">{actionLabel(action.action_name)}</span>
        <EffectBadge flag={action.no_external_effect} />
      </div>
      <div className="mt-1 grid gap-1">
        <Fact
          label="Artefact"
          value={shortId(action.artifact_id)}
          title={action.artifact_id ?? undefined}
        />
        <Fact label="Statut cible" value={action.target_status} />
        <SafetyFact
          label="Validation"
          flag={action.requires_validation}
          trueLabel="requise"
          falseLabel="non requise"
        />
      </div>
      <div className="mt-1 flex flex-wrap gap-1">
        {uniqueCodes(action.reason_codes).map((reason) => (
          <CodeBadge key={reason} code={reason} />
        ))}
      </div>
    </div>
  );
}

function ScoresPanel({ scores }: { scores: BusinessScore[] }) {
  const tSignal = useTranslations("businessSignal");
  const ordered = [...scores].sort(scoreSort);
  return (
    <Card className="min-w-0">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <BadgeCheck className="h-4 w-4 text-sky-300" />
          Scores métier
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-1.5">
        {ordered.map((score) => {
          const label = tSignal.has(score.metric) ? tSignal(score.metric) : score.metric;
          return (
            <div
              key={score.metric}
              className="rounded-lg border border-[var(--tessera-border)] px-2.5 py-2 text-[0.68rem]"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="min-w-0 font-medium leading-snug">{label}</span>
                <span className="inline-flex items-center gap-1 font-mono">
                  {score.score === 1 ? (
                    <CheckCircle2 className="h-3 w-3 text-[var(--tessera-green)]" />
                  ) : null}
                  <Badge tone={scoreTone(score)}>{scoreLabel(score)}</Badge>
                </span>
              </div>
              <p className="mt-1 text-[0.6rem] leading-snug text-[var(--tessera-text-muted)]">
                {scoreReasonLabel(score)}
              </p>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

function actionKey(action: RecouvrementSensitiveAction): string {
  return `${action.event_name}-${action.action_name}-${action.artifact_id}-${action.target_status}`;
}

function Fact({
  label,
  value,
  title,
}: {
  label: string;
  value: unknown;
  title?: string;
}) {
  return (
    <div className="flex items-start justify-between gap-2">
      <span className="shrink-0 text-[var(--tessera-text-muted)]">{label}</span>
      <span className="min-w-0 break-words text-right font-mono" title={title}>
        {valueLabel(value)}
      </span>
    </div>
  );
}

function ContextFact({ label, value }: { label: string; value: unknown }) {
  const raw = value == null ? "" : String(value);
  const display = ID_LABELS.has(label) ? shortId(raw) : valueLabel(value);
  return (
    <div className="min-w-0 rounded-md border border-[var(--tessera-border)]/60 bg-[var(--tessera-bg)]/30 px-2 py-1.5">
      <span className="block text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
        {label}
      </span>
      <span className="mt-0.5 flex min-w-0 items-center gap-1 font-mono text-[0.68rem]" title={raw}>
        <span className="min-w-0 break-words">{display}</span>
        {ID_LABELS.has(label) && raw ? (
          <button
            type="button"
            title="Copier l'identifiant complet"
            className="rounded p-0.5 text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]"
            onClick={() => copyValue(raw)}
          >
            <Copy className="h-3 w-3" />
          </button>
        ) : null}
      </span>
    </div>
  );
}

function IdChip({
  value,
  className = "",
}: { value: string | null | undefined; className?: string }) {
  if (!value) return null;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded bg-[var(--tessera-bg)] px-1.5 py-0.5 font-mono text-[0.58rem] text-[var(--tessera-text-muted)] ${className}`}
      title={value}
    >
      {shortId(value)}
      <button
        type="button"
        title="Copier l'identifiant complet"
        className="rounded p-0.5 hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]"
        onClick={(event) => {
          event.stopPropagation();
          copyValue(value);
        }}
      >
        <Copy className="h-3 w-3" />
      </button>
    </span>
  );
}

function CodeBadge({ code }: { code: string }) {
  const normalized = code.toUpperCase();
  const dangerous = normalized.includes("UNAUTHORIZED") || normalized.includes("UNSAFE");
  return (
    <Badge
      tone={dangerous ? "danger" : "neutral"}
      className="font-mono text-[0.56rem]"
      title={codeLabel(normalized)}
    >
      {normalized}
    </Badge>
  );
}

function SafetyFact({
  label,
  flag,
  trueLabel = "non",
  falseLabel = "oui",
}: {
  label: string;
  flag: boolean | null | undefined;
  trueLabel?: string;
  falseLabel?: string;
}) {
  const badge =
    flag === true ? (
      <Badge tone="success">{trueLabel}</Badge>
    ) : flag === false ? (
      <Badge tone="danger">{falseLabel}</Badge>
    ) : (
      <Badge tone="neutral">—</Badge>
    );
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="min-w-0 text-[var(--tessera-text-muted)]">{label}</span>
      {badge}
    </div>
  );
}

function EffectBadge({ flag }: { flag: boolean | null | undefined }) {
  if (flag === true) return <Badge tone="success">Effets externes contrôlés</Badge>;
  if (flag === false) return <Badge tone="danger">Effet externe réel</Badge>;
  return null;
}
