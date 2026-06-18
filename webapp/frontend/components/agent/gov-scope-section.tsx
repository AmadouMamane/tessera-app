import { getTranslations } from "next-intl/server";

import { AgentBreakdown } from "@/components/agent/agent-breakdown";
import { AgentScopeFilter } from "@/components/agent/agent-scope-filter";
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
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <AgentScopeFilter />
        <span className="text-[0.62rem] text-[var(--tessera-text-muted)]">{t("hint")}</span>
      </div>
      <AgentBreakdown fleet={fleet} scope={scope} locale={locale} />
      {signalsNote ? (
        <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{t("orgSignalsNote")}</p>
      ) : null}
    </div>
  );
}
