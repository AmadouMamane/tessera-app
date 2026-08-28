"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Users } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { AGENT_SCOPE_PARAM, parseAgentScope } from "@/lib/agent-scope";
import { fetchCatalogueConsumers } from "@/lib/api/client";

const VERDICT_DOT: Record<string, string> = {
  good: "bg-emerald-400",
  crit: "bg-red-400",
  bad: "bg-amber-400",
  muted: "bg-[var(--tessera-text-muted)]",
};

/**
 * CONFIGURER "used-by" panel — the inverse of the AGENT instance binding.
 *
 * For one catalogue `kind` (model, guardrails, knowledge…), list each shared item
 * and the agents that consume it, with each consumer's release verdict. Changing a
 * shared definition therefore shows its blast radius: the consuming agents must be
 * **re-validated** (re-gated). Respects the global `?agent=` filter. Real data from
 * the governed registry bindings; honest empty state when none.
 */
export function CatalogueConsumers({ kind }: { kind: string }) {
  return (
    <Suspense
      fallback={
        <div className="flex flex-col gap-2.5">
          <Skeleton className="h-24 w-full rounded-lg" />
          <Skeleton className="h-24 w-full rounded-lg" />
        </div>
      }
    >
      <CatalogueConsumersInner kind={kind} />
    </Suspense>
  );
}

function CatalogueConsumersInner({ kind }: { kind: string }) {
  const t = useTranslations("usedBy");
  const locale = useLocale();
  const searchParams = useSearchParams();
  const scope = parseAgentScope(searchParams.get(AGENT_SCOPE_PARAM));

  const { data, isLoading, isError } = useQuery({
    queryKey: ["catalogue-consumers", kind, scope, locale],
    queryFn: ({ signal }) => fetchCatalogueConsumers(kind, scope, locale, signal),
    staleTime: 60_000,
  });

  const items = data?.items ?? [];

  if (isLoading) {
    return <p className="text-xs text-[var(--tessera-text-muted)]">{t("loading")}</p>;
  }
  if (isError || !data?.available || items.length === 0) {
    return (
      <p className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4 text-xs text-[var(--tessera-text-muted)]">
        {t("empty")}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2.5">
      {items.map((it) => (
        <section
          key={it.item}
          className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4"
        >
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <span className="font-mono text-[0.82rem] font-semibold">{it.item}</span>
            <span className="flex items-center gap-3 text-xs text-[var(--tessera-text-muted)]">
              <span className="inline-flex items-center gap-1">
                <Users className="h-3.5 w-3.5" />
                {t("consumers", { count: it.consumer_count })}
              </span>
              {it.regate_count > 0 ? (
                <span className="inline-flex items-center gap-1 text-[var(--tessera-fg-warning)]">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  {t("regate", { count: it.regate_count })}
                </span>
              ) : null}
            </span>
          </div>
          <ul className="flex flex-wrap gap-2">
            {it.consumers.map((c) => (
              <li
                key={c.agent_id}
                className="inline-flex items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface-2)] px-2 py-1 text-xs"
                title={c.release.verdict_label}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    VERDICT_DOT[c.release.verdict_tone] ?? VERDICT_DOT.muted
                  }`}
                />
                {c.name}
              </li>
            ))}
          </ul>
        </section>
      ))}
      <p className="text-xs text-[var(--tessera-text-muted)]">{t("note")}</p>
    </div>
  );
}
