import { getTranslations, setRequestLocale } from "next-intl/server";

import { LandingLauncher } from "@/components/landing/landing-launcher";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "landing" });
  return { title: t("welcome") };
}

export default async function HomePage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <LandingLauncher />;
}
