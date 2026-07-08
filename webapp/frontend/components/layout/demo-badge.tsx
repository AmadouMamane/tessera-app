"use client";

import { FlaskConical } from "lucide-react";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

interface DemoBadgeProps {
  className?: string;
  floating?: boolean;
  href?: "/select-space" | "/espaces";
  label?: string;
}

export function DemoBadge({
  className,
  floating = false,
  href = "/select-space",
  label,
}: DemoBadgeProps) {
  const t = useTranslations("demoBadge");
  const link = (
    <Link
      href={href}
      aria-label={t("ariaLabel")}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--card)]/70 px-3 py-1.5 text-xs font-medium text-[var(--muted-foreground)] backdrop-blur transition-colors hover:bg-[var(--muted)] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
        className,
      )}
    >
      <FlaskConical className="h-3.5 w-3.5" />
      {label ?? t("label")}
    </Link>
  );

  if (floating) {
    return <div className="fixed bottom-3 left-3 z-40">{link}</div>;
  }

  return link;
}
