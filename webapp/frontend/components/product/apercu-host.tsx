import { ArrowLeftRight, CreditCard, FileText, Landmark, Lock } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useTranslations } from "next-intl";

/**
 * Decor host for the customer chat (`/produit`). Pure stage set:
 * a fake "Crédit Aurore — Espace personnel" customer portal made of greyed
 * skeleton tiles explicitly labelled "demo host". It carries **no real banking
 * data and no banking functionality** — its only job is to be the backdrop the
 * floating chat widget (the one real, functional element) sits on top of.
 */
export function ApercuHost() {
  const t = useTranslations("product.apercu");

  const tiles: { key: string; label: string; Icon: LucideIcon }[] = [
    { key: "balance", label: t("tiles.balance"), Icon: Landmark },
    { key: "cards", label: t("tiles.cards"), Icon: CreditCard },
    { key: "transfers", label: t("tiles.transfers"), Icon: ArrowLeftRight },
    { key: "documents", label: t("tiles.documents"), Icon: FileText },
  ];

  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--foreground)]">
      {/* Portal header */}
      <header className="border-b border-[var(--border)] bg-[var(--card)]/60 backdrop-blur-xl">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-5 py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-navy-900 text-gold-400 ring-1 ring-gold-500/20 dark:bg-gold-500 dark:text-navy-950">
            <Landmark className="h-4 w-4" />
          </div>
          <div className="flex min-w-0 flex-col">
            <span className="text-sm font-semibold leading-tight">{t("brand")}</span>
            <span className="text-xs text-[var(--muted-foreground)] leading-tight">
              {t("space")}
            </span>
          </div>
          <span className="ml-auto inline-flex items-center gap-1.5 rounded-full border border-dashed border-[var(--border)] bg-[var(--muted)]/40 px-2.5 py-1 text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">
            <Lock className="h-3 w-3" />
            {t("demoBadge")}
          </span>
        </div>
      </header>

      {/* Demo notice */}
      <div className="mx-auto max-w-5xl px-5 pt-6">
        <p className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--muted)]/30 px-4 py-3 text-xs text-[var(--muted-foreground)]">
          {t("demoNotice")}
        </p>
      </div>

      {/* Greyed skeleton tiles */}
      <main className="mx-auto max-w-5xl px-5 py-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {tiles.map(({ key, label, Icon }) => (
            <div
              key={key}
              aria-hidden
              className="relative select-none overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]/40 p-4 opacity-60"
            >
              <div className="flex items-center gap-2 text-[var(--muted-foreground)]">
                <Icon className="h-4 w-4" />
                <span className="text-xs font-medium">{label}</span>
              </div>
              {/* skeleton bars — clearly non-data placeholders */}
              <div className="mt-4 space-y-2">
                <div className="h-6 w-2/3 animate-pulse rounded-md bg-[var(--muted)]" />
                <div className="h-3 w-full animate-pulse rounded bg-[var(--muted)]/70" />
                <div className="h-3 w-4/5 animate-pulse rounded bg-[var(--muted)]/70" />
              </div>
              <span className="mt-4 inline-block text-xs uppercase tracking-wider text-[var(--muted-foreground)]/60">
                {t("tiles.placeholder")}
              </span>
            </div>
          ))}
        </div>

        {/* Secondary skeleton rows */}
        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
          {["a", "b", "c"].map((k) => (
            <div
              key={k}
              aria-hidden
              className="space-y-3 rounded-2xl border border-[var(--border)] bg-[var(--card)]/40 p-4 opacity-50"
            >
              <div className="h-3 w-1/3 animate-pulse rounded bg-[var(--muted)]" />
              <div className="h-3 w-full animate-pulse rounded bg-[var(--muted)]/70" />
              <div className="h-3 w-5/6 animate-pulse rounded bg-[var(--muted)]/70" />
              <div className="h-3 w-2/3 animate-pulse rounded bg-[var(--muted)]/70" />
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
