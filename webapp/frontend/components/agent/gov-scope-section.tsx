import type { Route } from "next";
import { getTranslations } from "next-intl/server";

import { AgentBreakdown } from "@/components/agent/agent-breakdown";
import { AgentScopeFilter } from "@/components/agent/agent-scope-filter";
import { Link } from "@/i18n/navigation";
import { AGENT_SCOPE_ALL } from "@/lib/agent-scope";
import type { Fleet } from "@/lib/api/schemas";

/**
 * Reusable GOUVERNER / PLATEFORME header section: the global agent-scope filter +
 * the per-agent breakdown + the honest "org signals not yet per-agent" banner.
 *
 * Drop it at the top of any global surface so the multi-agent dimension (filter,
 * deduplicated org total, per-agent breakdown) is consistent everywhere — distinct
 * from the AGENT switcher. Pass `signalsNote={false}` where the page below is
 * already fully per-agent and the banner would be misleading.
 */
export async function GovScopeSection({
  fleet,
  scope,
  locale,
  signalsNote = true,
}: {
  fleet: Fleet | null;
  scope: string;
  locale: string;
  signalsNote?: boolean;
}) {
  const t = await getTranslations({ locale, namespace: "agentScope" });
  const q = scope !== AGENT_SCOPE_ALL ? `?agent=${scope}` : "";
  // P3 — cockpit cross-links, scope-carrying, making GOUVERNER/PLATEFORME navigable.
  const links: { href: Route; label: string }[] = [
    { href: (`/agir/release-control${q}`) as Route, label: t("linkRelease") },
    { href: (`/prouver/audit-logs${q}`) as Route, label: t("linkAudit") },
    { href: "/configurer/signal-catalog" as Route, label: t("linkSignals") },
  ];
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <AgentScopeFilter />
        <span className="text-[0.62rem] text-[var(--tessera-text-muted)]">{t("hint")}</span>
      </div>
      <AgentBreakdown fleet={fleet} scope={scope} locale={locale} />
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[10px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
          {t("usefulLinks")}
        </span>
        {links.map((l) => (
          <Link
            key={l.label}
            href={l.href}
            className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface-2)] px-2 py-1 text-[11px] text-[var(--tessera-text)] transition-colors hover:border-[#7c5cf5]/50 hover:text-white"
          >
            {l.label} →
          </Link>
        ))}
      </div>
      {signalsNote ? (
        <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{t("orgSignalsNote")}</p>
      ) : null}
    </div>
  );
}
