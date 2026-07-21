"use client";

import { useQuery } from "@tanstack/react-query";
import { Check, ChevronDown, Filter } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { Truncate } from "@/components/ui/truncate";
import { usePathname, useRouter } from "@/i18n/navigation";
import { AGENT_SCOPE_ALL, AGENT_SCOPE_PARAM, parseAgentScope } from "@/lib/agent-scope";
import { fetchFleet } from "@/lib/api/client";
import { cn } from "@/lib/cn";

/**
 * Global agent-scope filter for GOUVERNER / PLATEFORME surfaces.
 *
 * Distinct from the header {@link AgentSwitcher}: that one navigates the AGENT
 * section (path scope); this one writes `?agent=all|<id>` on the *current* page
 * (query scope) and never changes the route. Default is "Tous les agents" (the
 * deduplicated org view). Styled with a Filter icon + an explicit "Filtre" label
 * so an operator never confuses it with the AGENT switcher.
 */
export function AgentScopeFilter({ contentClassName }: { contentClassName?: string } = {}) {
  return (
    <Suspense fallback={<Skeleton className="h-8 w-[11rem] rounded-md" />}>
      <AgentScopeFilterInner contentClassName={contentClassName} />
    </Suspense>
  );
}

function AgentScopeFilterInner({ contentClassName }: { contentClassName?: string }) {
  const t = useTranslations("agentScope");
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const scope = parseAgentScope(searchParams.get(AGENT_SCOPE_PARAM));

  const { data } = useQuery({
    queryKey: ["fleet-scope-filter"],
    queryFn: ({ signal }) => fetchFleet(signal),
    staleTime: 60_000,
  });
  const agents = data?.agents ?? [];
  const current = agents.find((a) => a.id === scope);

  function select(next: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (next === AGENT_SCOPE_ALL) params.delete(AGENT_SCOPE_PARAM);
    else params.set(AGENT_SCOPE_PARAM, next);
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname);
  }

  const label = scope === AGENT_SCOPE_ALL ? t("all") : (current?.name ?? scope);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex h-8 items-center gap-2 rounded-md border border-dashed border-[var(--tessera-border-strong)] bg-[var(--tessera-surface-2)] px-2.5 text-[0.72rem] font-medium text-[var(--tessera-text)] transition-colors hover:bg-[var(--tessera-muted)]"
          title={t("hint")}
        >
          <Filter className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
          <span className="text-[var(--tessera-text-muted)]">{t("label")}</span>
          <Truncate full={label} className="max-w-[10rem]">
            {label}
          </Truncate>
          <ChevronDown className="h-3 w-3 text-[var(--tessera-text-muted)]" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className={cn("min-w-[14rem]", contentClassName)}>
        <DropdownMenuItem
          onSelect={() => select(AGENT_SCOPE_ALL)}
          className="flex items-center justify-between gap-3"
        >
          <span className="truncate">{t("all")}</span>
          {scope === AGENT_SCOPE_ALL ? <Check className="h-3.5 w-3.5 text-[#b9a6ff]" /> : null}
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {agents.map((a) => (
          <DropdownMenuItem
            key={a.id}
            onSelect={() => select(a.id)}
            className="flex items-center justify-between gap-3"
          >
            <Truncate full={a.name}>{a.name}</Truncate>
            {a.id === scope ? <Check className="h-3.5 w-3.5 text-[#b9a6ff]" /> : null}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
