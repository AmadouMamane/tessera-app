import { getTranslations } from "next-intl/server";

import type {
  AlarmLens,
  BreakdownLens,
  CellEmpty,
  ComplianceLens,
  ObservabilityLens,
  QualityLens,
  ReliabilityLens,
  SecurityLens,
} from "@/lib/agent-lens";
import { AGENT_SCOPE_ALL } from "@/lib/agent-scope";
import type { Fleet } from "@/lib/api/schemas";

const fmtInt = (n: number) => n.toLocaleString("fr-FR").replace(/ /g, " ");
const fmtPct = (n: number) => `${n.toFixed(1).replace(".", ",")} %`;
const fmtSecs = (ms: number | null) =>
  ms === null ? "—" : `${(ms / 1000).toFixed(1).replace(".", ",")} s`;
/** A 0..1 rate as a percentage ("71,6 %"). */
const fmtRate = (r: number) => fmtPct(r * 100);
/** A signed percentage-point distance ("−23,4 pt" / "+1,2 pt"). */
const fmtPp = (pp: number) => `${pp > 0 ? "+" : ""}${pp.toFixed(1).replace(".", ",")} pt`;
const fmtDate = (iso: string | undefined) => (iso ? iso.slice(0, 10) : "—");

const RELEASE_TONE: Record<string, string> = {
  good: "text-emerald-300",
  crit: "text-red-300",
  bad: "text-amber-300",
  muted: "text-[var(--tessera-text-muted)]",
};

type Translator = Awaited<ReturnType<typeof getTranslations>>;
type FleetAgent = NonNullable<Fleet["agents"]>[number];

/** The release verdict cell — the release lane's work, rendered identically in every lens. */
function ReleaseCell({ agent, t }: { agent: FleetAgent; t: Translator }) {
  return (
    <span className={RELEASE_TONE[agent.release?.verdict_tone ?? "muted"] ?? RELEASE_TONE.muted}>
      {agent.release?.available ? agent.release.verdict_label : t("releaseNotRun")}
    </span>
  );
}

/**
 * An honest empty cell: a dash that says WHY, never a bare gap. A refusal (the report could
 * not prove the slice) and "no sample" (the read succeeded, the window was empty) are both
 * dashes on screen — but they are NOT the same fact, and the title says which.
 */
function EmptyCell({ reason, t }: { reason: CellEmpty | null; t: Translator }) {
  return <span title={reason ? t(`refusal.${reason}`) : undefined}>—</span>;
}

function rowClass(selected: boolean, dimmed: boolean): string {
  return `border-t border-[var(--tessera-border)] ${selected ? "bg-[#7c5cf5]/10" : ""} ${
    dimmed ? "opacity-45" : ""
  }`;
}

/**
 * Per-agent breakdown for GOUVERNER / PLATEFORME surfaces, with a visually
 * distinct **Total org (dédup)** row.
 *
 * The org total counts DISTINCT conversations (a handoff conversation = 1) — it is
 * NEVER the sum of the per-agent rows, and the gap (dedup saving) is shown
 * explicitly so an operator can see the deduplication at work. Sourced from the
 * real fleet rollup; when scoped to one agent (`scope` ≠ `all`) the matching row
 * is highlighted while the org total stays the deduplicated whole.
 *
 * The columns are a **lens**, not a fixture. The default `monitoring` lens keeps the
 * historical observable KPIs (volume, escalation, latency, handoffs, release verdict —
 * ADR 0013's monitoring facet), unchanged everywhere it was already rendered. Qualité IA
 * passes the lens `lib/server/agent-lens.ts` builds: `alarm` answers the breached signal
 * (value · gap to SLO · contribution, sorted by contribution), `quality` answers the
 * page's question when nothing breaches, and `masked` hides the table entirely for an
 * org-wide signal — a signal with no per-agent substrate must not get a per-agent table.
 * Every lens number is gated by the signal's own scope report (`selectHonouredSignal`).
 */
export async function AgentBreakdown({
  fleet,
  scope,
  locale,
  lens = { kind: "monitoring" },
}: {
  fleet: Fleet | null;
  scope: string;
  locale: string;
  lens?: BreakdownLens;
}) {
  const t = await getTranslations({ locale, namespace: "agentScope" });
  const agents = fleet?.agents ?? [];
  // Handoff reconciliation — the S1 journal's claim vs what the conversation store can see.
  // `shared_conversations` alone reads 0 with composure when handed-off journeys never share
  // an id in the store, so the footer must state the journal's side too, and name any gap.
  const attested = fleet?.handoff_conversations ?? 0;
  const seenShared = fleet?.handoff_conversations_seen_shared ?? 0;
  const handoffGap = attested - seenShared;

  if (!fleet || agents.length === 0) {
    return (
      <section className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4">
        <h2 className="text-[0.82rem] font-semibold">{t("breakdownTitle")}</h2>
        <p className="mt-2 text-[0.72rem] text-[var(--tessera-text-muted)]">{t("empty")}</p>
      </section>
    );
  }

  // An org-wide signal has no per-agent substrate: the table is masked, and the header
  // note + the "Fiche signal" rail say why — the operator knows what they are NOT seeing.
  if (lens.kind === "masked") {
    return (
      <section className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4">
        <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-[0.82rem] font-semibold">{t("breakdownTitle")}</h2>
        </div>
        <p className="text-[0.72rem] text-[var(--tessera-text-muted)]">{t("maskedOrgWide")}</p>
      </section>
    );
  }

  const note =
    lens.kind === "alarm"
      ? t("alarmNote", { metric: metricLabel(lens.metric, t) })
      : lens.kind === "quality"
        ? t("qualityNote")
        : lens.kind === "security"
          ? t("securityNote")
          : lens.kind === "compliance"
            ? t("complianceNote")
            : lens.kind === "reliability"
              ? t("reliabilityNote")
              : lens.kind === "observability"
                ? t("observabilityNote")
                : t("breakdownNote");

  return (
    <section className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-[0.82rem] font-semibold">{t("breakdownTitle")}</h2>
        <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{note}</p>
      </div>
      <div className="overflow-x-auto">
        {lens.kind === "alarm" ? (
          <AlarmTable lens={lens} agents={agents} scope={scope} t={t} fleet={fleet} />
        ) : lens.kind === "quality" ? (
          <QualityTable lens={lens} agents={agents} scope={scope} t={t} fleet={fleet} />
        ) : lens.kind === "security" ? (
          <SecurityTable lens={lens} agents={agents} scope={scope} t={t} fleet={fleet} />
        ) : lens.kind === "compliance" ? (
          <ComplianceTable lens={lens} agents={agents} scope={scope} t={t} fleet={fleet} />
        ) : lens.kind === "reliability" ? (
          <ReliabilityTable lens={lens} agents={agents} scope={scope} t={t} fleet={fleet} />
        ) : lens.kind === "observability" ? (
          <ObservabilityTable lens={lens} agents={agents} scope={scope} t={t} fleet={fleet} />
        ) : (
          <MonitoringTable
            agents={agents}
            scope={scope}
            t={t}
            fleet={fleet}
            attested={attested}
            seenShared={seenShared}
            handoffGap={handoffGap}
          />
        )}
      </div>
    </section>
  );
}

function metricLabel(metric: string | null, t: Translator): string {
  if (!metric) return t("metricUnknown");
  return t.has(`metric.${metric}`) ? t(`metric.${metric}`) : metric;
}

/** The historical monitoring columns — byte-for-byte the pre-lens rendering. */
function MonitoringTable({
  agents,
  scope,
  t,
  fleet,
  attested,
  seenShared,
  handoffGap,
}: {
  agents: FleetAgent[];
  scope: string;
  t: Translator;
  fleet: Fleet;
  attested: number;
  seenShared: number;
  handoffGap: number;
}) {
  return (
    <table className="w-full text-[0.72rem]">
      <thead>
        <tr className="text-left text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
          <th className="pb-2 pr-3 font-medium">{t("colAgent")}</th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colVolume")}</th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colEscalation")}</th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colLatency")}</th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colHandoffs")}</th>
          <th className="pb-2 font-medium">{t("colRelease")}</th>
        </tr>
      </thead>
      <tbody>
        {agents.map((a) => {
          const selected = scope !== AGENT_SCOPE_ALL && a.id === scope;
          const dimmed = scope !== AGENT_SCOPE_ALL && a.id !== scope;
          return (
            <tr key={a.id} className={rowClass(selected, dimmed)}>
              <td className="py-1.5 pr-3 font-medium">{a.name}</td>
              <td className="py-1.5 pr-3 text-right tabular-nums">{fmtInt(a.conversations)}</td>
              <td className="py-1.5 pr-3 text-right tabular-nums">{fmtPct(a.escalation_rate)}</td>
              <td className="py-1.5 pr-3 text-right tabular-nums">{fmtSecs(a.latency_ms)}</td>
              <td className="py-1.5 pr-3 text-right tabular-nums">
                {a.handoffs_in} / {a.handoffs_out}
              </td>
              <td className="py-1.5">
                <ReleaseCell agent={a} t={t} />
              </td>
            </tr>
          );
        })}
      </tbody>
      <tfoot>
        {/* Total org — DISTINCT entities, never the sum of the rows above. */}
        <tr className="border-t-2 border-[#7c5cf5]/40">
          <td className="py-2 pr-3 font-semibold text-[#b9a6ff]">{t("orgTotal")}</td>
          <td className="py-2 pr-3 text-right font-semibold tabular-nums text-[#b9a6ff]">
            {fmtInt(fleet.org?.conversations ?? 0)}
          </td>
          <td
            colSpan={4}
            className="py-2 text-right text-[0.62rem] text-[var(--tessera-text-muted)]"
          >
            <DedupFooter
              fleet={fleet}
              t={t}
              attested={attested}
              seenShared={seenShared}
              handoffGap={handoffGap}
            />
          </td>
        </tr>
      </tfoot>
    </table>
  );
}

/** The dedup + handoff reconciliation block — ONE implementation, shared by every lens. */
function DedupFooter({
  fleet,
  t,
  attested,
  seenShared,
  handoffGap,
}: {
  fleet: Fleet;
  t: Translator;
  attested: number;
  seenShared: number;
  handoffGap: number;
}) {
  return (
    <>
      <span className="block">
        {t("dedupExplain", {
          naive: fmtInt(fleet.naive_sum_conversations ?? 0),
          saved: fmtInt(fleet.dedup_saved ?? 0),
          shared: fmtInt(fleet.shared_conversations ?? 0),
        })}
      </span>
      {attested > 0 ? (
        handoffGap > 0 ? (
          <span className="mt-0.5 block text-amber-300/90">
            {t("handoffGap", {
              events: fmtInt(fleet.handoff_events ?? 0),
              attested: fmtInt(attested),
              seen: fmtInt(seenShared),
            })}
          </span>
        ) : (
          <span className="mt-0.5 block">
            {t("handoffReconciled", { attested: fmtInt(attested) })}
          </span>
        )
      ) : null}
    </>
  );
}

/**
 * The alarm lens: the table answers the breached signal, per agent, sorted by
 * contribution descending — the banner says "N bad", this says WHICH ones are WHOSE.
 */
function AlarmTable({
  lens,
  agents,
  scope,
  t,
  fleet,
}: {
  lens: AlarmLens;
  agents: FleetAgent[];
  scope: string;
  t: Translator;
  fleet: Fleet;
}) {
  const byId = new Map(agents.map((a) => [a.id, a]));
  const attested = fleet.handoff_conversations ?? 0;
  const seenShared = fleet.handoff_conversations_seen_shared ?? 0;
  return (
    <table className="w-full text-[0.72rem]">
      <thead>
        <tr className="text-left text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
          <th className="pb-2 pr-3 font-medium">{t("colAgent")}</th>
          <th className="pb-2 pr-3 text-right font-medium">
            {t("colSignalValue", { metric: metricLabel(lens.metric, t) })}
          </th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colSloGap")}</th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colContribution")}</th>
          <th className="pb-2 font-medium">{t("colRelease")}</th>
        </tr>
      </thead>
      <tbody>
        {lens.rows.map((row) => {
          const a = byId.get(row.agentId);
          if (!a) return null;
          const selected = scope !== AGENT_SCOPE_ALL && a.id === scope;
          const dimmed = scope !== AGENT_SCOPE_ALL && a.id !== scope;
          return (
            <tr key={a.id} className={rowClass(selected, dimmed)}>
              <td className="py-1.5 pr-3 font-medium">{a.name}</td>
              <td className="py-1.5 pr-3 text-right tabular-nums">
                {row.value === null ? <EmptyCell reason={row.refusal} t={t} /> : fmtRate(row.value)}
              </td>
              <td
                className={`py-1.5 pr-3 text-right tabular-nums ${
                  row.gapPp !== null && row.gapPp < 0 ? "text-red-300" : ""
                }`}
              >
                {row.gapPp === null ? <EmptyCell reason={row.refusal} t={t} /> : fmtPp(row.gapPp)}
              </td>
              <td className="py-1.5 pr-3 text-right tabular-nums">
                {row.nBad === null ? (
                  <EmptyCell reason={row.refusal} t={t} />
                ) : (
                  `${fmtInt(row.nBad)} / ${fmtInt(row.n ?? 0)}`
                )}
              </td>
              <td className="py-1.5">
                <ReleaseCell agent={a} t={t} />
              </td>
            </tr>
          );
        })}
      </tbody>
      <tfoot>
        <tr className="border-t-2 border-[#7c5cf5]/40">
          <td className="py-2 pr-3 font-semibold text-[#b9a6ff]">{t("orgTotal")}</td>
          <td colSpan={2} className="py-2" />
          <td className="py-2 pr-3 text-right font-semibold tabular-nums text-[#b9a6ff]">
            {lens.orgNBad === null || lens.orgN === null
              ? "—"
              : `${fmtInt(lens.orgNBad)} / ${fmtInt(lens.orgN)}`}
          </td>
          <td className="py-2" />
        </tr>
        <tr>
          <td
            colSpan={5}
            className="pb-1 text-right text-[0.62rem] text-[var(--tessera-text-muted)]"
          >
            {/* Contribution reconciliation — the per-agent slices vs the deduplicated org
                total. ∑ slices = org would be a coincidence, not a proof: a handed-off
                journey touches two agents and counts once in the org. Stated, never smoothed;
                the handoff line below (the ONE existing reconciliation) explains the gap. */}
            {lens.sumNBad !== null && lens.orgNBad !== null ? (
              lens.sumNBad === lens.orgNBad ? (
                <span className="block">
                  {t("contribReconciled", { sum: fmtInt(lens.sumNBad), org: fmtInt(lens.orgNBad) })}
                </span>
              ) : (
                <span className="block text-amber-300/90">
                  {t("contribGap", { sum: fmtInt(lens.sumNBad), org: fmtInt(lens.orgNBad) })}
                </span>
              )
            ) : (
              <span className="block">{t("contribUnknown")}</span>
            )}
            <DedupFooter
              fleet={fleet}
              t={t}
              attested={attested}
              seenShared={seenShared}
              handoffGap={attested - seenShared}
            />
          </td>
        </tr>
      </tfoot>
    </table>
  );
}

/** The quality lens (no alarm): the page's own question, per agent. */
function QualityTable({
  lens,
  agents,
  scope,
  t,
  fleet,
}: {
  lens: QualityLens;
  agents: FleetAgent[];
  scope: string;
  t: Translator;
  fleet: Fleet;
}) {
  const byId = new Map(lens.rows.map((r) => [r.agentId, r]));
  const attested = fleet.handoff_conversations ?? 0;
  const seenShared = fleet.handoff_conversations_seen_shared ?? 0;
  return (
    <table className="w-full text-[0.72rem]">
      <thead>
        <tr className="text-left text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
          <th className="pb-2 pr-3 font-medium">{t("colAgent")}</th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colFaithfulness")}</th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colHallucination")}</th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colRegression")}</th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colGate")}</th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colEvalFreshness")}</th>
          <th className="pb-2 font-medium">{t("colRelease")}</th>
        </tr>
      </thead>
      <tbody>
        {agents.map((a) => {
          const row = byId.get(a.id);
          const selected = scope !== AGENT_SCOPE_ALL && a.id === scope;
          const dimmed = scope !== AGENT_SCOPE_ALL && a.id !== scope;
          const rel = a.release?.available ? a.release : null;
          return (
            <tr key={a.id} className={rowClass(selected, dimmed)}>
              <td className="py-1.5 pr-3 font-medium">{a.name}</td>
              <td className="py-1.5 pr-3 text-right tabular-nums">
                {row?.faithfulness == null ? (
                  <EmptyCell reason={row?.faithfulnessRefusal ?? "absent"} t={t} />
                ) : (
                  fmtRate(row.faithfulness)
                )}
              </td>
              <td className="py-1.5 pr-3 text-right tabular-nums">
                {row?.hallucination == null ? (
                  <EmptyCell reason={row?.hallucinationRefusal ?? "absent"} t={t} />
                ) : (
                  fmtRate(row.hallucination)
                )}
              </td>
              <td
                className={`py-1.5 pr-3 text-right tabular-nums ${
                  rel && rel.blocking_t1 > 0 ? "text-red-300" : ""
                }`}
              >
                {rel ? fmtInt(rel.blocking_t1) : "—"}
              </td>
              <td className="py-1.5 pr-3 text-right tabular-nums">
                {rel && rel.summary_passed != null && rel.summary_total != null
                  ? `${fmtInt(rel.summary_passed)}/${fmtInt(rel.summary_total)}`
                  : "—"}
              </td>
              <td
                className={`py-1.5 pr-3 text-right tabular-nums ${
                  rel?.verdict_stale ? "text-amber-300" : ""
                }`}
                title={rel?.verdict_stale ? t("staleEval") : undefined}
              >
                {rel ? fmtDate(rel.run_at) : "—"}
              </td>
              <td className="py-1.5">
                <ReleaseCell agent={a} t={t} />
              </td>
            </tr>
          );
        })}
      </tbody>
      <tfoot>
        <tr className="border-t-2 border-[#7c5cf5]/40">
          <td className="py-2 pr-3 font-semibold text-[#b9a6ff]">{t("orgTotal")}</td>
          <td
            colSpan={6}
            className="py-2 text-right text-[0.62rem] text-[var(--tessera-text-muted)]"
          >
            <DedupFooter
              fleet={fleet}
              t={t}
              attested={attested}
              seenShared={seenShared}
              handoffGap={attested - seenShared}
            />
          </td>
        </tr>
      </tfoot>
    </table>
  );
}

/** A "found / screened" pair, or the honest empty cell naming why. */
function PairCell({
  found,
  outOf,
  reason,
  t,
}: {
  found: number | null;
  outOf: number | null;
  reason: CellEmpty | null;
  t: Translator;
}) {
  if (found === null || outOf === null) return <EmptyCell reason={reason ?? "absent"} t={t} />;
  return (
    <>
      {fmtInt(found)} / {fmtInt(outOf)}
    </>
  );
}

/** A plain count. 0 is a measured fact and renders as 0 — only an unproven read refuses. */
function CountCell({
  value,
  reason,
  t,
}: {
  value: number | null;
  reason: CellEmpty | null;
  t: Translator;
}) {
  if (value === null) return <EmptyCell reason={reason ?? "absent"} t={t} />;
  return <>{fmtInt(value)}</>;
}

/** The shared tfoot of the domain lens tables: org total + the dedup/handoff reconciliation. */
function DomainFoot({ fleet, t, span }: { fleet: Fleet; t: Translator; span: number }) {
  const attested = fleet.handoff_conversations ?? 0;
  const seenShared = fleet.handoff_conversations_seen_shared ?? 0;
  return (
    <tfoot>
      <tr className="border-t-2 border-[#7c5cf5]/40">
        <td className="py-2 pr-3 font-semibold text-[#b9a6ff]">{t("orgTotal")}</td>
        <td
          colSpan={span}
          className="py-2 text-right text-[0.62rem] text-[var(--tessera-text-muted)]"
        >
          <DedupFooter
            fleet={fleet}
            t={t}
            attested={attested}
            seenShared={seenShared}
            handoffGap={attested - seenShared}
          />
        </td>
      </tr>
    </tfoot>
  );
}

/**
 * The security lens (Sécurité & Privacy): the security facts the spine deposits PER AGENT —
 * PII leaks, toxicity, guard denials. Guard efficacy and injection bypass are org-wide by
 * construction and deliberately have no column here (the page body carries them org-wide).
 */
function SecurityTable({
  lens,
  agents,
  scope,
  t,
  fleet,
}: {
  lens: SecurityLens;
  agents: FleetAgent[];
  scope: string;
  t: Translator;
  fleet: Fleet;
}) {
  const byId = new Map(lens.rows.map((r) => [r.agentId, r]));
  return (
    <table className="w-full text-[0.72rem]">
      <thead>
        <tr className="text-left text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
          <th className="pb-2 pr-3 font-medium">{t("colAgent")}</th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colPiiLeaks")}</th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colToxicity")}</th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colGuardDenied")}</th>
          <th className="pb-2 font-medium">{t("colRelease")}</th>
        </tr>
      </thead>
      <tbody>
        {agents.map((a) => {
          const row = byId.get(a.id);
          const selected = scope !== AGENT_SCOPE_ALL && a.id === scope;
          const dimmed = scope !== AGENT_SCOPE_ALL && a.id !== scope;
          return (
            <tr key={a.id} className={rowClass(selected, dimmed)}>
              <td className="py-1.5 pr-3 font-medium">{a.name}</td>
              <td
                className={`py-1.5 pr-3 text-right tabular-nums ${
                  row?.piiLeaks ? "text-red-300" : ""
                }`}
              >
                <PairCell
                  found={row?.piiLeaks ?? null}
                  outOf={row?.piiN ?? null}
                  reason={row?.piiRefusal ?? null}
                  t={t}
                />
              </td>
              <td
                className={`py-1.5 pr-3 text-right tabular-nums ${
                  row?.toxCount ? "text-red-300" : ""
                }`}
              >
                <PairCell
                  found={row?.toxCount ?? null}
                  outOf={row?.toxN ?? null}
                  reason={row?.toxRefusal ?? null}
                  t={t}
                />
              </td>
              <td className="py-1.5 pr-3 text-right tabular-nums">
                <PairCell
                  found={row?.guardDenied ?? null}
                  outOf={row?.guardTotal ?? null}
                  reason={row?.guardRefusal ?? null}
                  t={t}
                />
              </td>
              <td className="py-1.5">
                <ReleaseCell agent={a} t={t} />
              </td>
            </tr>
          );
        })}
      </tbody>
      <DomainFoot fleet={fleet} t={t} span={4} />
    </table>
  );
}

/**
 * The compliance lens (Conformité): governed acts and ledger entries per agent (counts — an
 * honest 0 is data), plus the fleet's own per-agent escalation rate, the same fact the
 * monitoring lens renders. Ledger INTEGRITY is org-wide by construction: not a column.
 */
function ComplianceTable({
  lens,
  agents,
  scope,
  t,
  fleet,
}: {
  lens: ComplianceLens;
  agents: FleetAgent[];
  scope: string;
  t: Translator;
  fleet: Fleet;
}) {
  const byId = new Map(lens.rows.map((r) => [r.agentId, r]));
  return (
    <table className="w-full text-[0.72rem]">
      <thead>
        <tr className="text-left text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
          <th className="pb-2 pr-3 font-medium">{t("colAgent")}</th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colGovernedActs")}</th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colLedgerEntries")}</th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colEscalation")}</th>
          <th className="pb-2 font-medium">{t("colRelease")}</th>
        </tr>
      </thead>
      <tbody>
        {agents.map((a) => {
          const row = byId.get(a.id);
          const selected = scope !== AGENT_SCOPE_ALL && a.id === scope;
          const dimmed = scope !== AGENT_SCOPE_ALL && a.id !== scope;
          return (
            <tr key={a.id} className={rowClass(selected, dimmed)}>
              <td className="py-1.5 pr-3 font-medium">{a.name}</td>
              <td className="py-1.5 pr-3 text-right tabular-nums">
                <CountCell
                  value={row?.governedActs ?? null}
                  reason={row?.governedRefusal ?? null}
                  t={t}
                />
              </td>
              <td className="py-1.5 pr-3 text-right tabular-nums">
                <CountCell
                  value={row?.ledgerEntries ?? null}
                  reason={row?.ledgerRefusal ?? null}
                  t={t}
                />
              </td>
              <td className="py-1.5 pr-3 text-right tabular-nums">{fmtPct(a.escalation_rate)}</td>
              <td className="py-1.5">
                <ReleaseCell agent={a} t={t} />
              </td>
            </tr>
          );
        })}
      </tbody>
      <DomainFoot fleet={fleet} t={t} span={4} />
    </table>
  );
}

/**
 * The observability lens (Observabilité): behavioural anomalies and tool-call schema
 * conformance per agent — the telemetry-plane facts measured to deposit per agent.
 * Pipeline/collector health and Langfuse traces stay in the page body: org-wide (traces
 * is declared per-agent but has no registered read), so deliberately no column here.
 */
function ObservabilityTable({
  lens,
  agents,
  scope,
  t,
  fleet,
}: {
  lens: ObservabilityLens;
  agents: FleetAgent[];
  scope: string;
  t: Translator;
  fleet: Fleet;
}) {
  const byId = new Map(lens.rows.map((r) => [r.agentId, r]));
  return (
    <table className="w-full text-[0.72rem]">
      <thead>
        <tr className="text-left text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
          <th className="pb-2 pr-3 font-medium">{t("colAgent")}</th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colAnomalies")}</th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colConformance")}</th>
          <th className="pb-2 font-medium">{t("colRelease")}</th>
        </tr>
      </thead>
      <tbody>
        {agents.map((a) => {
          const row = byId.get(a.id);
          const selected = scope !== AGENT_SCOPE_ALL && a.id === scope;
          const dimmed = scope !== AGENT_SCOPE_ALL && a.id !== scope;
          return (
            <tr key={a.id} className={rowClass(selected, dimmed)}>
              <td className="py-1.5 pr-3 font-medium">{a.name}</td>
              <td
                className={`py-1.5 pr-3 text-right tabular-nums ${
                  row?.anomalous ? "text-red-300" : ""
                }`}
              >
                <PairCell
                  found={row?.anomalous ?? null}
                  outOf={row?.sessions ?? null}
                  reason={row?.anomaliesRefusal ?? null}
                  t={t}
                />
              </td>
              <td
                className={`py-1.5 pr-3 text-right tabular-nums ${
                  row?.violations ? "text-red-300" : ""
                }`}
              >
                <PairCell
                  found={row?.violations ?? null}
                  outOf={row?.calls ?? null}
                  reason={row?.conformanceRefusal ?? null}
                  t={t}
                />
              </td>
              <td className="py-1.5">
                <ReleaseCell agent={a} t={t} />
              </td>
            </tr>
          );
        })}
      </tbody>
      <DomainFoot fleet={fleet} t={t} span={3} />
    </table>
  );
}

/**
 * The reliability lens (Fiabilité & coût): tool errors and token cost per agent, plus the
 * fleet's own per-agent AVERAGE latency (the same fact as the monitoring column — latency
 * p95 has no per-agent substrate and is deliberately not a column).
 */
function ReliabilityTable({
  lens,
  agents,
  scope,
  t,
  fleet,
}: {
  lens: ReliabilityLens;
  agents: FleetAgent[];
  scope: string;
  t: Translator;
  fleet: Fleet;
}) {
  const byId = new Map(lens.rows.map((r) => [r.agentId, r]));
  return (
    <table className="w-full text-[0.72rem]">
      <thead>
        <tr className="text-left text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
          <th className="pb-2 pr-3 font-medium">{t("colAgent")}</th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colToolErrors")}</th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colLatency")}</th>
          <th className="pb-2 pr-3 text-right font-medium">{t("colCostTokens")}</th>
          <th className="pb-2 font-medium">{t("colRelease")}</th>
        </tr>
      </thead>
      <tbody>
        {agents.map((a) => {
          const row = byId.get(a.id);
          const selected = scope !== AGENT_SCOPE_ALL && a.id === scope;
          const dimmed = scope !== AGENT_SCOPE_ALL && a.id !== scope;
          return (
            <tr key={a.id} className={rowClass(selected, dimmed)}>
              <td className="py-1.5 pr-3 font-medium">{a.name}</td>
              <td
                className={`py-1.5 pr-3 text-right tabular-nums ${
                  row?.toolErrors ? "text-red-300" : ""
                }`}
              >
                <PairCell
                  found={row?.toolErrors ?? null}
                  outOf={row?.toolTotal ?? null}
                  reason={row?.toolRefusal ?? null}
                  t={t}
                />
              </td>
              <td className="py-1.5 pr-3 text-right tabular-nums">{fmtSecs(a.latency_ms)}</td>
              <td
                className="py-1.5 pr-3 text-right tabular-nums"
                title={
                  row?.meanTokens != null
                    ? t("costMeanTitle", { mean: fmtInt(Math.round(row.meanTokens)) })
                    : undefined
                }
              >
                <CountCell
                  value={row?.totalTokens ?? null}
                  reason={row?.costRefusal ?? null}
                  t={t}
                />
              </td>
              <td className="py-1.5">
                <ReleaseCell agent={a} t={t} />
              </td>
            </tr>
          );
        })}
      </tbody>
      <DomainFoot fleet={fleet} t={t} span={4} />
    </table>
  );
}
