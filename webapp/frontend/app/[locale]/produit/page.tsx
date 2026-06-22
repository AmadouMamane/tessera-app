import { setRequestLocale } from "next-intl/server";

import { DemoLauncherLink } from "@/components/layout/demo-launcher-link";
import { ChatWidget } from "@/components/product/chat-widget";
import { CreditAuroreMesComptesHost } from "@/components/product/credit-aurore-mes-comptes-host";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export function generateMetadata() {
  return { title: "Crédit Aurore · Mes comptes" };
}

/**
 * Customer product — the v2 cut-over (decision recorded): `/produit` now renders
 * the "Crédit Aurore · Mes comptes" host (formerly `/produit/apercu3`) with the
 * real chat. It is an honest fictional decor host — its visible "Page client
 * fictive, chat réel" label is kept — and the floating `ChatWidget` reuses the
 * shared `<ChatRoom>` core verbatim (re-skin, NOT a fork: `streamChat` stays the
 * single chat entry point). The launcher bubble is persistent (no `hideLauncher`).
 *
 * `produit/layout.tsx` applies the product access gate above; the host is full-
 * bleed (no shell chrome) so there is no double chrome. `/produit/apercu3`
 * redirects here; `/produit/apercu` and `/produit/apercu2` are left untouched.
 */
export default async function ProductChatPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  return (
    <>
      <CreditAuroreMesComptesHost />
      <ChatWidget />
      <DemoLauncherLink floating />
    </>
  );
}
