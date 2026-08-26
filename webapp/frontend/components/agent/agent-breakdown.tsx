import type { Route } from "next";
import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { agentPath } from "@/lib/agent-context";
import type {
  AlarmLens,
  BreakdownLens,
  CellEmpty,
  ComplianceLens,
  ObservabilityLens,
  ProofLens,
  QualityLens,
  ReliabilityLens,
  SecurityLens,
} from "@/lib/agent-lens";
import { AGENT_SCOPE_ALL } from "@/lib/agent-scope";
import type { Fleet } from "@/lib/api/schemas";
import { COL_IDENTITY, COL_VERDICT, TABLE_BREAKDOWN } from "@/lib/breakdown-columns";
import { fmtRunDay } from "@/lib/eval-score";

/**
 * This table's numbers, in the language the page is being read in.
 *
 * Frozen for a day in `number-format-follows-the-reader.test.ts` with an honest reason: one
 * `fmtInt` shared by seven functions over seventeen call sites, and threading a locale through
 * every signature is a refactor rather than a sed. It is that refactor. Every helper is now
 * built ONCE per render from the locale the route already carries, and passed down as a single
 * `fmt` object — so twelve signatures gain one parameter instead of five.
 *
 * What was wrong: `toLocaleString("fr-FR")` and `.toFixed(1).replace(".", ",")` are the same
 * defect twice. Both are right in French and silently wrong for the German or English operator —
 * and the percentage sign moves too, which hand-gluing " %" cannot know (French and German space
 * it, English does not).
 */
interface Fmt {
  int: (n: number) => string;
  pct: (n: number) => string;
  secs: (ms: number | null) => string;
  rate: (r: number) => string;
  pp: (pp: number) => string;
}

function formatters(locale: string): Fmt {
  const int = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 });
  const one = new Intl.NumberFormat(locale, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  const percent = new Intl.NumberFormat(locale, {
    style: "percent",
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  return {
    int: (n) => int.format(n),
    // Takes a percentage (71.6), not a ratio, because that is what the callers hold; `rate`
    // below is the ratio door and goes through Intl's percent style, which places the sign.
    pct: (n) => percent.format(n / 100),
    secs: (ms) => (ms === null ? "—" : `${one.format(ms / 1000)} s`),
    rate: (r) => percent.format(r),
    // `signDisplay` rather than a hand-written "+": the minus sign is locale-dependent too, and
    // the previous version emitted a hard "+" beside an ASCII "-".
    pp: (v) =>
      `${new Intl.NumberFormat(locale, {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
        signDisplay: "exceptZero",
      }).format(v)} pt`,
  };
}

const RELEASE_TONE: Record<string, string> = {
  good: "text-[var(--tessera-fg-success)]",
  crit: "text-[var(--tessera-fg-danger)]",
  bad: "text-[var(--tessera-fg-warning)]",
  muted: "text-[var(--tessera-text-muted)]",
};

type Translator = Awaited<ReturnType<typeof getTranslations>>;
type FleetAgent = NonNullable<Fleet["agents"]>[number];

/**
 * The two clocks of the quality/alarm lenses, named as spanning column groups: what the rail
 * windows (the period group) vs what the release lane holds (the pre-launch group — the bench
 * verdict and its date, which never follow the period on purpose). The lens flip below only
 * ever swaps the CONTENT of the first group, so the card's skeleton is invariant: two columns
 * appear to explain an alert; the table never becomes a different table. Each label carries its
 * own hairline, inset by the padding, so the two brackets read as two — not one line across.
 */
function TwoClocksHead({ windowSpan, t }: { windowSpan: number; t: Translator }) {
  const bracket =
    "block border-b border-[var(--tessera-border)] pb-1 text-center text-[0.55rem] font-medium uppercase tracking-[0.08em] text-[var(--tessera-text-muted)]";
  return (
    <tr className="text-left">
      <th aria-hidden className="pb-1" />
      <th colSpan={windowSpan} className="px-3 pb-1">
        <span className={bracket}>{t("groupWindow")}</span>
      </th>
      <th colSpan={2} className="px-3 pb-1">
        <span className={bracket}>{t("groupRelease")}</span>
      </th>
    </tr>
  );
}

/**
 * The last-evaluation cell — the bench verdict's date, i.e. its provenance: a release
 * verdict without its date is unverifiable, so it rides beside the verdict column in BOTH
 * lens modes and, like the verdict, deliberately ignores the period rail.
 */
function EvalFreshnessCell({ agent, t }: { agent: FleetAgent; t: Translator }) {
  const rel = agent.release?.available ? agent.release : null;
  return (
    <td
      className={`py-1.5 text-center tabular-nums ${
        rel?.verdict_stale ? "text-[var(--tessera-fg-warning)]" : ""
      }`}
      title={rel?.verdict_stale ? t("staleEval") : undefined}
    >
      {rel ? fmtRunDay(rel.run_at) : "—"}
    </td>
  );
}

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
  // Built once per render from the route's locale, then threaded like `t`.
  const fmt = formatters(locale);
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
                : lens.kind === "proof"
                  ? t("proofNote")
                  : null;

  return (
    <section className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-[0.82rem] font-semibold">{t("breakdownTitle")}</h2>
        {note ? <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{note}</p> : null}
      </div>
      <div className="overflow-x-auto">
        {lens.kind === "alarm" ? (
          <AlarmTable fmt={fmt} lens={lens} agents={agents} scope={scope} t={t} fleet={fleet} />
        ) : lens.kind === "quality" ? (
          <QualityTable fmt={fmt} lens={lens} agents={agents} scope={scope} t={t} fleet={fleet} />
        ) : lens.kind === "security" ? (
          <SecurityTable fmt={fmt} lens={lens} agents={agents} scope={scope} t={t} fleet={fleet} />
        ) : lens.kind === "compliance" || lens.kind === "proof" ? (
          <ComplianceTable
            fmt={fmt}
            lens={lens}
            agents={agents}
            scope={scope}
            t={t}
            fleet={fleet}
          />
        ) : lens.kind === "reliability" ? (
          <ReliabilityTable
            fmt={fmt}
            lens={lens}
            agents={agents}
            scope={scope}
            t={t}
            fleet={fleet}
          />
        ) : lens.kind === "observability" ? (
          <ObservabilityTable
            fmt={fmt}
            lens={lens}
            agents={agents}
            scope={scope}
            t={t}
            fleet={fleet}
          />
        ) : (
          <MonitoringTable
            fmt={fmt}
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
  fmt,
}: {
  agents: FleetAgent[];
  scope: string;
  t: Translator;
  fleet: Fleet;
  attested: number;
  seenShared: number;
  handoffGap: number;
  fmt: Fmt;
}) {
  return (
    <div className="overflow-x-auto">
      <table data-breakdown="agent" className={TABLE_BREAKDOWN}>
        <thead>
          <tr className="text-left text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            <th className={`${COL_IDENTITY} pb-2 pr-3 font-medium`}>{t("colAgent")}</th>
            <th className="pb-2 text-center font-medium">{t("colVolume")}</th>
            <th className="pb-2 text-center font-medium">{t("colEscalation")}</th>
            <th className="pb-2 text-center font-medium">{t("colLatency")}</th>
            <th className="pb-2 text-center font-medium">{t("colHandoffs")}</th>
            {/* Prose, not a number: sized by `COL_VERDICT`, which explains why. */}
            <th className={`${COL_VERDICT} pb-2 pr-2 text-right font-medium`}>{t("colRelease")}</th>
          </tr>
        </thead>
        <tbody>
          {agents.map((a) => {
            const selected = scope !== AGENT_SCOPE_ALL && a.id === scope;
            const dimmed = scope !== AGENT_SCOPE_ALL && a.id !== scope;
            return (
              <tr key={a.id} className={rowClass(selected, dimmed)}>
                <td className="py-1.5 pr-3 font-medium">{a.name}</td>
                <td className="py-1.5 text-center tabular-nums">{fmt.int(a.conversations)}</td>
                <td className="py-1.5 text-center tabular-nums">{fmt.pct(a.escalation_rate)}</td>
                <td className="py-1.5 text-center tabular-nums">{fmt.secs(a.latency_ms)}</td>
                <td className="py-1.5 text-center tabular-nums">
                  {a.handoffs_in} / {a.handoffs_out}
                </td>
                <td className="py-1.5 pr-2 text-right">
                  <ReleaseCell agent={a} t={t} />
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          {/* Total org — DISTINCT entities, never the sum of the rows above. */}
          <tr className="border-t-2 border-[#7c5cf5]/40">
            <td className="py-2 pr-3 font-semibold text-[var(--tessera-fg-accent)]">
              {t("orgTotal")}
            </td>
            <td
              data-testid="fleet-org-total"
              className="py-2 text-center font-semibold tabular-nums text-[var(--tessera-fg-accent)]"
            >
              {fmt.int(fleet.org?.conversations ?? 0)}
            </td>
            <td
              colSpan={4}
              className="py-2 pr-2 text-right text-[0.62rem] text-[var(--tessera-text-muted)]"
            >
              <DedupFooter
                fmt={fmt}
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
    </div>
  );
}

/** The dedup + handoff reconciliation block — ONE implementation, shared by every lens. */
function DedupFooter({
  fleet,
  t,
  attested,
  seenShared,
  handoffGap,
  fmt,
}: {
  fleet: Fleet;
  t: Translator;
  attested: number;
  seenShared: number;
  handoffGap: number;
  fmt: Fmt;
}) {
  const total = fmt.int(fleet.org?.conversations ?? 0);

  if (attested === 0) {
    return <span className="block">{t("noHandoffSummary", { total })}</span>;
  }

  if (handoffGap > 0) {
    return (
      <span className="block text-[var(--tessera-fg-warning)]/90">
        {t("handoffGap", {
          events: fmt.int(fleet.handoff_events ?? 0),
          attested: fmt.int(attested),
          seen: fmt.int(seenShared),
        })}
      </span>
    );
  }

  return (
    <span className="block">
      {t(`handoffSummary.${attested === 1 ? "one" : "many"}`, {
        attested: fmt.int(attested),
        total,
      })}
    </span>
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
  fmt,
}: {
  lens: AlarmLens;
  agents: FleetAgent[];
  scope: string;
  t: Translator;
  fleet: Fleet;
  fmt: Fmt;
}) {
  const byId = new Map(agents.map((a) => [a.id, a]));
  const attested = fleet.handoff_conversations ?? 0;
  const seenShared = fleet.handoff_conversations_seen_shared ?? 0;
  return (
    <div className="overflow-x-auto">
      <table data-breakdown="agent" className={TABLE_BREAKDOWN}>
        <thead>
          <TwoClocksHead windowSpan={3} t={t} />
          <tr className="text-left text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            <th className={`${COL_IDENTITY} pb-2 pr-3 font-medium`}>{t("colAgent")}</th>
            {/* The measure keeps ONE name across both lens modes: the column holds the value
                by definition, so wrapping the metric label in a "value (…)" template only
                made the same fact change name when the table changed state. */}
            <th className="pb-2 text-center font-medium">{metricLabel(lens.metric, t)}</th>
            <th className="pb-2 text-center font-medium">{t("colSloGap")}</th>
            <th className="pb-2 text-center font-medium">{t("colContribution")}</th>
            <th className="pb-2 text-center font-medium">{t("colEvalFreshness")}</th>
            <th className={`${COL_VERDICT} pb-2 pr-2 text-right font-medium`}>{t("colRelease")}</th>
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
                {/* Same door as the quality lens: the alarm lens REPLACES it while a
                  signal burns, and the way to an agent's evaluations must not
                  disappear exactly when someone is investigating quality. */}
                <td className="py-1.5 pr-3 font-medium">
                  <Link
                    href={agentPath(a.id, "evaluations") as Route}
                    title={t("openEvaluations")}
                    className="hover:text-[var(--tessera-fg-accent)] hover:underline"
                  >
                    {a.name}
                  </Link>
                </td>
                <td className="py-1.5 text-center tabular-nums">
                  {row.value === null ? (
                    <EmptyCell reason={row.refusal} t={t} />
                  ) : (
                    fmt.rate(row.value)
                  )}
                </td>
                <td
                  className={`py-1.5 text-center tabular-nums ${
                    row.gapPp !== null && row.gapPp < 0 ? "text-[var(--tessera-fg-danger)]" : ""
                  }`}
                >
                  {row.gapPp === null ? (
                    <EmptyCell reason={row.refusal} t={t} />
                  ) : (
                    fmt.pp(row.gapPp)
                  )}
                </td>
                <td className="py-1.5 text-center tabular-nums">
                  {row.nBad === null ? (
                    <EmptyCell reason={row.refusal} t={t} />
                  ) : (
                    `${fmt.int(row.nBad)} / ${fmt.int(row.n ?? 0)}`
                  )}
                </td>
                <EvalFreshnessCell agent={a} t={t} />
                <td className="py-1.5 pr-2 text-right">
                  <ReleaseCell agent={a} t={t} />
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-[#7c5cf5]/40">
            <td className="py-2 pr-3 font-semibold text-[var(--tessera-fg-accent)]">
              {t("orgTotal")}
            </td>
            <td colSpan={2} className="py-2" />
            <td className="py-2 text-center font-semibold tabular-nums text-[var(--tessera-fg-accent)]">
              {lens.orgNBad === null || lens.orgN === null
                ? "—"
                : `${fmt.int(lens.orgNBad)} / ${fmt.int(lens.orgN)}`}
            </td>
            <td colSpan={2} className="py-2" />
          </tr>
          <tr>
            <td
              colSpan={6}
              className="pb-1 pr-2 text-right text-[0.62rem] text-[var(--tessera-text-muted)]"
            >
              {/* Contribution reconciliation — the per-agent slices vs the deduplicated org
                total. ∑ slices = org would be a coincidence, not a proof: a handed-off
                journey touches two agents and counts once in the org. A check that PASSES
                stays silent (operator decision 2026-08-25 — the reconciled sentence restated
                the table's own numbers as doctrine); a gap or an unverifiable total still
                speaks, so silence can only ever mean checked-and-equal. */}
              {lens.sumNBad !== null && lens.orgNBad !== null ? (
                lens.sumNBad === lens.orgNBad ? null : (
                  <span className="block text-[var(--tessera-fg-warning)]/90">
                    {t("contribGap", { sum: fmt.int(lens.sumNBad), org: fmt.int(lens.orgNBad) })}
                  </span>
                )
              ) : (
                <span className="block">{t("contribUnknown")}</span>
              )}
              <DedupFooter
                fmt={fmt}
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
    </div>
  );
}

/** The quality lens (no alarm): the page's own question, per agent. */
function QualityTable({
  lens,
  agents,
  scope,
  t,
  fleet,
  fmt,
}: {
  lens: QualityLens;
  agents: FleetAgent[];
  scope: string;
  t: Translator;
  fleet: Fleet;
  fmt: Fmt;
}) {
  const byId = new Map(lens.rows.map((r) => [r.agentId, r]));
  const attested = fleet.handoff_conversations ?? 0;
  const seenShared = fleet.handoff_conversations_seen_shared ?? 0;
  return (
    <div className="overflow-x-auto">
      <table data-breakdown="agent" className={TABLE_BREAKDOWN}>
        <thead>
          <TwoClocksHead windowSpan={2} t={t} />
          <tr className="text-left text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            <th className={`${COL_IDENTITY} pb-2 pr-3 font-medium`}>{t("colAgent")}</th>
            <th className="pb-2 text-center font-medium">{t("colFaithfulness")}</th>
            <th className="pb-2 text-center font-medium">{t("colHallucination")}</th>
            <th className="pb-2 text-center font-medium">{t("colEvalFreshness")}</th>
            <th className={`${COL_VERDICT} pb-2 pr-2 text-right font-medium`}>{t("colRelease")}</th>
          </tr>
        </thead>
        <tbody>
          {agents.map((a) => {
            const row = byId.get(a.id);
            const selected = scope !== AGENT_SCOPE_ALL && a.id === scope;
            const dimmed = scope !== AGENT_SCOPE_ALL && a.id !== scope;
            return (
              <tr key={a.id} className={rowClass(selected, dimmed)}>
                {/* The quality lens answers "how is THIS agent evaluated?" — the row is
                  the door to the agent's own Évaluations page (ER-01 run rail). */}
                <td className="py-1.5 pr-3 font-medium">
                  <Link
                    href={agentPath(a.id, "evaluations") as Route}
                    title={t("openEvaluations")}
                    className="hover:text-[var(--tessera-fg-accent)] hover:underline"
                  >
                    {a.name}
                  </Link>
                </td>
                <td className="py-1.5 text-center tabular-nums">
                  {row?.faithfulness == null ? (
                    <EmptyCell reason={row?.faithfulnessRefusal ?? "absent"} t={t} />
                  ) : (
                    fmt.rate(row.faithfulness)
                  )}
                </td>
                <td className="py-1.5 text-center tabular-nums">
                  {row?.hallucination == null ? (
                    <EmptyCell reason={row?.hallucinationRefusal ?? "absent"} t={t} />
                  ) : (
                    fmt.rate(row.hallucination)
                  )}
                </td>
                {/* The bench's internals (blocking failures, cases passed) left this view:
                    they are the evaluations view's work, one click through the row's own
                    door. Only the verdict and its date remain — the second clock, named. */}
                <EvalFreshnessCell agent={a} t={t} />
                <td className="py-1.5 pr-2 text-right">
                  <ReleaseCell agent={a} t={t} />
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-[#7c5cf5]/40">
            <td className="py-2 pr-3 font-semibold text-[var(--tessera-fg-accent)]">
              {t("orgTotal")}
            </td>
            <td
              colSpan={4}
              className="py-2 pr-2 text-right text-[0.62rem] text-[var(--tessera-text-muted)]"
            >
              <DedupFooter
                fmt={fmt}
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
    </div>
  );
}

/** A "found / screened" pair, or the honest empty cell naming why. */
function PairCell({
  found,
  outOf,
  reason,
  t,
  fmt,
}: {
  found: number | null;
  outOf: number | null;
  reason: CellEmpty | null;
  t: Translator;
  fmt: Fmt;
}) {
  if (found === null || outOf === null) return <EmptyCell reason={reason ?? "absent"} t={t} />;
  return (
    <>
      {fmt.int(found)} / {fmt.int(outOf)}
    </>
  );
}

/** A plain count. 0 is a measured fact and renders as 0 — only an unproven read refuses. */
function CountCell({
  value,
  reason,
  t,
  fmt,
}: {
  value: number | null;
  reason: CellEmpty | null;
  t: Translator;
  fmt: Fmt;
}) {
  if (value === null) return <EmptyCell reason={reason ?? "absent"} t={t} />;
  return <>{fmt.int(value)}</>;
}

/** The shared tfoot of the domain lens tables: org total + the dedup/handoff reconciliation. */
function DomainFoot({
  fleet,
  t,
  span,
  fmt,
}: { fleet: Fleet; t: Translator; span: number; fmt: Fmt }) {
  const attested = fleet.handoff_conversations ?? 0;
  const seenShared = fleet.handoff_conversations_seen_shared ?? 0;
  return (
    <tfoot>
      <tr className="border-t-2 border-[#7c5cf5]/40">
        <td className="py-2 pr-3 font-semibold text-[var(--tessera-fg-accent)]">{t("orgTotal")}</td>
        <td
          colSpan={span}
          className="py-2 pr-2 text-right text-[0.62rem] text-[var(--tessera-text-muted)]"
        >
          <DedupFooter
            fmt={fmt}
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
  fmt,
}: {
  lens: SecurityLens;
  agents: FleetAgent[];
  scope: string;
  t: Translator;
  fleet: Fleet;
  fmt: Fmt;
}) {
  const byId = new Map(lens.rows.map((r) => [r.agentId, r]));
  return (
    <div className="overflow-x-auto">
      <table data-breakdown="agent" className={TABLE_BREAKDOWN}>
        <thead>
          <tr className="text-left text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            <th className={`${COL_IDENTITY} pb-2 pr-3 font-medium`}>{t("colAgent")}</th>
            <th className="pb-2 text-center font-medium">{t("colPiiLeaks")}</th>
            <th className="pb-2 text-center font-medium">{t("colToxicity")}</th>
            <th className="pb-2 text-center font-medium">{t("colGuardDenied")}</th>
            <th className={`${COL_VERDICT} pb-2 pr-2 text-right font-medium`}>{t("colRelease")}</th>
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
                  className={`py-1.5 text-center tabular-nums ${
                    row?.piiLeaks ? "text-[var(--tessera-fg-danger)]" : ""
                  }`}
                >
                  <PairCell
                    fmt={fmt}
                    found={row?.piiLeaks ?? null}
                    outOf={row?.piiN ?? null}
                    reason={row?.piiRefusal ?? null}
                    t={t}
                  />
                </td>
                <td
                  className={`py-1.5 text-center tabular-nums ${
                    row?.toxCount ? "text-[var(--tessera-fg-danger)]" : ""
                  }`}
                >
                  <PairCell
                    fmt={fmt}
                    found={row?.toxCount ?? null}
                    outOf={row?.toxN ?? null}
                    reason={row?.toxRefusal ?? null}
                    t={t}
                  />
                </td>
                <td className="py-1.5 text-center tabular-nums">
                  <PairCell
                    fmt={fmt}
                    found={row?.guardDenied ?? null}
                    outOf={row?.guardTotal ?? null}
                    reason={row?.guardRefusal ?? null}
                    t={t}
                  />
                </td>
                <td className="py-1.5 pr-2 text-right">
                  <ReleaseCell agent={a} t={t} />
                </td>
              </tr>
            );
          })}
        </tbody>
        <DomainFoot fmt={fmt} fleet={fleet} t={t} span={4} />
      </table>
    </div>
  );
}

/**
 * The compliance lens (Conformité) — and the proof lens (Journal d'audit), which reads the
 * SAME two per-agent counts: governed acts and ledger entries (counts — an honest 0 is
 * data), plus the fleet's own per-agent escalation rate, the same fact the monitoring lens
 * renders. Ledger INTEGRITY is org-wide by construction: not a column in either.
 */
function ComplianceTable({
  lens,
  agents,
  scope,
  t,
  fleet,
  fmt,
}: {
  lens: ComplianceLens | ProofLens;
  agents: FleetAgent[];
  scope: string;
  t: Translator;
  fleet: Fleet;
  fmt: Fmt;
}) {
  const byId = new Map(lens.rows.map((r) => [r.agentId, r]));
  return (
    <div className="overflow-x-auto">
      <table data-breakdown="agent" className={TABLE_BREAKDOWN}>
        <thead>
          <tr className="text-left text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            <th className={`${COL_IDENTITY} pb-2 pr-3 font-medium`}>{t("colAgent")}</th>
            <th className="pb-2 text-center font-medium">{t("colGovernedActs")}</th>
            <th className="pb-2 text-center font-medium">{t("colLedgerEntries")}</th>
            <th className="pb-2 text-center font-medium">{t("colEscalation")}</th>
            <th className={`${COL_VERDICT} pb-2 pr-2 text-right font-medium`}>{t("colRelease")}</th>
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
                <td className="py-1.5 text-center tabular-nums">
                  <CountCell
                    fmt={fmt}
                    value={row?.governedActs ?? null}
                    reason={row?.governedRefusal ?? null}
                    t={t}
                  />
                </td>
                <td className="py-1.5 text-center tabular-nums">
                  <CountCell
                    fmt={fmt}
                    value={row?.ledgerEntries ?? null}
                    reason={row?.ledgerRefusal ?? null}
                    t={t}
                  />
                </td>
                <td className="py-1.5 text-center tabular-nums">{fmt.pct(a.escalation_rate)}</td>
                <td className="py-1.5 pr-2 text-right">
                  <ReleaseCell agent={a} t={t} />
                </td>
              </tr>
            );
          })}
        </tbody>
        <DomainFoot fmt={fmt} fleet={fleet} t={t} span={4} />
      </table>
    </div>
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
  fmt,
}: {
  lens: ObservabilityLens;
  agents: FleetAgent[];
  scope: string;
  t: Translator;
  fleet: Fleet;
  fmt: Fmt;
}) {
  const byId = new Map(lens.rows.map((r) => [r.agentId, r]));
  return (
    <div className="overflow-x-auto">
      <table data-breakdown="agent" className={TABLE_BREAKDOWN}>
        <thead>
          <tr className="text-left text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            <th className={`${COL_IDENTITY} pb-2 pr-3 font-medium`}>{t("colAgent")}</th>
            <th className="pb-2 text-center font-medium">{t("colAnomalies")}</th>
            <th className="pb-2 text-center font-medium">{t("colConformance")}</th>
            <th className={`${COL_VERDICT} pb-2 pr-2 text-right font-medium`}>{t("colRelease")}</th>
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
                  className={`py-1.5 text-center tabular-nums ${
                    row?.anomalous ? "text-[var(--tessera-fg-danger)]" : ""
                  }`}
                >
                  <PairCell
                    fmt={fmt}
                    found={row?.anomalous ?? null}
                    outOf={row?.sessions ?? null}
                    reason={row?.anomaliesRefusal ?? null}
                    t={t}
                  />
                </td>
                <td
                  className={`py-1.5 text-center tabular-nums ${
                    row?.violations ? "text-[var(--tessera-fg-danger)]" : ""
                  }`}
                >
                  <PairCell
                    fmt={fmt}
                    found={row?.violations ?? null}
                    outOf={row?.calls ?? null}
                    reason={row?.conformanceRefusal ?? null}
                    t={t}
                  />
                </td>
                <td className="py-1.5 pr-2 text-right">
                  <ReleaseCell agent={a} t={t} />
                </td>
              </tr>
            );
          })}
        </tbody>
        <DomainFoot fmt={fmt} fleet={fleet} t={t} span={3} />
      </table>
    </div>
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
  fmt,
}: {
  lens: ReliabilityLens;
  agents: FleetAgent[];
  scope: string;
  t: Translator;
  fleet: Fleet;
  fmt: Fmt;
}) {
  const byId = new Map(lens.rows.map((r) => [r.agentId, r]));
  return (
    <div className="overflow-x-auto">
      <table data-breakdown="agent" className={TABLE_BREAKDOWN}>
        <thead>
          <tr className="text-left text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            <th className={`${COL_IDENTITY} pb-2 pr-3 font-medium`}>{t("colAgent")}</th>
            <th className="pb-2 text-center font-medium">{t("colToolErrors")}</th>
            <th className="pb-2 text-center font-medium">{t("colLatency")}</th>
            <th className="pb-2 text-center font-medium">{t("colCostTokens")}</th>
            <th className={`${COL_VERDICT} pb-2 pr-2 text-right font-medium`}>{t("colRelease")}</th>
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
                  className={`py-1.5 text-center tabular-nums ${
                    row?.toolErrors ? "text-[var(--tessera-fg-danger)]" : ""
                  }`}
                >
                  <PairCell
                    fmt={fmt}
                    found={row?.toolErrors ?? null}
                    outOf={row?.toolTotal ?? null}
                    reason={row?.toolRefusal ?? null}
                    t={t}
                  />
                </td>
                <td className="py-1.5 text-center tabular-nums">{fmt.secs(a.latency_ms)}</td>
                <td
                  className="py-1.5 text-center tabular-nums"
                  title={
                    row?.meanTokens != null
                      ? t("costMeanTitle", { mean: fmt.int(Math.round(row.meanTokens)) })
                      : undefined
                  }
                >
                  <CountCell
                    fmt={fmt}
                    value={row?.totalTokens ?? null}
                    reason={row?.costRefusal ?? null}
                    t={t}
                  />
                </td>
                <td className="py-1.5 pr-2 text-right">
                  <ReleaseCell agent={a} t={t} />
                </td>
              </tr>
            );
          })}
        </tbody>
        <DomainFoot fmt={fmt} fleet={fleet} t={t} span={4} />
      </table>
    </div>
  );
}
