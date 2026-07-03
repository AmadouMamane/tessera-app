import { redirect } from "next/navigation";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export const dynamic = "force-dynamic";

export function generateMetadata() {
  return { title: "Recouvrement legacy" };
}

export default async function RecouvrementRedirectPage({ params }: PageProps) {
  const { locale } = await params;
  redirect(`/${locale}/recouvrement-legacy`);
}
