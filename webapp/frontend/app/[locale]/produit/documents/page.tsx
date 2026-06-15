import { getTranslations, setRequestLocale } from "next-intl/server";

import { ScaffoldView } from "@/components/common/scaffold-view";
import { ProductShell } from "@/components/layout/product-shell";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "product.nav" });
  return { title: t("documents") };
}

export default async function ProductScaffoldPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "product.nav" });
  const title = t("documents");
  return (
    <ProductShell title={title}>
      <ScaffoldView title={title} />
    </ProductShell>
  );
}
