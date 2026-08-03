import { getTranslations, setRequestLocale } from "next-intl/server";

import { FleetExplorer } from "@/components/agent/fleet-explorer";
import { NewAgentButton } from "@/components/agent/new-agent-button";
import { MetricInfo } from "@/components/cockpit/metric-info";
import { Link, redirect } from "@/i18n/navigation";
import { currentRole, hasCockpitAccess, isOperator } from "@/lib/auth/session";
import { loadFleet } from "@/lib/server/fleet";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export const dynamic = "force-dynamic";

const fmtInt = (n: number) => n.toLocaleString("fr-FR").replace(/ /g, " ");

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
  if (data === null) {
    const te = await getTranslations({ locale, namespace: "queryError" });
    return (
      <section
        role="alert"
        className="grid min-h-[280px] place-items-center rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-5 py-10 text-center shadow-[var(--shadow-card)]"
      >
        <div className="max-w-md">
          <h2 className="text-sm font-semibold text-[var(--tessera-text)]">{te("title")}</h2>
          <p className="mt-1.5 text-xs leading-relaxed text-[var(--tessera-text-muted)]">
            {te("detail")}
          </p>
          <Link
            href="/agents"
            className="mt-5 inline-flex h-8 items-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg-soft)] px-3 text-xs font-medium text-[var(--tessera-text)] transition-colors hover:bg-[var(--tessera-muted)]"
          >
            {te("retry")}
          </Link>
        </div>
      </section>
    );
  }
  const agents = data.agents ?? [];
  const org = data.org;
  // `window` is a DOM global in a browser bundle; the trailing underscore keeps this a page
  // fact rather than something that silently resolves to `globalThis.window` in a refactor.
  const window_ = data.window;

  return (
    <div className="flex flex-col gap-2.5 pb-2 text-[var(--tessera-text)]">
      {/* Org rollup — deduplicated (a shared conversation counts once). */}
      <section className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4">
        <div className="flex flex-wrap items-center gap-6">
          <div>
            <p className="flex items-center gap-1 text-[0.66rem] text-[var(--tessera-text-muted)]">
              {t("orgConversations")}
              <MetricInfo
                title={t("orgConversations")}
                what={t("explain.orgConversations.what")}
                how={t("explain.orgConversations.how")}
                source={t("explain.orgConversations.source")}
              />
            </p>
            <p className="text-[1.3rem] font-semibold tabular-nums">
              {org ? fmtInt(org.conversations) : "-"}
            </p>
          </div>
          <div>
            <p className="flex items-center gap-1 text-[0.66rem] text-[var(--tessera-text-muted)]">
              {t("naiveSum")}
              <MetricInfo
                title={t("naiveSum")}
                what={t("explain.naiveSum.what")}
                how={t("explain.naiveSum.how")}
              />
            </p>
            <p className="text-[1.3rem] font-semibold tabular-nums text-[var(--tessera-text-muted)]">
              {data ? fmtInt(data.naive_sum_conversations ?? 0) : "-"}
            </p>
          </div>
          <div>
            <p className="flex items-center gap-1 text-[0.66rem] text-[var(--tessera-text-muted)]">
              {t("dedupSaved")}
              <MetricInfo
                title={t("dedupSaved")}
                what={t("explain.dedupSaved.what")}
                how={t("explain.dedupSaved.how")}
                source={t("explain.dedupSaved.source")}
              />
            </p>
            <p className="text-[1.3rem] font-semibold tabular-nums text-[var(--tessera-fg-success)]">
              {fmtInt(data?.dedup_saved ?? 0)}
            </p>
            <p className="text-[0.6rem] text-[var(--tessera-text-muted)]">
              {fmtInt(data?.shared_conversations ?? 0)} {t("shared")}
            </p>
          </div>
        </div>
        {isOperator(role) ? <NewAgentButton /> : null}
      </section>

      {/* Which interval these numbers are about.
          This page reads ALL HISTORY; every SURVEILLER domain page reads a trailing 7 days.
          Both render the same payload shape, so an operator moving between them was comparing
          figures that were never the same measurement, with nothing on either screen saying
          so. The window now travels in the payload and is stated here. */}
      <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">
        {/* THREE states, not two. `window_ === undefined` means the payload did not say —
            an older cached snapshot, or a server that stopped emitting the field. Collapsing
            it into "all history" would rebuild, one level down, the very conflation this lot
            exists to remove: an unstated interval read as a stated one. */}
        {window_ === undefined
          ? t("windowUnknown")
          : window_.period_days === null
            ? t("windowAllHistory")
            : t("windowDays", { n: window_.period_days })}
      </p>

      {/* Rich agent directory — search · audience filters + counters · grid/list. */}
      <FleetExplorer agents={agents} />

      <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{t("releaseNote")}</p>
    </div>
  );
}
