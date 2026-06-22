import type { ReactNode } from "react";

import { redirect } from "@/i18n/navigation";
import { currentRole, hasProductAccess, spaceRedirectForRole } from "@/lib/auth/session";

interface ProductLayoutProps {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}

export const dynamic = "force-dynamic";

export default async function ProductLayout({ children, params }: ProductLayoutProps) {
  const { locale } = await params;
  const role = await currentRole();

  if (!hasProductAccess(role)) {
    // Send a denied session to ITS landing (ADR 0013), not a hard-coded surface:
    // a collections role lands on /recouvrement, not the cockpit (which it cannot
    // reach) — avoiding a redirect loop.
    redirect({ href: spaceRedirectForRole(role), locale });
  }

  return children;
}
