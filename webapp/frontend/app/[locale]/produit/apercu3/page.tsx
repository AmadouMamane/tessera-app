import { redirect } from "@/i18n/navigation";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export const dynamic = "force-dynamic";

// v2 cut-over: apercu3 became the real product. This route now redirects to
// /produit (which renders the same CreditAuroreMesComptesHost + ChatWidget). Kept
// as a stable redirect so existing links/bookmarks to /produit/apercu3 still land.
export default async function ProductApercu3Page({ params }: PageProps) {
  const { locale } = await params;
  redirect({ href: "/produit", locale });
}
