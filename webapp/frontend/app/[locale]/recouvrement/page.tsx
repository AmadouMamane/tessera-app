import { setRequestLocale } from "next-intl/server";

import { RecouvrementProductExperience } from "@/components/recouvrement/recouvrement-product-experience";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export const dynamic = "force-dynamic";

export function generateMetadata() {
  return { title: "Recouvrement" };
}

// The canonical collections surface. The product experience (formerly stranded on the
// ungated `recouvrement-new`) renders HERE, behind this route's collections gate
// (layout.tsx) — which closes the ungated-surface hole the `-new` route left open
// (audit P0.4). `-new` and the `-legacy` console route are removed; every inbound link,
// the role router (spaceRedirectForRole), and the gate already pointed at `/recouvrement`.
export default async function RecouvrementPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <RecouvrementProductExperience />;
}
