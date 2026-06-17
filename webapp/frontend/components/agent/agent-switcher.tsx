"use client";

import { useQuery } from "@tanstack/react-query";
import { Bot, Check, ChevronDown, Network } from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { agentPath } from "@/lib/agent-context";
import { fetchFleet } from "@/lib/api/client";
import { useAgentId } from "@/lib/use-agent-id";

/**
 * Header agent switcher for the AGENT section — scopes every AGENT page to the
 * selected agent. Selecting an agent navigates to the same sub-page under the new
 * agent (URL-driven; the scope change is live). "Tous les agents →" opens the
 * fleet. The customer never sees this; it is operator chrome.
 */
export function AgentSwitcher() {
  const agentId = useAgentId();
  const pathname = usePathname();
  const router = useRouter();
  const { data } = useQuery({
    queryKey: ["fleet-switcher"],
    queryFn: ({ signal }) => fetchFleet(signal),
    staleTime: 60_000,
  });

  const agents = data?.agents ?? [];
  const current = agents.find((a) => a.id === agentId);
  // The sub-page after /agents/<id>/ (e.g. "synthese"), to keep the user on the
  // same page when switching agents.
  const match = pathname.match(/\/agents\/[^/]+\/(.+)$/);
  const page = match?.[1] ?? "synthese";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border-strong)] bg-[var(--tessera-surface)] px-3 text-[0.78rem] font-medium text-[var(--tessera-text)] transition-colors hover:bg-[var(--tessera-muted)]"
        >
          <Bot className="h-4 w-4 text-[#b9a6ff]" />
          <span className="max-w-[12rem] truncate">{current?.name ?? agentId}</span>
          <ChevronDown className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="min-w-[15rem]">
        {agents.map((a) => (
          <DropdownMenuItem
            key={a.id}
            onSelect={() => router.push(agentPath(a.id, page))}
            className="flex items-center justify-between gap-3"
          >
            <span className="flex min-w-0 items-center gap-2">
              <Bot className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)]" />
              <span className="truncate">{a.name}</span>
            </span>
            {a.id === agentId ? <Check className="h-3.5 w-3.5 text-[#b9a6ff]" /> : null}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/agents" className="flex items-center gap-2">
            <Network className="h-3.5 w-3.5" /> Tous les agents →
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
