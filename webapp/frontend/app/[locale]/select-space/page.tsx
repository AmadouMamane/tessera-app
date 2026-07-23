import { getTranslations, setRequestLocale } from "next-intl/server";

import { LandingLauncher } from "@/components/landing/landing-launcher";
import { loadLauncherSignal } from "@/lib/server/launcher-signal";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "landing" });
  return { title: t("demoTitle") };
}

// ADR 0013 — demoted from front door to a labelled DEMO LAUNCHER. The real entry
// is identity (the locale root role-routes server-side). This page is a reviewer
// convenience that shows both audiences, so it is open to anyone and never
// redirects: the two cards just *link* to /espaces and the cockpit. Following
// the operator card without operator-rbac hits the cockpit guard (no bypass) —
// routing here is not authorization.
export default async function DemoLauncherPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  // Public-safe aggregate signal (ADR 0009): real fleet rollup + last eval, or
  // null → the launcher shows an honest "indisponible" (never a fabricated number).
  const signal = await loadLauncherSignal();

  return <LandingLauncher signal={signal} />;
}
