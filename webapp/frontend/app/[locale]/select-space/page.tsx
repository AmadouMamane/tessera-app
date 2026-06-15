import { getTranslations, setRequestLocale } from "next-intl/server";

import { LandingLauncher } from "@/components/landing/landing-launcher";
import { redirect } from "@/i18n/navigation";
import { currentRole, hasDualSpaceAccess, spaceRedirectForRole } from "@/lib/auth/session";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "landing" });
  return { title: t("welcome") };
}

export default async function SelectSpacePage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const role = await currentRole();

  if (!hasDualSpaceAccess(role)) {
    redirect({ href: spaceRedirectForRole(role), locale });
  }

  return <LandingLauncher />;
}
