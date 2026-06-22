import { getTranslations, setRequestLocale } from "next-intl/server";

import { ApercuHost } from "@/components/product/apercu-host";
import { ChatWidget } from "@/components/product/chat-widget";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "product.apercu" });
  return { title: `${t("brand")} · ${t("space")}` };
}

/**
 * v2 product preview — the new presentation of the customer chat.
 *
 * Lives on a *separate route* while the legacy `/produit` (ProductShell +
 * full-page ChatRoom) stays intact and functional. This page is intentionally
 * NOT wrapped in `ProductShell`: it renders its own decor host (a fake bank
 * portal) with the floating `ChatWidget` on top. The widget reuses the
 * existing `<ChatRoom>` core verbatim — see the cut-over plan in
 * `docs/design/ui-contract.md`.
 *
 * `produit/layout.tsx` still applies the product access gate above this page.
 */
export default async function ProductApercuPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  return (
    <>
      <ApercuHost />
      <ChatWidget />
    </>
  );
}
