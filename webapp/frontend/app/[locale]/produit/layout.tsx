import type { ReactNode } from "react";

import { redirect } from "@/i18n/navigation";
import { DEFAULT_AGENT_ID, agentPath } from "@/lib/agent-context";
import { currentRole, hasProductAccess } from "@/lib/auth/session";

interface ProductLayoutProps {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}

export const dynamic = "force-dynamic";

export default async function ProductLayout({ children, params }: ProductLayoutProps) {
  const { locale } = await params;
  const role = await currentRole();

  if (!hasProductAccess(role)) {
    redirect({ href: agentPath(DEFAULT_AGENT_ID, "synthese"), locale });
  }

  return children;
}
