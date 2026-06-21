import { getTranslations, setRequestLocale } from "next-intl/server";

import { ChatWidget } from "@/components/product/chat-widget";
import { MesComptesHost } from "@/components/product/mes-comptes-host";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "product.apercu2" });
  return { title: `${t("brand")} · ${t("title")}` };
}

/**
 * v2 product preview #2 — faithful reproduction of the "Mes comptes" retail
 * bank portal (`docs/ui-reference/produit/espace_client.png`) as a decor host,
 * with the *same* floating `ChatWidget` (reusing `<ChatRoom>`) on top.
 *
 * Like `/produit/apercu`, this is a separate route: the legacy `/produit`
 * stays intact. Rendered outside `ProductShell`, still behind the product
 * access gate in `produit/layout.tsx`. See `docs/design/ui-contract.md`.
 */
export default async function ProductApercu2Page({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  return (
    <>
      <MesComptesHost />
      <ChatWidget />
    </>
  );
}
