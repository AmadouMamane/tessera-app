import { redirect } from "@/i18n/navigation";

interface PageProps {
  params: Promise<{ locale: string }>;
}

/** Stable proof entry point used by explanatory and product surfaces. */
export default async function ProuverPage({ params }: PageProps) {
  const { locale } = await params;
  redirect({ href: "/prouver/audit-logs", locale });
}
