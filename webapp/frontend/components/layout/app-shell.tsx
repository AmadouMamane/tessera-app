import type { ReactNode } from "react";

import { AppFooter } from "./app-footer";
import { AppHeader, type HeaderAction, type HeaderContextItem } from "./app-header";
import { CockpitAuthGate } from "./cockpit-auth-gate";
import { ShellChrome } from "./shell-chrome";
import { ShellFrame } from "./shell-frame";
import { Sidebar } from "./sidebar";

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
  topbarContext?: HeaderContextItem[];
  /** Extra view filters in the header's filter bar (e.g. the agent filter). */
  topbarFilters?: ReactNode;
  topbarActions?: HeaderAction[];
  /** Override the left rail (defaults to the cockpit sidebar). */
  sidebar?: ReactNode;
}

export function AppShell({
  title,
  description,
  children,
  topbarContext,
  topbarFilters,
  topbarActions,
  sidebar,
}: AppShellProps) {
  return (
    <CockpitAuthGate>
      <ShellChrome>
        <ShellFrame
          sidebar={sidebar ?? <Sidebar />}
          topbar={
            <AppHeader
              plan="cockpit"
              title={title}
              description={description}
              contextItems={topbarContext}
              filters={topbarFilters}
              actions={topbarActions}
            />
          }
          footer={<AppFooter />}
        >
          {children}
        </ShellFrame>
      </ShellChrome>
    </CockpitAuthGate>
  );
}
