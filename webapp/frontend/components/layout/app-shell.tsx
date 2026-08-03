import type { ReactNode } from "react";

import { AppFooter } from "./app-footer";
import { AppHeader, type HeaderAction, type HeaderContextItem } from "./app-header";
import { CockpitAuthGate } from "./cockpit-auth-gate";
import { QueryHealthNotice } from "./query-health-notice";
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
  /**
   * Skip the cockpit role gate. **Exactly one page sets this: `/comprendre`.**
   *
   * That page holds no data — eight paragraphs and a drawing, straight from the locale
   * catalogue, reading no store and no backend. It exists to explain the product to someone
   * who has never seen it, and the launcher offers it to a visitor who has not logged in.
   * Requiring a session to read it would lock the very door it was built to open.
   *
   * Not a general escape hatch: any page that renders a fact must stay behind the gate.
   */
  publicAccess?: boolean;
}

export function AppShell({
  title,
  description,
  children,
  topbarContext,
  topbarFilters,
  topbarActions,
  sidebar,
  publicAccess = false,
}: AppShellProps) {
  const shell = (
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
        <QueryHealthNotice />
        {children}
      </ShellFrame>
    </ShellChrome>
  );

  return publicAccess ? shell : <CockpitAuthGate>{shell}</CockpitAuthGate>;
}
