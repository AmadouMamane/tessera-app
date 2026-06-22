import { setRequestLocale } from "next-intl/server";

import { ChatWidget } from "@/components/product/chat-widget";
import { CreditAuroreMesComptesHost } from "@/components/product/credit-aurore-mes-comptes-host";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export function generateMetadata() {
  return { title: "Crédit Aurore · Mes comptes" };
}

export default async function ProductApercu3Page({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <>
      <CreditAuroreMesComptesHost />
      <ChatWidget hideLauncher />
    </>
  );
}
