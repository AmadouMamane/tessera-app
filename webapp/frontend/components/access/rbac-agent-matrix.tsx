"use client";

import { useQuery } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { AGENT_SCOPE_PARAM, parseAgentScope } from "@/lib/agent-scope";
import { fetchRbacMatrix } from "@/lib/api/client";

/**
 * RBAC role × agent matrix (multi-agent, Tier 3).
 *
 * Real roles (the enforced auth model) × real registry agents. The enforced roles
 * are currently org-wide, so every cell reads "org" — stated truthfully rather than
 * fabricating per-agent grants. Respects the global `?agent=` filter. The per-agent
 * role-binding store is a logged follow-up.
 */
export function RbacAgentMatrix() {
  return (
    <Suspense
      fallback={
        <section className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4">
          <Skeleton className="h-4 w-40 rounded" />
          <Skeleton className="mt-4 h-32 w-full rounded" />
        </section>
      }
    >
      <RbacAgentMatrixInner />
    </Suspense>
  );
}

function RbacAgentMatrixInner() {
  const t = useTranslations("rbac");
  const searchParams = useSearchParams();
  const scope = parseAgentScope(searchParams.get(AGENT_SCOPE_PARAM));

  const { data, isLoading, isError } = useQuery({
    queryKey: ["rbac-matrix", scope],
    queryFn: ({ signal }) => fetchRbacMatrix(scope, signal),
    staleTime: 60_000,
  });

  const roles = data?.roles ?? [];
  const agents = data?.agents ?? [];

  if (isLoading) {
    return <p className="text-[0.72rem] text-[var(--tessera-text-muted)]">{t("loading")}</p>;
  }
  if (isError || !data?.available || roles.length === 0 || agents.length === 0) {
    return (
      <section className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4">
        <h2 className="text-[0.82rem] font-semibold">{t("title")}</h2>
        <p className="mt-2 text-[0.72rem] text-[var(--tessera-text-muted)]">{t("empty")}</p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-[0.82rem] font-semibold">{t("title")}</h2>
        <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{t("orgNote")}</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[0.72rem]">
          <thead>
            <tr className="text-left text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              <th className="pb-2 pr-3 font-medium">{t("role")}</th>
              {agents.map((a) => (
                <th key={a.id} className="pb-2 pr-3 text-center font-medium">
                  {a.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {roles.map((r) => (
              <tr key={r.role} className="border-t border-[var(--tessera-border)]">
                <td className="py-2 pr-3">
                  <span className="font-medium">{r.label}</span>
                  <span className="ml-2 text-[0.58rem] text-[var(--tessera-text-muted)]">
                    {r.caps.join(" · ")}
                  </span>
                </td>
                {r.cells.map((c) => (
                  <td key={c.agent_id} className="py-2 pr-3 text-center">
                    <span className="inline-flex items-center gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface-2)] px-1.5 py-0.5 text-[0.58rem]">
                      <Check className="h-3 w-3 text-emerald-400" />
                      {t("scopeOrg")}
                    </span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[0.6rem] text-[var(--tessera-text-muted)]">{t("followup")}</p>
    </section>
  );
}
