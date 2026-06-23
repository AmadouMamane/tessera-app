import { setRequestLocale } from "next-intl/server";

import { redirect } from "@/i18n/navigation";
import { currentRole, spaceRedirectForRole } from "@/lib/auth/session";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export const dynamic = "force-dynamic";

export default async function HomePage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  // Identity-routed root (ADR 0013), with the demo launcher as the fallback: an
  // authenticated next-auth session (operator → overview, collections → its
  // console) is routed to its home; an unauthenticated visitor lands on the demo
  // launcher (/select-space) — the space picker / showcase. Either way the
  // per-surface RBAC guards remain the authority; routing only chooses the landing.
  const role = await currentRole();
  redirect({ href: role ? spaceRedirectForRole(role) : "/select-space", locale });
}
