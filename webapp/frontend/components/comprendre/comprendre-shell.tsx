import type { ReactNode } from "react";

import { AppShell } from "@/components/layout/app-shell";

/** Public wrapper shared by the concise explanation and its long-form reading. */
export function ComprendreShell({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <AppShell title={title} description={description} publicAccess>
      {children}
    </AppShell>
  );
}
