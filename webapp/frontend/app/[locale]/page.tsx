import { setRequestLocale } from "next-intl/server";

import { redirect } from "@/i18n/navigation";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export const dynamic = "force-dynamic";

export default async function HomePage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  // The locale root always opens the demo launcher (/select-space) — the space
  // chooser — for EVERYONE, signed in or not. Per-surface RBAC guards remain the
  // authority once a space is entered; routing only chooses the landing.
  redirect({ href: "/select-space", locale });
}
