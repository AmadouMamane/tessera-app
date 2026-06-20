import { getTranslations, setRequestLocale } from "next-intl/server";

import { ClientRequests } from "@/components/client/client-requests";
import { ProductShell } from "@/components/layout/product-shell";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "product.nav" });
  return { title: t("requests") };
}

export default async function ProductRequestsPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "product.nav" });
  return (
    <ProductShell title={t("requests")}>
      <ClientRequests />
    </ProductShell>
  );
}
