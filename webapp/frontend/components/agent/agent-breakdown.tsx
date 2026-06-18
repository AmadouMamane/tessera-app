import { getTranslations } from "next-intl/server";

import type { Fleet } from "@/lib/api/schemas";
import { AGENT_SCOPE_ALL } from "@/lib/agent-scope";

const fmtInt = (n: number) => n.toLocaleString("fr-FR").replace(/ /g, " ");
const fmtPct = (n: number) => `${n.toFixed(1).replace(".", ",")} %`;
const fmtSecs = (ms: number | null) =>
  ms === null ? "—" : `${(ms / 1000).toFixed(1).replace(".", ",")} s`;

const RELEASE_TONE: Record<string, string> = {
  good: "text-emerald-300",
  crit: "text-red-300",
  bad: "text-amber-300",
  muted: "text-[var(--tessera-text-muted)]",
};

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
 * Only **observable** KPIs that genuinely differ per agent are shown (volume,
 * escalation, latency, handoffs, release verdict). Judged quality stays shared
 * until per-agent eval — see the fleet note.
 */
export async function AgentBreakdown({
  fleet,
  scope,
  locale,
}: {
  fleet: Fleet | null;
  scope: string;
  locale: string;
}) {
  const t = await getTranslations({ locale, namespace: "agentScope" });
  const agents = fleet?.agents ?? [];

  if (!fleet || agents.length === 0) {
    return (
      <section className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4">
        <h2 className="text-[0.82rem] font-semibold">{t("breakdownTitle")}</h2>
        <p className="mt-2 text-[0.72rem] text-[var(--tessera-text-muted)]">{t("empty")}</p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-[0.82rem] font-semibold">{t("breakdownTitle")}</h2>
        <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{t("breakdownNote")}</p>
      </div>
      <div className="overflow-x-auto">
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
                <tr
                  key={a.id}
                  className={`border-t border-[var(--tessera-border)] ${
                    selected ? "bg-[#7c5cf5]/10" : ""
                  } ${dimmed ? "opacity-45" : ""}`}
                >
                  <td className="py-1.5 pr-3 font-medium">{a.name}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{fmtInt(a.conversations)}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">
                    {fmtPct(a.escalation_rate)}
                  </td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{fmtSecs(a.latency_ms)}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">
                    {a.handoffs_in} / {a.handoffs_out}
                  </td>
                  <td className="py-1.5">
                    <span
                      className={
                        RELEASE_TONE[a.release?.verdict_tone ?? "muted"] ?? RELEASE_TONE.muted
                      }
                    >
                      {a.release?.available ? a.release.verdict_label : t("releaseNotRun")}
                    </span>
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
              <td colSpan={4} className="py-2 text-right text-[0.62rem] text-[var(--tessera-text-muted)]">
                {t("dedupExplain", {
                  naive: fmtInt(fleet.naive_sum_conversations ?? 0),
                  saved: fmtInt(fleet.dedup_saved ?? 0),
                  shared: fmtInt(fleet.shared_conversations ?? 0),
                })}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}
