import type { ReactNode } from "react";

import { AppBreadcrumb } from "./app-breadcrumb";
import { AppFooter } from "./app-footer";
import { ShellChrome } from "./shell-chrome";
import { ShellFrame } from "./shell-frame";
import { Sidebar } from "./sidebar";
import { Topbar, type TopbarAction, type TopbarContextItem } from "./topbar";

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
    <ShellChrome>
      <ShellFrame
        sidebar={sidebar ?? <Sidebar />}
        topbar={
          <Topbar
            title={title}
            description={description}
            contextItems={topbarContext}
            actions={topbarActions}
            breadcrumb={breadcrumb}
          />
        }
        footer={<AppFooter />}
      >
        <AppBreadcrumb />
        {children}
      </ShellFrame>
    </ShellChrome>
  );
}
