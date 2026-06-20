import { getTranslations, setRequestLocale } from "next-intl/server";

import { ClientDocuments } from "@/components/client/client-documents";
import { ProductShell } from "@/components/layout/product-shell";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "product.nav" });
  return { title: t("documents") };
}

export default async function ProductDocumentsPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "product.nav" });
  return (
    <ProductShell title={t("documents")}>
      <ClientDocuments />
    </ProductShell>
  );
}
