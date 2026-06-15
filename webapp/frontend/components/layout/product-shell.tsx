"use client";

import { Bell, FileText, ListChecks, MessageSquare, Settings } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { Link, usePathname } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

type ProductHref =
  | "/produit"
  | "/produit/mes-demandes"
  | "/produit/documents"
  | "/produit/alertes"
  | "/produit/parametres";

const NAV: ReadonlyArray<{ href: ProductHref; icon: LucideIcon; key: string }> = [
  { href: "/produit", icon: MessageSquare, key: "chat" },
  { href: "/produit/mes-demandes", icon: ListChecks, key: "requests" },
  { href: "/produit/documents", icon: FileText, key: "documents" },
  { href: "/produit/alertes", icon: Bell, key: "alerts" },
  { href: "/produit/parametres", icon: Settings, key: "settings" },
];

function isActive(pathname: string, href: ProductHref): boolean {
  if (href === "/produit") return pathname === "/produit";
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * Client-facing shell. Deliberately carries no cockpit chrome (no grouped
 * sidebar, no operator nav): the end customer never sees the Cockpit.
 */
export function ProductShell({ children }: { children: ReactNode }) {
  const t = useTranslations("product.nav");
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col bg-[var(--tessera-bg)] text-[var(--tessera-text)]">
      <header className="flex h-14 shrink-0 items-center gap-4 border-b border-[var(--tessera-border)] bg-[var(--tessera-bg-soft)] px-4">
        <Link href="/produit" className="flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-[var(--tessera-green-muted)] text-sm font-semibold text-[#d6f0e3]">
            CA
          </span>
          <span className="hidden text-sm font-semibold text-white sm:block">{t("brand")}</span>
        </Link>
        <nav className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
          {NAV.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex shrink-0 items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-[var(--tessera-surface-elevated)] text-white"
                    : "text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]",
                )}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                <span className="hidden md:block">{t(item.key)}</span>
              </Link>
            );
          })}
        </nav>
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--tessera-muted)] text-xs font-semibold text-[var(--tessera-text)]">
          ML
        </div>
      </header>
      <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
