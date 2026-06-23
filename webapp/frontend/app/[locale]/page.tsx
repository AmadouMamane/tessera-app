import { setRequestLocale } from "next-intl/server";

import { redirect } from "@/i18n/navigation";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export const dynamic = "force-dynamic";

export default async function HomePage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  // The locale root opens the demo launcher (the space picker / showcase). Direct
  // URLs stay bookmarkable (/produit, /surveiller/vue-ensemble, /recouvrement), and
  // the per-surface RBAC guards remain the authority — the launcher only informs
  // and links.
  redirect({ href: "/select-space", locale });
}
