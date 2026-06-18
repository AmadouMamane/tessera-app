import type { ReactNode } from "react";

import { AppBreadcrumb } from "./app-breadcrumb";
import { AppFooter } from "./app-footer";
import { Sidebar } from "./sidebar";
import { Topbar, type TopbarAction, type TopbarContextItem } from "./topbar";

interface AppShellProps {
  title: string;
  description?: string;
  children: ReactNode;
  contentWidth?: "default" | "wide" | "full";
  topbarContext?: TopbarContextItem[];
  topbarActions?: TopbarAction[];
  breadcrumb?: { section: string; label: string };
  /** Override the left rail (defaults to the cockpit sidebar). */
  sidebar?: ReactNode;
}

export function AppShell({
  title,
  description,
  children,
  contentWidth = "default",
  topbarContext,
  topbarActions,
  breadcrumb,
  sidebar,
}: AppShellProps) {
  // "full" — edge-to-edge desktop dashboard (no centred cap), tight padding.
  const maxWidth =
    contentWidth === "full"
      ? "max-w-none"
      : contentWidth === "wide"
        ? "max-w-[1440px]"
        : "max-w-6xl";
  const mainPadding =
    contentWidth === "full" ? "px-3 py-2" : contentWidth === "wide" ? "px-4 py-3" : "px-8 py-6";

  return (
    <div className="bg-canvas-glow relative flex h-full overflow-hidden bg-[var(--tessera-bg)] text-[var(--tessera-text)]">
      {sidebar ?? <Sidebar />}
      <div className="flex h-full min-w-0 flex-1 flex-col">
        <Topbar
          title={title}
          description={description}
          contextItems={topbarContext}
          actions={topbarActions}
          breadcrumb={breadcrumb}
        />
        <main className={`min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto ${mainPadding}`}>
          <div className={`mx-auto flex h-full w-full ${maxWidth} flex-col`}>
            <AppBreadcrumb />
            {children}
          </div>
        </main>
        <AppFooter />
      </div>
    </div>
  );
}
