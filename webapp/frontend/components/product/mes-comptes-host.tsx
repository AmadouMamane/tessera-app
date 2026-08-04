import {
  ArrowLeftRight,
  Bell,
  Briefcase,
  ChevronRight,
  ChevronUp,
  CreditCard,
  Facebook,
  FileText,
  Files,
  Instagram,
  Landmark,
  Lock,
  MessageSquare,
  Phone,
  PiggyBank,
  PlusCircle,
  Search,
  Settings2,
  ShieldCheck,
  Smartphone,
  User,
  Users,
  Wallet,
  Youtube,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useTranslations } from "next-intl";

/**
 * Decor host #2 for the v2 product preview (`/produit/apercu2`). A generic
 * retail-bank "Mes comptes" customer portal — the industry's common shape, not
 * any particular institution's page — in Tessera's navy/gold palette (follows
 * the active light/dark theme via CSS tokens):
 * top bar, secondary tabs, a two-column accounts layout (current / savings /
 * cashback + a credit promo) and a "useful links" right rail, over a dark
 * footer.
 *
 * It is pure stage set — **fictitious data, no banking functionality**. The
 * only real, functional element is the floating `ChatWidget` mounted on top by
 * the page. Everything here is non-interactive on purpose (honest decor).
 */
export function MesComptesHost() {
  const t = useTranslations("product.apercu2");

  const headerIcons: { key: string; label: string; Icon: LucideIcon; badge?: boolean }[] = [
    { key: "search", label: t("header.search"), Icon: Search },
    { key: "notifications", label: t("header.notifications"), Icon: Bell, badge: true },
    { key: "messages", label: t("header.messages"), Icon: MessageSquare },
    { key: "subscribe", label: t("header.subscribe"), Icon: PlusCircle },
    { key: "profile", label: t("header.profile"), Icon: User },
  ];

  const tabs: { key: string; label: string }[] = [
    { key: "accounts", label: t("tabs.accounts") },
    { key: "cards", label: t("tabs.cards") },
    { key: "savings", label: t("tabs.savings") },
    { key: "insurance", label: t("tabs.insurance") },
    { key: "debits", label: t("tabs.debits") },
    { key: "budget", label: t("tabs.budget") },
    { key: "offers", label: t("tabs.offers") },
  ];

  const linkGroups: { title: string; items: { label: string; Icon: LucideIcon }[] }[] = [
    {
      title: t("links.management"),
      items: [
        { label: t("links.rib"), Icon: FileText },
        { label: t("links.statements"), Icon: Files },
        { label: t("links.customize"), Icon: Settings2 },
        { label: t("links.security"), Icon: ShieldCheck },
      ],
    },
    {
      title: t("links.services"),
      items: [
        { label: t("links.service1"), Icon: Smartphone },
        { label: t("links.service2"), Icon: Briefcase },
        { label: t("links.mobility"), Icon: ArrowLeftRight },
        { label: t("links.referral"), Icon: Users },
      ],
    },
    {
      title: t("links.contacts"),
      items: [{ label: t("links.agency"), Icon: Phone }],
    },
  ];

  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--foreground)]">
      {/* Top bar — Tessera navy/gold */}
      <header className="bg-gradient-to-r from-navy-900 to-navy-950 text-white dark:from-navy-950 dark:to-black">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gold-500 text-sm font-extrabold tracking-tight text-navy-950">
            CA
          </div>
          <span className="hidden text-sm font-semibold tracking-wide sm:inline">{t("brand")}</span>
          <span className="ml-2 inline-flex items-center gap-1.5 rounded-full border border-gold-500/30 bg-gold-500/10 px-2.5 py-0.5 text-[0.6rem] font-medium uppercase tracking-wider text-gold-300">
            <Lock className="h-3 w-3" />
            {t("demoBadge")}
          </span>
          <nav className="ml-auto flex items-center gap-4 sm:gap-5">
            {headerIcons.map(({ key, label, Icon, badge }) => (
              <span
                key={key}
                className="relative flex flex-col items-center gap-0.5 text-[0.6rem] font-medium text-white/85"
              >
                <span className="relative">
                  <Icon className="h-[18px] w-[18px]" />
                  {badge && (
                    <span className="absolute -right-1.5 -top-1 flex h-3.5 min-w-3.5 items-center justify-center rounded-full bg-gold-500 px-1 text-[0.55rem] font-bold text-navy-950">
                      3
                    </span>
                  )}
                </span>
                <span className="hidden md:inline">{label}</span>
              </span>
            ))}
          </nav>
        </div>
      </header>

      {/* Secondary tabs */}
      <div className="border-b border-[var(--border)] bg-[var(--card)]">
        <div className="mx-auto flex max-w-6xl gap-6 overflow-x-auto px-5 text-sm">
          {tabs.map((tab, i) => (
            <span
              key={tab.key}
              className={`whitespace-nowrap border-b-2 py-3.5 ${
                i === 0
                  ? "border-gold-500 font-semibold text-gold-600 dark:text-gold-400"
                  : "border-transparent text-[var(--muted-foreground)]"
              }`}
            >
              {tab.label}
            </span>
          ))}
        </div>
      </div>

      {/* Title */}
      <h1 className="pt-7 text-center text-2xl font-semibold text-[var(--foreground)]">
        {t("title")}
      </h1>

      {/* Demo notice */}
      <div className="mx-auto mt-4 max-w-6xl px-5">
        <p className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--muted)]/30 px-4 py-2.5 text-xs text-[var(--muted-foreground)]">
          {t("demoNotice")}
        </p>
      </div>

      {/* Body */}
      <main className="mx-auto grid max-w-6xl grid-cols-1 gap-6 px-5 py-6 lg:grid-cols-3">
        {/* Left column */}
        <div className="space-y-5 lg:col-span-2">
          {/* Comptes bancaires */}
          <Card title={t("sections.bank")}>
            <AccountRow
              Icon={Wallet}
              label={`${t("accounts.current")} n°•••• 0280`}
              amount="5 050,20 €"
            />
            <Divider />
            <AccountRow
              Icon={CreditCard}
              label={`${t("accounts.visa")} n°•••• 5837`}
              badge={t("accounts.noOverdraft")}
              amount="-1 143,36 €"
              negative
            />
          </Card>

          {/* Comptes d'épargne */}
          <Card title={t("sections.savings")}>
            <AccountRow
              Icon={PiggyBank}
              label={`${t("accounts.livretA")} n°•••• 4417`}
              sub={`${t("accounts.used")} · ${t("accounts.ceiling")}`}
              amount="19,77 €"
            />
          </Card>

          {/* Cashback */}
          <Card title={t("sections.cashback")}>
            <AccountRow
              Icon={Landmark}
              label={t("accounts.cagnotte")}
              sub={`${t("accounts.pending")} — ${t("accounts.cashbackNote")}`}
              amount="28,15 €"
            />
          </Card>

          {/* Credit promo banner */}
          <div className="flex items-stretch overflow-hidden rounded-xl border border-navy-800/60 bg-gradient-to-r from-navy-900 to-navy-950 text-white shadow-sm">
            <div className="flex flex-1 flex-col gap-2 p-5">
              <span className="w-fit rounded-full bg-gold-500/15 px-2.5 py-0.5 text-[0.6rem] font-semibold uppercase tracking-wider text-gold-300">
                {t("promo.tag")}
              </span>
              <div className="flex items-end gap-2">
                <span className="text-3xl font-bold text-gold-400">{t("promo.rate")}</span>
                <span className="pb-1 text-sm font-medium">{t("promo.title")}</span>
              </div>
              <p className="max-w-md text-[0.62rem] leading-snug text-white/60">
                {t("promo.legal")}
              </p>
              <span className="mt-1 w-fit rounded-lg bg-gold-500 px-4 py-2 text-xs font-semibold text-navy-950">
                {t("promo.cta")}
              </span>
            </div>
            <div
              aria-hidden
              className="hidden w-40 shrink-0 bg-[radial-gradient(circle_at_70%_30%,oklch(0.8_0.066_85/0.45),transparent_60%)] sm:block"
            />
          </div>
        </div>

        {/* Right rail — Liens utiles */}
        <aside className="space-y-4">
          <h2 className="px-1 text-sm font-semibold text-[var(--foreground)]">
            {t("links.title")}
          </h2>
          {linkGroups.map((group) => (
            <div
              key={group.title}
              className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-sm"
            >
              <div className="flex items-center justify-between px-4 py-3">
                <span className="text-xs font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">
                  {group.title}
                </span>
                <ChevronUp className="h-4 w-4 text-[var(--muted-foreground)]" />
              </div>
              <div className="divide-y divide-[var(--border)] border-t border-[var(--border)]">
                {group.items.map(({ label, Icon }) => (
                  <div
                    key={label}
                    className="flex items-center gap-3 px-4 py-3 text-sm text-[var(--foreground)]"
                  >
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--muted)] text-gold-600 dark:text-gold-400">
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="flex-1">{label}</span>
                    <ChevronRight className="h-4 w-4 text-[var(--muted-foreground)]/60" />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </aside>
      </main>

      {/* Footer */}
      <footer className="bg-navy-950 text-white/70 dark:bg-black">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-3 px-5 py-5 text-xs">
          <span>{t("footer.faq")}</span>
          <span>{t("footer.findAgency")}</span>
          <span>{t("footer.otherSites")}</span>
          <div className="ml-auto flex items-center gap-3">
            <Facebook className="h-4 w-4" />
            <Instagram className="h-4 w-4" />
            <Youtube className="h-4 w-4" />
            <span className="ml-2 rounded-md border border-white/30 px-3 py-1.5 font-medium text-white">
              {t("footer.feedback")}
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-sm">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">
          {title}
        </h2>
        <ChevronUp className="h-4 w-4 text-[var(--muted-foreground)]" />
      </div>
      <div className="px-5 py-1">{children}</div>
    </section>
  );
}

function Divider() {
  return <div className="h-px bg-[var(--border)]" />;
}

function AccountRow({
  Icon,
  label,
  sub,
  badge,
  amount,
  negative,
}: {
  Icon: LucideIcon;
  label: string;
  sub?: string;
  badge?: string;
  amount: string;
  negative?: boolean;
}) {
  return (
    <div className="flex items-center gap-3 py-4">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--muted)] text-[var(--muted-foreground)]">
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-[var(--foreground)]">{label}</span>
          {badge && (
            <span className="rounded-full bg-[var(--muted)] px-2 py-0.5 text-[0.6rem] font-medium text-[var(--muted-foreground)]">
              {badge}
            </span>
          )}
        </div>
        {sub && <p className="mt-0.5 truncate text-xs text-[var(--muted-foreground)]">{sub}</p>}
      </div>
      <span
        className={`shrink-0 text-sm font-semibold tabular-nums ${
          negative ? "text-rose-500 dark:text-rose-400" : "text-[var(--foreground)]"
        }`}
      >
        {amount}
      </span>
    </div>
  );
}
