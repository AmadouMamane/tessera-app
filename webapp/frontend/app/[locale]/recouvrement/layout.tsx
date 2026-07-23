import type { ReactNode } from "react";

import { redirect } from "@/i18n/navigation";
import { currentRole, hasCollectionsAccess, spaceRedirectForRole } from "@/lib/auth/session";

interface RecouvrementLayoutProps {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}

export const dynamic = "force-dynamic";

// Business-plane gate (ADR 0010 Phase C / 0013). Reached DIRECTLY by the
// `collections` role (platform operators may also enter to supervise) — never via
// the cockpit. This is the *front* gate; the agent independently re-checks the
// signed operator assertion the BFF forwards (the real authority). A session
// without collections access is sent to its own landing, not the cockpit.
export default async function RecouvrementLayout({ children, params }: RecouvrementLayoutProps) {
  const { locale } = await params;
  const role = await currentRole();
  if (role === null) {
    redirect({ href: "/login?next=/recouvrement", locale });
  }
  if (!hasCollectionsAccess(role)) {
    redirect({ href: spaceRedirectForRole(role), locale });
  }
  return children;
}
