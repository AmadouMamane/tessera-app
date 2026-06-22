import { getTranslations, setRequestLocale } from "next-intl/server";

import { redirect } from "@/i18n/navigation";
import { currentRole, spaceRedirectForRole } from "@/lib/auth/session";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "landing" });
  return { title: t("welcome") };
}

export default async function HomePage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  // ADR 0013 — the front door is identity, not a picker. Resolve the session
  // SERVER-side (next-auth via currentRole → auth()), then route by audience: an
  // authenticated operator lands in the cockpit, everyone else on the customer
  // product. This only chooses the landing; the operator-rbac guard in the cockpit
  // layouts remains the authority. The manual picker survives only as a labelled
  // demo launcher reached by URL (/select-space), never as the front door.
  const role = await currentRole();
  redirect({ href: spaceRedirectForRole(role), locale });
}
