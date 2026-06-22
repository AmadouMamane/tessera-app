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
 * Customer chat — the single live presentation (cut-over done; see
 * `docs/design/ui-contract.md`). It is an honest decor host (badge + notice +
 * skeletons, NO fabricated banking data) with the floating `ChatWidget` on top.
 *
 * Re-skin, not re-fork: the widget reuses the existing `<ChatRoom>` core verbatim
 * (`streamChat` + `MessageBubble` + the chat store). This page owns no streaming
 * or message-rendering logic. `produit/layout.tsx` applies the product access gate
 * above it. The former portal presentation and its sub-pages were retired.
 */
export default async function ProductChatPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  return (
    <>
      <ApercuHost />
      <ChatWidget />
    </>
  );
}
