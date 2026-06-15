"use client";

import { Bell, FileText, ListChecks, type LucideIcon, MessageSquare, Settings } from "lucide-react";
import { useTranslations } from "next-intl";

import { TesseraLogo } from "@/components/brand/tessera-logo";
import { Link, usePathname } from "@/i18n/navigation";
import { cn } from "@/lib/cn";

type ClientHref =
  | "/produit"
  | "/produit/mes-demandes"
  | "/produit/documents"
  | "/produit/alertes"
  | "/produit/parametres";

const NAV: ReadonlyArray<{ href: ClientHref; icon: LucideIcon; key: string }> = [
  { href: "/produit", icon: MessageSquare, key: "chat" },
  { href: "/produit/mes-demandes", icon: ListChecks, key: "requests" },
  { href: "/produit/documents", icon: FileText, key: "documents" },
  { href: "/produit/alertes", icon: Bell, key: "alerts" },
  { href: "/produit/parametres", icon: Settings, key: "settings" },
];

function isActive(pathname: string, href: ClientHref): boolean {
  if (href === "/produit") return pathname === "/produit";
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * Left rail for the client space. Same look as the cockpit sidebar but carries
 * only client destinations — the end customer never sees any cockpit entry.
 */
export function ClientSidebar() {
  const pathname = usePathname();
  const t = useTranslations("product.nav");

  return (
    <aside className="flex h-full w-20 shrink-0 flex-col border-r border-[var(--tessera-border)] bg-[var(--tessera-bg-soft)] text-[var(--tessera-text)] md:w-[218px]">
      <div className="flex min-h-[5.5rem] items-center justify-center gap-3 border-b border-[var(--tessera-border)] px-3 md:justify-start md:px-5">
        <TesseraLogo className="h-9" />
      </div>

      <nav className="min-h-0 flex-1 overflow-y-auto px-2 py-4 md:px-3">
        <ul className="flex flex-col gap-1 md:gap-0.5">
          {NAV.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "group flex min-h-9 items-center justify-center gap-2 rounded-md px-2 py-2 text-sm font-medium transition-colors md:justify-start md:px-3",
                    active
                      ? "border-l-2 border-[var(--tessera-green)] bg-[var(--tessera-surface-elevated)] pl-[6px] text-white md:pl-[10px]"
                      : "text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]",
                  )}
                >
                  <item.icon
                    className={cn(
                      "h-4 w-4 shrink-0 transition-colors",
                      active
                        ? "text-[var(--tessera-green)]"
                        : "text-[var(--tessera-text-muted)] group-hover:text-[var(--tessera-text)]",
                    )}
                  />
                  <span className="hidden min-w-0 flex-1 truncate md:block">{t(item.key)}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="border-t border-[var(--tessera-border)] p-2 md:p-3">
        <div className="flex items-center justify-center gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2 md:justify-start md:p-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--tessera-green-muted)] text-sm font-semibold text-[#d6f0e3]">
            CA
          </div>
          <div className="hidden min-w-0 md:block">
            <p className="truncate text-sm font-semibold text-white">{t("brand")}</p>
            <p className="truncate text-xs text-[var(--tessera-text-muted)]">{t("chat")}</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
