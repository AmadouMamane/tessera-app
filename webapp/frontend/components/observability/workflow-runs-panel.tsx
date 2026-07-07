"use client";

import {
  AlertTriangle,
  BadgeCheck,
  CheckCircle2,
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
  RecouvrementRunsResponse,
} from "@/lib/api/schemas";
import { artifactStatusMeta } from "@/lib/recouvrement/artifact-status";

const SCORE_ORDER = [
  "contact_window_compliance",
  "action_blocking_correctness",
  "artifact_governance",
  "validation_required_compliance",
  "client_message_safety",
  "payment_option_safety",
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

function valueLabel(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "oui" : "non";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  if (Array.isArray(value)) return value.map(valueLabel).join(", ");
  return String(value);
}

function scoreLabel(score: BusinessScore): string {
  if (typeof score.score === "number") return `${Math.round(score.score * 100)}%`;
  return score.status;
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

function actionLabel(action: string): string {
  const labels: Record<string, string> = {
    submit_for_validation: "Soumettre à validation",
    insert_artifact_in_case: "Insérer dans le dossier",
    prepare_reminder_tomorrow: "Planifier un rappel demain",
    prepare_client_message: "Préparer le message client",
    prepare_schedule_proposal: "Préparer l'échéancier",
    prepare_outbound_call: "Préparer un appel sortant",
  };
  return labels[action] ?? action;
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
  return run.turn_id;
}

function scoreSort(a: BusinessScore, b: BusinessScore): number {
  return SCORE_ORDER.indexOf(a.metric) - SCORE_ORDER.indexOf(b.metric);
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
  const tArtifactStatus = useTranslations("artifactStatus");
  const [selectedTurnId, setSelectedTurnId] = useState<string | null>(null);
  const selected = runs.find((run) => run.turn_id === selectedTurnId) ?? runs[0] ?? null;
  const sensitiveActions = selected?.sensitive_actions ?? [];
  const hasUnsafeExternalEffect = sensitiveActions.some(
    (action) => action.no_external_effect === false,
  );
  const allSensitiveActionsSafe =
    sensitiveActions.length > 0 &&
    sensitiveActions.every((action) => action.no_external_effect === true);

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
    <div className="grid min-w-0 gap-2 2xl:grid-cols-[300px_minmax(0,1fr)]">
      <Card className="min-w-0">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <GitBranch className="h-4 w-4 text-[var(--tessera-green)]" />
            {title}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex max-h-[650px] flex-col gap-1.5 overflow-y-auto">
          {runs.map((run) => (
            <button
              key={run.turn_id}
              type="button"
              onClick={() => setSelectedTurnId(run.turn_id)}
              className={`rounded-lg border px-2.5 py-2 text-left transition-colors ${
                run.turn_id === selected.turn_id
                  ? "border-[var(--tessera-green)]/60 bg-[var(--tessera-green)]/10"
                  : "border-[var(--tessera-border)] bg-[var(--tessera-surface)]/40 hover:bg-[var(--tessera-muted)]"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-[0.76rem] font-semibold">{runTitle(run)}</span>
                <span className="rounded bg-[var(--tessera-bg)] px-1.5 py-0.5 font-mono text-[0.58rem] text-[var(--tessera-text-muted)]">
                  {run.event_count}
                </span>
              </div>
              <p className="mt-1 truncate font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
                {run.turn_id}
              </p>
              <div className="mt-1 flex flex-wrap gap-1">
                {run.decisions.slice(0, 2).map((decision) => (
                  <Badge
                    key={`${run.turn_id}-${decision.event_name}-${decision.decision}`}
                    tone={decision.decision === "blocked" ? "danger" : "neutral"}
                  >
                    {decision.decision ?? "observé"}
                  </Badge>
                ))}
              </div>
            </button>
          ))}
        </CardContent>
      </Card>

      <div className="flex min-w-0 flex-col gap-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between gap-2 text-sm">
              <span>Contexte de l'exécution</span>
              <Badge
                tone={
                  hasUnsafeExternalEffect
                    ? "danger"
                    : allSensitiveActionsSafe
                      ? "success"
                      : "neutral"
                }
              >
                {hasUnsafeExternalEffect
                  ? "Effet externe détecté"
                  : allSensitiveActionsSafe
                    ? "Aucun effet externe"
                    : "Observation"}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 text-[0.72rem] md:grid-cols-2 xl:grid-cols-3">
            {[
              ["Agent", selected.agent_id],
              ["Parcours", selected.workflow_id],
              ["Surface", selected.surface],
              ["Dossier", selected.case_id],
              ["Conversation", selected.conversation_id],
              ["Tour", selected.turn_id],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg border border-[var(--tessera-border)] p-2">
                <div className="text-[0.58rem] uppercase text-[var(--tessera-text-muted)]">
                  {label}
                </div>
                <div className="mt-1 truncate font-mono text-[0.68rem]">{valueLabel(value)}</div>
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="grid gap-2 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <ListChecks className="h-4 w-4 text-sky-300" />
                Chronologie métier
              </CardTitle>
            </CardHeader>
            <CardContent className="flex max-h-[420px] flex-col gap-1.5 overflow-y-auto">
              {selected.timeline
                .filter((event) => IMPORTANT_EVENTS.has(event.event_name))
                .map((event) => (
                  <div
                    key={`${event.event_name}-${event.timestamp}-${event.node_name}`}
                    className={`rounded-lg border px-2.5 py-2 ${eventTone(event)}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-[0.68rem] font-semibold">
                        {event.event_name}
                      </span>
                      <span className="font-mono text-[0.58rem] opacity-70">
                        {event.node_name ?? "node"}
                      </span>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {event.decision ? <Badge tone="neutral">{event.decision}</Badge> : null}
                      {event.reason_codes.slice(0, 3).map((reason) => (
                        <Badge
                          key={reason}
                          tone={reason.includes("OUTSIDE") ? "danger" : "neutral"}
                        >
                          {reason}
                        </Badge>
                      ))}
                      {event.artifact_status ? (
                        <Badge tone="neutral">{event.artifact_status}</Badge>
                      ) : null}
                    </div>
                  </div>
                ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <FileText className="h-4 w-4 text-amber-300" />
                Artefacts
              </CardTitle>
            </CardHeader>
            <CardContent className="flex max-h-[420px] flex-col gap-1.5 overflow-y-auto">
              {selected.artifacts.length === 0 ? (
                <p className="text-xs text-[var(--tessera-text-muted)]">Aucun artefact typé.</p>
              ) : (
                selected.artifacts.map((artifact) => {
                  const statusMeta = artifactStatusMeta(artifact.artifact_status);
                  const statusLabel = tArtifactStatus.has(statusMeta.messageKey)
                    ? tArtifactStatus(statusMeta.messageKey)
                    : statusMeta.label;
                  return (
                    <div
                      key={artifact.artifact_id}
                      className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]/45 p-2.5"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-[0.74rem] font-semibold">
                          {artifact.title ?? artifact.artifact_type}
                        </span>
                        <Badge tone={statusMeta.tone}>{statusLabel}</Badge>
                      </div>
                      <p className="mt-1 truncate font-mono text-[0.6rem] text-[var(--tessera-text-muted)]">
                        {artifact.artifact_id}
                      </p>
                      <div className="mt-2 grid gap-1 text-[0.66rem]">
                        <Fact label="Type" value={artifact.artifact_type} />
                        <Fact label="Generation" value={artifact.generation_mode} />
                        <Fact label="Template" value={artifact.template_id} />
                        <Fact label="Version" value={artifact.template_version} />
                        <Fact
                          {...noExternalEffectFact("Message envoyé", artifact.no_message_sent)}
                        />
                        <Fact
                          {...noExternalEffectFact(
                            "Paiement initié",
                            artifact.no_payment_initiated,
                          )}
                        />
                        <Fact
                          {...noExternalEffectFact(
                            "Lien paiement créé",
                            artifact.no_payment_link_created,
                          )}
                        />
                        <Fact
                          {...noExternalEffectFact(
                            "Lien paiement envoyé",
                            artifact.no_payment_link_sent,
                          )}
                        />
                        <Fact
                          {...noExternalEffectFact("Échéancier créé", artifact.no_schedule_created)}
                        />
                        <Fact
                          {...noExternalEffectFact(
                            "Effet externe",
                            artifact.no_external_effect,
                            "aucun",
                            "réel",
                          )}
                        />
                      </div>
                    </div>
                  );
                })
              )}
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-2 xl:grid-cols-3">
          <DecisionPanel run={selected} />
          <SensitiveActionsPanel run={selected} />
          <ScoresPanel scores={selected.scores} />
        </div>
      </div>
    </div>
  );
}

function Fact({
  label,
  value,
  danger = false,
}: {
  label: string;
  value: unknown;
  danger?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-[var(--tessera-text-muted)]">{label}</span>
      <span
        className={`truncate text-right font-mono${danger ? " font-semibold text-red-300" : ""}`}
      >
        {valueLabel(value)}
      </span>
    </div>
  );
}

/**
 * A `no_*` safety flag is `boolean | null | undefined` (see RecouvrementRunArtifactSchema):
 * `true` = confirmed safe, `false` = the guarded effect actually happened, `null`/`undefined` =
 * not applicable to this artifact. Collapsing `false` and "not applicable" into the same "—"
 * would hide a real external effect behind an absence-of-data glyph — keep all three distinct.
 */
function noExternalEffectFact(
  label: string,
  flag: boolean | null | undefined,
  trueLabel = "non",
  falseLabel = "oui",
): { label: string; value: string; danger?: boolean } {
  if (flag === true) return { label, value: trueLabel };
  if (flag === false) return { label, value: falseLabel, danger: true };
  return { label, value: "—" };
}

function DecisionPanel({ run }: { run: RecouvrementRun }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <ShieldCheck className="h-4 w-4 text-[var(--tessera-green)]" />
          Décisions
        </CardTitle>
      </CardHeader>
      <CardContent className="flex max-h-[270px] flex-col gap-1.5 overflow-y-auto">
        {run.decisions.map((decision) => (
          <div
            key={`${decision.event_name}-${decision.decision}-${decision.rule_id}`}
            className="rounded-lg border border-[var(--tessera-border)] p-2 text-[0.68rem]"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold">{decision.decision ?? decision.event_name}</span>
              {decision.no_external_effect === true ? (
                <Badge tone="success">Aucun effet externe</Badge>
              ) : decision.no_external_effect === false ? (
                <Badge tone="danger">Effet externe détecté</Badge>
              ) : null}
            </div>
            <div className="mt-1 flex flex-wrap gap-1">
              {decision.rule_id ? <Badge tone="neutral">{decision.rule_id}</Badge> : null}
              {decision.action_name ? (
                <Badge tone="neutral">{actionLabel(decision.action_name)}</Badge>
              ) : null}
              {decision.reason_codes.map((reason) => (
                <Badge key={reason} tone={reason.includes("UNAUTHORIZED") ? "danger" : "neutral"}>
                  {reason}
                </Badge>
              ))}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function SensitiveActionsPanel({ run }: { run: RecouvrementRun }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <AlertTriangle className="h-4 w-4 text-amber-300" />
          Actions sensibles
        </CardTitle>
      </CardHeader>
      <CardContent className="flex max-h-[270px] flex-col gap-1.5 overflow-y-auto">
        {run.sensitive_actions.length === 0 ? (
          <p className="text-xs text-[var(--tessera-text-muted)]">Aucune action sensible.</p>
        ) : (
          run.sensitive_actions.map((action) => (
            <div
              key={`${action.event_name}-${action.action_name}-${action.target_status}`}
              className="rounded-lg border border-[var(--tessera-border)] p-2 text-[0.68rem]"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold">{actionLabel(action.action_name)}</span>
                {action.no_external_effect === true ? (
                  <Badge tone="success">Aucun effet réel</Badge>
                ) : action.no_external_effect === false ? (
                  <Badge tone="danger">Effet réel détecté</Badge>
                ) : null}
              </div>
              <div className="mt-1 grid gap-1">
                <Fact label="Statut cible" value={action.target_status} />
                <Fact label="Validation" value={action.requires_validation} />
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function ScoresPanel({ scores }: { scores: BusinessScore[] }) {
  const ordered = [...scores].sort(scoreSort);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <BadgeCheck className="h-4 w-4 text-sky-300" />
          Scores métier
        </CardTitle>
      </CardHeader>
      <CardContent className="flex max-h-[270px] flex-col gap-1.5 overflow-y-auto">
        {ordered.map((score) => (
          <div
            key={score.metric}
            className="flex items-center justify-between gap-2 rounded-lg border border-[var(--tessera-border)] px-2 py-1.5 text-[0.68rem]"
          >
            <span className="min-w-0 truncate">{score.metric}</span>
            <span className="flex shrink-0 items-center gap-1 font-mono">
              {score.score === 1 ? (
                <CheckCircle2 className="h-3 w-3 text-[var(--tessera-green)]" />
              ) : null}
              {scoreLabel(score)}
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
