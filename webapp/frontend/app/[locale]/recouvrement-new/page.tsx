import { setRequestLocale } from "next-intl/server";

import { RecouvrementProductExperience } from "@/components/recouvrement/recouvrement-product-experience";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export const dynamic = "force-dynamic";

export function generateMetadata() {
  return { title: "Recouvrement" };
}

export default async function RecouvrementNewPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <RecouvrementProductExperience />;
}
