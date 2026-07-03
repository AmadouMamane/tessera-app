import { getTranslations, setRequestLocale } from "next-intl/server";

import { RecouvrementConsole } from "@/components/recouvrement/recouvrement-console";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "recouvrement" });
  return { title: t("title") };
}

/**
 * Recouvrement's dedicated business console (ADR 0010 Phase C). A re-skin over the
 * REAL chat core — it mounts the shared premium `<ChatRoom>` (not the debug
 * console) with the `recouvrement` surface hint, so a verified collections/operator
 * session talks to the real internal recouvrement agent. The layout gates entry to
 * the collections role.
 */
export default async function RecouvrementPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <RecouvrementConsole />;
}
