import { ArrowRight, Bot } from "lucide-react";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { NewAgentButton } from "@/components/agent/new-agent-button";
import { AppShell } from "@/components/layout/app-shell";
import { redirect } from "@/i18n/navigation";
import { Link } from "@/i18n/navigation";
import { agentPath } from "@/lib/agent-context";
import { FleetSchema } from "@/lib/api/schemas";
import { currentRole, hasCockpitAccess, isOperator } from "@/lib/auth/session";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export const dynamic = "force-dynamic";

const HEALTH: Record<string, { dot: string; label: string }> = {
  good: { dot: "bg-emerald-400", label: "Sain" },
  warn: { dot: "bg-amber-400", label: "À surveiller" },
  crit: { dot: "bg-red-400", label: "Critique" },
};

const fmtInt = (n: number) => n.toLocaleString("fr-FR").replace(/ /g, " ");
const fmtSecs = (ms: number | null) =>
  ms === null ? "-" : `${(ms / 1000).toFixed(1).replace(".", ",")} s`;

async function loadFleet() {
  try {
    const res = await fetch(`${backendUrl()}/observability/fleet`, {
      cache: "no-store",
      headers: backendHeaders({ Accept: "application/json" }),
    });
    if (!res.ok) return null;
    return FleetSchema.parse(await res.json());
  } catch {
    return null;
  }
}

export default async function FleetPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const role = await currentRole();
  if (!hasCockpitAccess(role)) redirect({ href: "/produit", locale });

  const t = await getTranslations({ locale, namespace: "fleet" });
  const data = await loadFleet();
  const agents = data?.agents ?? [];
  const org = data?.org;

  return (
    <AppShell title={t("title")} description={t("subtitle")} contentWidth="full">
      <div className="flex flex-col gap-3 pb-2 text-[var(--tessera-text)]">
        {/* Org rollup — deduplicated (a shared conversation counts once). */}
        <section className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4">
          <div className="flex flex-wrap items-center gap-6">
            <div>
              <p className="text-[0.66rem] text-[var(--tessera-text-muted)]">
                {t("orgConversations")}
              </p>
              <p className="text-[1.3rem] font-semibold tabular-nums">
                {org ? fmtInt(org.conversations) : "-"}
              </p>
            </div>
            <div>
              <p className="text-[0.66rem] text-[var(--tessera-text-muted)]">{t("naiveSum")}</p>
              <p className="text-[1.3rem] font-semibold tabular-nums text-[var(--tessera-text-muted)]">
                {data ? fmtInt(data.naive_sum_conversations ?? 0) : "-"}
              </p>
            </div>
            <div>
              <p className="text-[0.66rem] text-[var(--tessera-text-muted)]">{t("dedupSaved")}</p>
              <p className="text-[1.3rem] font-semibold tabular-nums text-emerald-300">
                {fmtInt(data?.dedup_saved ?? 0)}
              </p>
              <p className="text-[0.6rem] text-[var(--tessera-text-muted)]">
                {fmtInt(data?.shared_conversations ?? 0)} {t("shared")}
              </p>
            </div>
          </div>
          {isOperator(role) ? <NewAgentButton /> : null}
        </section>

        {/* Per-agent fleet table */}
        <div className="grid gap-2.5 md:grid-cols-2 xl:grid-cols-3">
          {agents.map((a) => {
            const health = HEALTH[a.health] ?? { dot: "bg-amber-400", label: "—" };
            return (
              <Link
                key={a.id}
                href={agentPath(a.id, "synthese")}
                className="group flex flex-col gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4 transition-colors hover:border-[#7c5cf5]/50"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="flex min-w-0 items-center gap-2">
                    <Bot className="h-4 w-4 shrink-0 text-[#b9a6ff]" />
                    <span className="truncate font-semibold">{a.name}</span>
                  </span>
                  <span className="inline-flex shrink-0 items-center gap-1.5 text-[0.66rem] text-[var(--tessera-text-muted)]">
                    <span className={`h-2 w-2 rounded-full ${health.dot}`} /> {health.label}
                  </span>
                </div>
                <p className="text-[0.66rem] text-[var(--tessera-text-muted)]">{a.owner}</p>
                <dl className="grid grid-cols-2 gap-2 text-[0.72rem]">
                  <Stat label={t("volume")} value={`${fmtInt(a.conversations)} conv.`} />
                  <Stat label={t("latency")} value={fmtSecs(a.latency_ms)} />
                  <Stat
                    label={t("escalation")}
                    value={`${a.escalation_rate.toFixed(1).replace(".", ",")} %`}
                  />
                  <Stat label={t("handoffs")} value={`${a.handoffs_in} / ${a.handoffs_out}`} />
                </dl>
                <span className="mt-1 inline-flex items-center gap-1 self-start text-[0.66rem] text-[#b9a6ff] group-hover:text-white">
                  {t("open")} <ArrowRight className="h-3 w-3" />
                </span>
              </Link>
            );
          })}
        </div>
        <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{t("judgedNote")}</p>
      </div>
    </AppShell>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[0.6rem] text-[var(--tessera-text-muted)]">{label}</dt>
      <dd className="font-medium tabular-nums text-[var(--tessera-text)]">{value}</dd>
    </div>
  );
}
