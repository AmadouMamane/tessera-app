import { getTranslations, setRequestLocale } from "next-intl/server";

import { FleetExplorer } from "@/components/agent/fleet-explorer";
import { NewAgentButton } from "@/components/agent/new-agent-button";
import { redirect } from "@/i18n/navigation";
import { FleetSchema } from "@/lib/api/schemas";
import { currentRole, hasCockpitAccess, isOperator } from "@/lib/auth/session";
import { backendHeaders, backendUrl } from "@/lib/server/backend";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export const dynamic = "force-dynamic";

const fmtInt = (n: number) => n.toLocaleString("fr-FR").replace(/ /g, " ");

async function loadFleet(locale: string) {
  try {
    const res = await fetch(
      `${backendUrl()}/observability/fleet?lang=${encodeURIComponent(locale)}`,
      {
        cache: "no-store",
        headers: backendHeaders({ Accept: "application/json" }),
      },
    );
    if (!res.ok) return null;
    return FleetSchema.parse(await res.json());
  } catch {
    return null;
  }
}

// The Flotte — the rich agent directory. Listing every agent is correct HERE
// (this is the cockpit / control plane); a click opens the agent's governance
// workspace, never a chat. The business plane (/produit, /espaces) never shows an
// agent picker — the supervisor routes the customer (ADR 0008/0010/0013).
export default async function FleetPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const role = await currentRole();
  if (!hasCockpitAccess(role)) redirect({ href: "/produit", locale });

  const t = await getTranslations({ locale, namespace: "fleet" });
  const data = await loadFleet(locale);
  const agents = data?.agents ?? [];
  const org = data?.org;

  return (
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

      {/* Rich agent directory — search · audience filters + counters · grid/list. */}
      <FleetExplorer agents={agents} />

      <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{t("releaseNote")}</p>
      <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{t("judgedNote")}</p>
    </div>
  );
}
