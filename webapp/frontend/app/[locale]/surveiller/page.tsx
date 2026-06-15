import { redirect } from "@/i18n/navigation";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export default async function RedirectPage({ params }: PageProps) {
  const { locale } = await params;
  redirect({ href: "/surveiller/vue-ensemble", locale });
}
