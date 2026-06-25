import type { ReactNode } from "react";

import { AppFooter } from "./app-footer";
import { AppHeader, type HeaderAction, type HeaderContextItem } from "./app-header";
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
  topbarActions?: HeaderAction[];
  /** Override the left rail (defaults to the cockpit sidebar). */
  sidebar?: ReactNode;
}

export function AppShell({
  title,
  description,
  children,
  topbarContext,
  topbarActions,
  sidebar,
}: AppShellProps) {
  return (
    <ShellChrome>
      <ShellFrame
        sidebar={sidebar ?? <Sidebar />}
        topbar={
          <AppHeader
            plan="cockpit"
            title={title}
            description={description}
            contextItems={topbarContext}
            actions={topbarActions}
          />
        }
        footer={<AppFooter />}
      >
        {children}
      </ShellFrame>
    </ShellChrome>
  );
}
