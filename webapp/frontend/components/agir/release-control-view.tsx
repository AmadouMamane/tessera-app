import { CheckCircle2, ChevronRight, CircleSlash, GitBranch, ShieldX } from "lucide-react";
import type { Route } from "next";
import { getTranslations } from "next-intl/server";
import type { ReactNode } from "react";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { Link } from "@/i18n/navigation";
import type { ReleaseControl } from "@/lib/api/schemas";

const VERDICT_TONE: Record<string, string> = {
  good: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  crit: "border-red-500/40 bg-red-500/10 text-red-300",
  bad: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  muted:
    "border-[var(--tessera-border)] bg-[var(--tessera-surface-2)] text-[var(--tessera-text-muted)]",
};

const STATE_DOT: Record<string, string> = {
  good: "bg-emerald-400",
  bad: "bg-red-400",
  warn: "bg-amber-400",
};

/**
 * Release Control body — org summary + per-agent release pipeline cards.
 *
 * Each agent is a governed package; the verdict is the policy-correct eval-gate
 * over the agent's OWN run (eval-gate-policy §6: the verdict is the headline,
 * colour tied to conformity). The summary counts DISTINCT agents by readiness
 * (agent counts, never deduped conversation totals).
 */
export async function ReleaseControlView({
  data,
  locale,
}: {
  data: ReleaseControl | null;
  locale: string;
}) {
  const t = await getTranslations({ locale, namespace: "releaseControl" });
  // ⓘ explainer for a metric/cell (every explain.<k> carries what/how/source, so we
  // never need a server-side `.has`). MetricInfo is a client component embedded here.
  const info = (k: string) => (
    <MetricInfo
      title={t(k)}
      what={t(`explain.${k}.what`)}
      how={t(`explain.${k}.how`)}
      source={t(`explain.${k}.source`)}
    />
  );
  const agents = data?.agents ?? [];
  const summary = data?.summary;

  if (!data || !data.available || agents.length === 0) {
    return (
      <p className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4 text-[0.78rem] text-[var(--tessera-text-muted)]">
        {t("empty")}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Org summary — distinct-agent counts by release readiness. The counts drill
          into the real fleet list. */}
      <section className="flex flex-col gap-2">
        <div className="flex items-center justify-end">
          <Link
            href="/agents"
            className="inline-flex items-center gap-0.5 text-[0.66rem] text-[#b9a6ff] hover:underline"
          >
            {t("viewFleet")}
            <ChevronRight className="h-3 w-3" />
          </Link>
        </div>
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
          <Kpi label={t("total")} value={summary?.total ?? agents.length} icon="branch" />
          <Kpi
            label={t("passing")}
            value={summary?.passing ?? 0}
            icon="ok"
            tone="good"
            info={info("passing")}
          />
          <Kpi
            label={t("blocked")}
            value={summary?.blocked ?? 0}
            icon="block"
            tone="bad"
            info={info("blocked")}
          />
          <Kpi
            label={t("notRun")}
            value={summary?.not_run ?? 0}
            icon="none"
            tone="muted"
            info={info("notRun")}
          />
        </div>
      </section>

      {/* Per-agent release pipeline cards. */}
      <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
        {agents.map((a) => {
          const rel = a.release;
          return (
            <section
              key={a.agent_id}
              className="flex flex-col gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate font-semibold">{a.name}</p>
                  <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{a.owner}</p>
                </div>
                <span className="inline-flex shrink-0 items-center gap-1.5 text-[0.66rem] text-[var(--tessera-text-muted)]">
                  <span
                    className={`h-2 w-2 rounded-full ${STATE_DOT[a.state_tone] ?? "bg-amber-400"}`}
                  />
                  {a.state}
                </span>
              </div>

              {/* Verdict — the headline, colour tied to gate conformity (policy §6). */}
              {rel.available ? (
                <div
                  className={`flex items-center justify-between gap-2 rounded-md border px-2.5 py-1.5 text-[0.72rem] font-medium ${
                    VERDICT_TONE[rel.verdict_tone] ?? VERDICT_TONE.muted
                  }`}
                >
                  <span>{rel.verdict_label}</span>
                  <span className="font-mono text-[0.58rem] opacity-80">
                    {rel.candidate_version}
                  </span>
                </div>
              ) : (
                <div className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface-2)] px-2.5 py-1.5 text-[0.72rem] text-[var(--tessera-text-muted)]">
                  {t("evalNotRun")}
                </div>
              )}

              {/* Gate breakdown — case×langue grain, reconciled with Évaluations. */}
              {rel.available ? (
                <dl className="grid grid-cols-2 gap-1.5 text-[0.66rem]">
                  <Cell label={t("evalSet")} value={rel.eval_set} />
                  <Cell label={t("executions")} value={String(rel.executions)} />
                  <Cell
                    label={t("socle")}
                    value={rel.socle_ok ? t("socleOk") : t("socleFail")}
                    tone={rel.socle_ok ? "good" : "bad"}
                    info={info("socle")}
                  />
                  <Cell
                    label={t("blockingSocle")}
                    value={String(rel.blocking_socle)}
                    info={info("blockingSocle")}
                  />
                  <Cell
                    label={t("blockingT1")}
                    value={String(rel.blocking_t1)}
                    info={info("blockingT1")}
                  />
                  <Cell
                    label={t("waived")}
                    value={String(rel.waived_active)}
                    info={info("waived")}
                  />
                </dl>
              ) : null}

              {/* Governance flow stepper. */}
              <div className="flex items-center gap-1 text-[0.6rem]">
                {a.flow.map((stage, i) => {
                  const reached =
                    a.flow.indexOf(a.last_phase) >= i && a.last_phase !== "registered";
                  return (
                    <span key={stage} className="flex items-center gap-1">
                      <span
                        className={`rounded px-1.5 py-0.5 ${
                          reached
                            ? "bg-[#7c5cf5]/20 text-[#b9a6ff]"
                            : "bg-[var(--tessera-surface-2)] text-[var(--tessera-text-muted)]"
                        }`}
                      >
                        {t(`flow.${stage}`)}
                      </span>
                      {i < a.flow.length - 1 ? (
                        <span className="text-[var(--tessera-text-muted)]">→</span>
                      ) : null}
                    </span>
                  );
                })}
              </div>

              {a.history[0] ? (
                <p className="border-t border-[var(--tessera-border)] pt-2 text-[0.6rem] text-[var(--tessera-text-muted)]">
                  {t("lastEvent")}: {a.history[0].phase} · {a.history[0].occurred_at}
                </p>
              ) : null}
              {/* Drill into the agent's own surface (release/eval detail). */}
              <Link
                href={`/agents/${a.agent_id}` as Route}
                className="mt-auto inline-flex items-center gap-0.5 self-start text-[0.62rem] text-[#b9a6ff] hover:underline"
              >
                {t("viewAgent")}
                <ChevronRight className="h-3 w-3" />
              </Link>
            </section>
          );
        })}
      </div>
    </div>
  );
}

function Kpi({
  label,
  value,
  icon,
  tone,
  info,
}: {
  label: string;
  value: number;
  icon: "branch" | "ok" | "block" | "none";
  tone?: "good" | "bad" | "muted";
  info?: ReactNode;
}) {
  const color =
    tone === "good"
      ? "text-emerald-300"
      : tone === "bad"
        ? "text-red-300"
        : "text-[var(--tessera-text)]";
  const Icon =
    icon === "ok"
      ? CheckCircle2
      : icon === "block"
        ? ShieldX
        : icon === "none"
          ? CircleSlash
          : GitBranch;
  return (
    <div className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="flex items-center gap-1.5 text-[0.62rem] text-[var(--tessera-text-muted)]">
        <Icon className="h-3.5 w-3.5 shrink-0" />
        <span className="min-w-0 truncate">{label}</span>
        {info ? <span className="ml-auto shrink-0">{info}</span> : null}
      </div>
      <p className={`mt-1 text-[1.3rem] font-semibold tabular-nums ${color}`}>{value}</p>
    </div>
  );
}

function Cell({
  label,
  value,
  tone,
  info,
}: {
  label: string;
  value: string;
  tone?: "good" | "bad";
  info?: ReactNode;
}) {
  const color =
    tone === "good"
      ? "text-emerald-300"
      : tone === "bad"
        ? "text-red-300"
        : "text-[var(--tessera-text)]";
  return (
    <div>
      <dt className="flex items-center gap-1 text-[var(--tessera-text-muted)]">
        <span className="min-w-0 truncate">{label}</span>
        {info}
      </dt>
      <dd className={`font-medium tabular-nums ${color}`}>{value}</dd>
    </div>
  );
}
