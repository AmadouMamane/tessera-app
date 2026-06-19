import { Skeleton } from "@/components/ui/skeleton";

/**
 * Streaming fallback for every AGENT sub-page. The shell (sidebar + topbar) and
 * the per-agent command bar (AgentTabs) live in the parent layouts and stay
 * mounted, so on a tab click this skeleton paints INSTANTLY in the body while the
 * page's server prefetch (a backend round-trip) runs — no blank screen, no shell
 * flash. The layout mirrors the real agent pages (KPI strip + main/aside grid) to
 * avoid content-shift when the data arrives.
 */
export default function AgentSectionLoading() {
  return (
    <div
      data-testid="agent-loading"
      className="flex animate-in flex-col gap-3 pb-2 duration-150 motion-reduce:animate-none"
    >
      {/* cross-links / sub-bar */}
      <Skeleton className="h-9 w-full" />

      {/* KPI strip */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-7">
        {["k1", "k2", "k3", "k4", "k5", "k6", "k7"].map((k) => (
          <Skeleton key={k} className="h-[88px] w-full" />
        ))}
      </div>

      {/* main + aside grid */}
      <div className="grid gap-3 xl:grid-cols-12">
        <div className="flex min-w-0 flex-col gap-3 xl:col-span-8">
          <Skeleton className="h-[220px] w-full" />
          <div className="grid gap-3 sm:grid-cols-2">
            <Skeleton className="h-[180px] w-full" />
            <Skeleton className="h-[180px] w-full" />
          </div>
          <Skeleton className="h-[200px] w-full" />
        </div>
        <div className="flex min-w-0 flex-col gap-3 xl:col-span-4">
          <Skeleton className="h-[160px] w-full" />
          <Skeleton className="h-[240px] w-full" />
          <Skeleton className="h-[140px] w-full" />
        </div>
      </div>
    </div>
  );
}
