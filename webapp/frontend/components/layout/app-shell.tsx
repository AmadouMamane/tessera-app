import type { ReactNode } from "react";

import { AppBreadcrumb } from "./app-breadcrumb";
import { AppFooter } from "./app-footer";
import { Sidebar } from "./sidebar";
import { Topbar, type TopbarAction, type TopbarContextItem } from "./topbar";

/** The single, shell-wide content cap. Below it the content is fluid with side
 *  padding; at/above it (incl. 32"+ displays) the column is centred and never
 *  stretches edge-to-edge. Wide artefacts (large tables, the XT-01 waterfall)
 *  take the full container width and scroll-x inside it. */
const CONTENT_MAX_WIDTH = "max-w-[1600px]";

interface AppShellProps {
  title: string;
  description?: string;
  children: ReactNode;
  /**
   * @deprecated Page width is standardized in the shell (a single ~1600px
   * centred cap). Accepted for backwards compatibility but no longer changes
   * the width — remove ad-hoc `contentWidth` from pages.
   */
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
  topbarContext,
  topbarActions,
  breadcrumb,
  sidebar,
}: AppShellProps) {
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
        <main className="min-h-0 min-w-0 flex-1 overflow-x-hidden overflow-y-auto px-4 py-5 sm:px-6">
          <div className={`mx-auto flex h-full w-full ${CONTENT_MAX_WIDTH} flex-col`}>
            <AppBreadcrumb />
            {children}
          </div>
        </main>
        <AppFooter />
      </div>
    </div>
  );
}
