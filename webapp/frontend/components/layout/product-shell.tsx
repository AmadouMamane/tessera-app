import type { ReactNode } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { ClientSidebar } from "@/components/layout/client-sidebar";

interface ProductShellProps {
  children: ReactNode;
  title: string;
  description?: string;
  contentWidth?: "default" | "wide" | "full";
}

/**
 * Client-facing shell: the shared app shell with the client sidebar swapped in,
 * so the customer gets the left rail + content layout but never any cockpit
 * chrome.
 */
export function ProductShell({ children, title, description, contentWidth }: ProductShellProps) {
  return (
    <AppShell
      title={title}
      description={description}
      contentWidth={contentWidth}
      sidebar={<ClientSidebar />}
    >
      {children}
    </AppShell>
  );
}
