import type { ReactNode } from "react";

import { redirect } from "@/i18n/navigation";
import { currentRole, hasCockpitAccess } from "@/lib/auth/session";

interface AgentLayoutProps {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}

export const dynamic = "force-dynamic";

export default async function AgentLayout({ children, params }: AgentLayoutProps) {
  const { locale } = await params;
  const role = await currentRole();

  if (!hasCockpitAccess(role)) {
    redirect({ href: "/produit", locale });
  }

  return children;
}
