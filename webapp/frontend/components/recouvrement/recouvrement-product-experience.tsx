"use client";

import {
  Bell,
  CalendarDays,
  Check,
  ChevronDown,
  ChevronRight,
  CircleCheck,
  CircleHelp,
  Clock3,
  FileText,
  Folder,
  Home,
  Info,
  LockKeyhole,
  Mail,
  PenLine,
  Phone,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import { useLocale } from "next-intl";

import { CreditAuroreLogo } from "@/components/brand/credit-aurore-logo";
import { cn } from "@/lib/cn";

const navigation = [
  { label: "Ma journée", Icon: Home, active: true },
  { label: "Dossiers", Icon: Folder },
  { label: "Relances", Icon: Send, count: 14 },
  { label: "Échéanciers", Icon: CalendarDays, count: 8 },
  { label: "Situations à vérifier", Icon: ShieldCheck, count: 5 },
  { label: "Historique", Icon: Clock3 },
];

const reasons = [
  "Promesse de paiement non tenue le 12 juin.",
  "Retard significatif : 32 jours",
  "Échéancier envisageable",
  "Contact autorisé aujourd'hui de 8h à 20h",
];

const assistantActions = [
  {
    label: "Résumer ce dossier",
    description: "Obtenir les points clés en quelques secondes",
    Icon: FileText,
  },
  {
    label: "Rédiger une relance",
    description: "Message personnalisé prêt à envoyer",
    Icon: PenLine,
  },
  {
    label: "Vérifier une règle",
    description: "Contrôler la conformité en un clic",
    Icon: ShieldCheck,
  },
  {
    label: "Proposer un échéancier",
    description: "Simulation adaptée à la situation",
    Icon: CalendarDays,
  },
];

const nextItems = [
  { value: "4", label: "Relances", detail: "à valider", Icon: Send, accent: "orange" },
  { value: "3", label: "Échéanciers", detail: "à confirmer", Icon: CalendarDays, accent: "violet" },
  { value: "5", label: "Situations", detail: "à vérifier", Icon: ShieldCheck, accent: "violet" },
];

const quickActions = [
  { label: "Préparer une relance", detail: "Rédiger un message personnalisé", Icon: FileText },
  { label: "Créer un échéancier", detail: "Proposer un plan de remboursement", Icon: CalendarDays },
  { label: "Reporter un dossier", detail: "Choisir une nouvelle date", Icon: FileText },
  { label: "Escalader à un responsable", detail: "Demander une validation", Icon: Users },
  { label: "Consulter l'historique", detail: "Voir toutes les actions", Icon: Clock3 },
];

const cardClass =
  "rounded-[6px] border border-[#dcdee6] bg-white shadow-[0_2px_8px_rgba(0,0,0,0.06)]";

function CountBadge({ count, className }: { count: number; className?: string }) {
  return (
    <span
      className={cn(
        "grid h-6 min-w-6 place-items-center rounded-full bg-[#f1efeb] px-2 font-semibold text-[#2b2d36] text-xs",
        className,
      )}
    >
      {count}
    </span>
  );
}

export function RecouvrementProductExperience() {
  const locale = useLocale();
  const assistantHref = `/${locale}/recouvrement`;

  return (
    <div className="min-h-screen bg-[#c9ccd1] font-sans text-[#050816]">
      <div className="mx-auto min-h-screen max-w-[1718px] bg-white">
        <div className="flex min-h-screen flex-col">
          <div className="flex min-h-9 items-center justify-between gap-4 bg-[#050816] px-4 text-white text-xs font-bold sm:px-6">
            <span className="inline-flex items-center gap-2">
              Espace recouvrement Crédit Aurore
              <ChevronRight className="h-4 w-4" />
            </span>
            <span className="hidden items-center gap-2 sm:inline-flex">
              <CircleHelp className="h-4 w-4" />
              Aide et contacts
            </span>
          </div>

          <header className="flex min-h-[76px] shrink-0 flex-wrap items-center gap-5 border-[#d0d0d0] border-b bg-white px-4 py-3 sm:px-6 lg:flex-nowrap lg:px-[23px]">
            <CreditAuroreLogo className="min-w-[250px] gap-[9px]" gradientIdPrefix="caRecLogo" />
            <nav
              className="hidden flex-1 items-center gap-7 lg:flex"
              aria-label="Navigation produit"
            >
              <span className="relative font-bold text-[#b99245] text-[13px]">
                Recouvrement
                <span className="-bottom-[29px] absolute right-0 left-0 h-[3px] bg-[#b99245]" />
              </span>
              <span className="font-bold text-[13px] text-[#222]">Pilotage</span>
              <span className="font-bold text-[13px] text-[#222]">Règles métier</span>
              <span className="font-bold text-[13px] text-[#222]">Reporting</span>
            </nav>
            <label className="relative order-last block w-full max-w-[360px] md:order-none lg:ml-auto">
              <Search className="-translate-y-1/2 absolute top-1/2 left-4 h-5 w-5 text-[#050816]" />
              <input
                aria-label="Rechercher"
                placeholder="Rechercher un dossier, un client, ..."
                className="h-11 w-full rounded-[4px] border border-[#d7d9e1] bg-white pr-4 pl-12 text-[#050816] text-sm outline-none transition placeholder:text-[#5d6275] focus:border-[#b99245] focus:ring-2 focus:ring-[#b99245]/20"
              />
            </label>
            <div className="flex items-center gap-4 sm:gap-6">
              <button
                type="button"
                className="relative flex flex-col items-center gap-1 text-[10.5px]"
              >
                <Bell className="h-[22px] w-[22px]" />
                <span className="-top-1 absolute right-1 grid h-4 min-w-4 place-items-center rounded-full bg-[#b99245] px-1 text-[#050816] text-[9px]">
                  3
                </span>
                Notifications
              </button>
              <button type="button" className="flex items-center gap-3">
                <span className="grid h-10 w-10 place-items-center rounded-full bg-[#fbf0dd] font-bold text-[#050816]">
                  JD
                </span>
                <span className="hidden text-left sm:block">
                  <span className="block font-bold text-sm">Julie Dubois</span>
                  <span className="block text-[#050816]/65 text-xs">Chargée de recouvrement</span>
                </span>
                <ChevronDown className="h-5 w-5" />
              </button>
            </div>
          </header>

          <div className="grid min-h-0 flex-1 lg:grid-cols-[258px_minmax(0,1fr)]">
            <aside className="hidden min-h-0 flex-col border-[#d8d8d8] border-r bg-white lg:flex">
              <div className="border-[#e2e2e6] border-b px-6 py-8">
                <p className="font-extrabold text-[#b99245] text-sm uppercase tracking-[0]">
                  Recouvrement
                </p>
                <p className="mt-2 text-[#565656] text-xs leading-5">
                  File interne et actions dossiers
                </p>
              </div>
              <nav className="flex flex-col gap-1 px-4 py-6" aria-label="Navigation recouvrement">
                {navigation.map(({ label, Icon, count, active }) => (
                  <button
                    key={label}
                    type="button"
                    className={cn(
                      "flex min-h-[52px] items-center gap-4 rounded-[5px] px-4 text-left font-bold text-[0.92rem] transition",
                      active
                        ? "bg-[#fbf0dd] text-[#050816] shadow-[inset_3px_0_0_#b99245]"
                        : "text-[#333] hover:bg-[#f5f4f2]",
                    )}
                  >
                    <Icon
                      className={cn(
                        "h-5 w-5 shrink-0",
                        active ? "fill-current text-[#b99245]" : "text-[#1d2334]",
                      )}
                    />
                    <span>{label}</span>
                    {count ? <CountBadge count={count} className="ml-auto" /> : null}
                  </button>
                ))}
              </nav>
              <div className="mt-auto border-[#e2e2e6] border-t px-6 py-7">
                <div className="flex items-start gap-3 text-[#050816] text-sm leading-5">
                  <LockKeyhole className="mt-0.5 h-5 w-5 shrink-0" />
                  <p>
                    Accès limité
                    <br />
                    aux dossiers assignés
                  </p>
                </div>
                <div className="mt-7 flex items-center gap-3 text-sm">
                  <span className="h-3 w-3 rounded-full bg-[#139b45]" />
                  En ligne
                </div>
              </div>
            </aside>

            <main className="min-h-0 overflow-y-auto bg-[radial-gradient(circle_at_62%_8%,rgba(231,235,246,0.58),transparent_32%),#fbfbfd]">
              <div className="px-4 py-10 sm:px-6 lg:py-11">
                <div className="mx-auto max-w-[1274px]">
                  <div className="mb-8">
                    <h1 className="!font-sans !text-[#050816] font-extrabold text-[2rem] leading-tight tracking-[0]">
                      Bonjour Julie,
                    </h1>
                    <p className="mt-2 text-[#071044] text-[1.12rem]">
                      Votre file du jour est prête.
                    </p>
                  </div>

                  <div className="grid gap-[31px] xl:grid-cols-[minmax(0,818px)_377px]">
                    <section className="min-w-0">
                      <section className={cn(cardClass, "p-6 sm:p-8")}>
                        <div className="mb-5">
                          <span className="inline-flex rounded-[4px] bg-[#fff3e4] px-3 py-1.5 font-bold text-[#d97700] text-xs uppercase">
                            À traiter maintenant
                          </span>
                        </div>
                        <div className="grid items-center gap-8 lg:grid-cols-[360px_minmax(0,1fr)_96px]">
                          <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:gap-7">
                            <span className="grid h-[78px] w-[78px] shrink-0 place-items-center rounded-full bg-[#fbf0dd] font-semibold text-[#d97700] text-[1.65rem] shadow-[inset_0_1px_0_rgba(255,255,255,0.9)]">
                              MD
                            </span>
                            <div className="min-w-0">
                              <div className="flex flex-nowrap items-center gap-3">
                                <h2 className="!font-sans !text-[#071044] font-bold text-[1.5rem] leading-8 tracking-[0]">
                                  RC-2048
                                </h2>
                                <span className="shrink-0 rounded-[6px] bg-[#ffe8e5] px-2.5 py-1 font-medium text-[#f23932] text-[0.68rem]">
                                  Promesse non tenue
                                </span>
                              </div>
                              <p className="mt-2 text-[0.9rem] leading-[1.2rem]">M. D.</p>
                              <div className="mt-3 flex items-center gap-5 font-semibold text-[0.94rem] leading-5">
                                <span>840,00 €</span>
                                <span className="h-1 w-1 rounded-full bg-[#071044]" />
                                <span className="font-medium">Retard 32 jours</span>
                              </div>
                              <div className="mt-4 inline-flex items-center gap-3 rounded-[5px] bg-[#e9f7e9] px-4 py-2 text-[#145b2b] text-[0.86rem] leading-[1.15rem]">
                                <CircleCheck className="h-4 w-4 shrink-0" />
                                <span>
                                  Contact autorisé aujourd'hui
                                  <br />
                                  de 8h à 20h
                                </span>
                              </div>
                            </div>
                          </div>

                          <div className="border-[#dfe2ec] border-t pt-6 lg:border-t-0 lg:border-l lg:pt-0 lg:pl-8">
                            <h3 className="mb-4 !font-sans !text-[#d97700] font-bold text-sm">
                              Pourquoi ce dossier ?
                            </h3>
                            <ul className="space-y-2.5 text-[0.78rem]">
                              {reasons.map((reason) => (
                                <li key={reason} className="flex items-start gap-3">
                                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-[#158d3c]" />
                                  <span className="leading-[1.15rem]">{reason}</span>
                                </li>
                              ))}
                            </ul>
                          </div>

                          <div className="relative hidden h-24 w-24 place-items-center rounded-full bg-[#fbf0dd] text-[#d97700] shadow-[inset_0_1px_0_rgba(255,255,255,0.9)] lg:grid">
                            <CalendarDays className="h-12 w-12" strokeWidth={1.8} />
                            <Phone
                              className="absolute right-[12px] bottom-[10px] h-6 w-6 rotate-[-18deg]"
                              strokeWidth={2.2}
                            />
                          </div>
                        </div>

                        <div className="mt-10 flex flex-col gap-5 border-[#e4e6ee] border-t pt-6 lg:flex-row lg:items-center lg:justify-between">
                          <div>
                            <p className="font-bold text-sm">Action recommandée</p>
                            <p className="mt-1 text-[0.9rem]">
                              Préparer un échéancier de remboursement.
                            </p>
                          </div>
                          <div className="flex flex-wrap items-center gap-3 lg:flex-nowrap">
                            <button
                              type="button"
                              className="inline-flex h-11 w-[196px] items-center justify-center gap-3 rounded-[8px] bg-[linear-gradient(180deg,#e38a00,#cf7300)] font-bold text-sm text-white shadow-[0_10px_22px_rgba(217,119,0,0.22)] transition hover:bg-[#c96f00]"
                            >
                              Préparer l'échéancier
                              <ChevronRight className="h-5 w-5" />
                            </button>
                            <button
                              type="button"
                              className="inline-flex h-11 w-[122px] items-center justify-center gap-3 rounded-[8px] border border-[#cfd4e3] bg-white font-semibold text-sm transition hover:bg-[#f7f8fb]"
                            >
                              Reporter
                              <Clock3 className="h-5 w-5" />
                            </button>
                            <a
                              href={assistantHref}
                              className="inline-flex h-11 w-[198px] items-center justify-center gap-2 rounded-lg px-1.5 font-semibold text-[#6048ff] text-[0.74rem] transition hover:bg-[#f4f1ff]"
                            >
                              <Sparkles className="h-4 w-4" />
                              Préparer avec l'assistant
                            </a>
                          </div>
                        </div>
                      </section>

                      <section className="relative mt-8 overflow-hidden rounded-[6px] border border-[#c8bbff] bg-[linear-gradient(120deg,#fbfaff,#f9f7ff)] p-6 shadow-[0_10px_24px_rgba(96,72,255,0.045)]">
                        <Sparkles className="-right-1 absolute top-14 h-16 w-16 text-[#7a63ff]/22" />
                        <Sparkles className="absolute right-8 bottom-8 h-7 w-7 text-[#7a63ff]/18" />
                        <div className="mb-6 flex items-center justify-between gap-4">
                          <div>
                            <h2 className="flex items-center gap-3 !font-sans !text-[#6048ff] font-bold text-sm uppercase tracking-[0]">
                              <Sparkles className="h-5 w-5" />
                              Assistant de traitement <span className="font-medium">— RC-2048</span>
                            </h2>
                            <p className="mt-2 text-sm">
                              L'assistant vous aide à agir plus vite et en toute conformité.
                            </p>
                          </div>
                          <a
                            href={assistantHref}
                            className="inline-flex h-9 items-center gap-2 rounded-[8px] border border-[#c7bbff] bg-white px-4 font-semibold text-[#6048ff] text-xs transition hover:bg-[#f4f1ff]"
                          >
                            Ouvrir l'assistant complet
                            <ChevronRight className="h-4 w-4" />
                          </a>
                        </div>
                        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                          {assistantActions.map(({ label, description, Icon }) => (
                            <a
                              key={label}
                              href={assistantHref}
                              className="flex h-[108px] items-center gap-3 overflow-hidden rounded-[5px] border border-[#e2defd] bg-white p-3 text-left shadow-[0_6px_16px_rgba(96,72,255,0.025)] transition hover:border-[#b7aaff] hover:bg-[#fbfaff]"
                            >
                              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-[#f0edff] text-[#6048ff]">
                                <Icon className="h-5 w-5" />
                              </span>
                              <span className="min-w-0">
                                <span className="block font-bold text-[0.72rem] leading-4">
                                  {label}
                                </span>
                                <span className="mt-1.5 block text-[0.64rem] leading-[1.05rem]">
                                  {description}
                                </span>
                              </span>
                              <ChevronRight className="ml-auto h-3.5 w-3.5 shrink-0" />
                            </a>
                          ))}
                        </div>
                      </section>

                      <section className="mt-10">
                        <h2 className="mb-5 !font-sans !text-[#050816] font-extrabold text-2xl leading-7">
                          À faire ensuite
                        </h2>
                        <div className="grid gap-6 md:grid-cols-3">
                          {nextItems.map(({ value, label, detail, Icon, accent }) => (
                            <button
                              key={label}
                              type="button"
                              className="flex h-[154px] flex-col rounded-[6px] border border-[#dfe2ec] bg-white p-6 text-left shadow-[0_2px_8px_rgba(0,0,0,0.055)] transition hover:border-[#d97700]/40 hover:shadow-[0_8px_20px_rgba(7,16,68,0.07)]"
                            >
                              <span className="flex items-center gap-4">
                                <span
                                  className={cn(
                                    "grid h-12 w-12 place-items-center rounded-full",
                                    accent === "orange"
                                      ? "bg-[#fff1dc] text-[#e48700]"
                                      : "bg-[#f0edff] text-[#6048ff]",
                                  )}
                                >
                                  <Icon className="h-6 w-6" />
                                </span>
                                <span className="font-bold text-[2.2rem] leading-none">
                                  {value}
                                </span>
                                <span className="font-bold text-sm">
                                  {label}
                                  <br />
                                  <span className="font-semibold">{detail}</span>
                                </span>
                              </span>
                              <span className="mt-auto flex items-center justify-end border-[#e4e6ee] border-t pt-3 font-semibold text-[#0047ff] text-sm">
                                Voir la liste
                                <ChevronRight className="ml-auto h-5 w-5 text-[#071044]" />
                              </span>
                            </button>
                          ))}
                        </div>
                      </section>

                      <section className="mt-10 flex min-h-[72px] flex-col items-start gap-3 rounded-[6px] border border-[#dfe2ec] bg-white px-6 py-4 shadow-[0_2px_8px_rgba(0,0,0,0.055)] sm:flex-row sm:items-center">
                        <Info className="mr-4 h-5 w-5" />
                        <span className="mr-6 font-bold">A noter aujourd'hui</span>
                        <span className="hidden h-8 w-px bg-[#dfe2ec] sm:block" />
                        <p className="text-sm text-[#071044]/80 sm:ml-6">
                          3 dossiers sont joignables entre 17h et 19h selon les règles de contact.
                        </p>
                        <button
                          type="button"
                          className="inline-flex items-center gap-3 font-semibold text-[#0047ff] text-sm sm:ml-auto"
                        >
                          Voir lesquels
                          <ChevronRight className="h-5 w-5" />
                        </button>
                      </section>
                    </section>

                    <aside className="space-y-8 xl:sticky xl:top-8 xl:self-start">
                      <section className={cn(cardClass, "overflow-hidden")}>
                        <h2 className="border-[#e4e6ee] border-b px-6 py-6 !font-sans !text-[#050816] font-extrabold text-lg">
                          Actions rapides
                        </h2>
                        <div className="divide-y divide-[#e4e6ee]">
                          {quickActions.map(({ label, detail, Icon }) => (
                            <button
                              key={label}
                              type="button"
                              className="flex w-full items-center gap-4 px-6 py-5 text-left transition hover:bg-[#f7f8fb]"
                            >
                              <Icon className="h-6 w-6 shrink-0" />
                              <span>
                                <span className="block font-bold text-sm">{label}</span>
                                <span className="mt-1 block text-xs">{detail}</span>
                              </span>
                              <ChevronRight className="ml-auto h-5 w-5" />
                            </button>
                          ))}
                        </div>
                      </section>

                      <section className={cn(cardClass, "p-6")}>
                        <div className="mb-6 flex items-center justify-between">
                          <h2 className="!font-sans !text-[#050816] font-extrabold text-lg">
                            Cadre de contact
                          </h2>
                          <span className="rounded-full bg-[#e4f5dd] px-3 py-1 font-bold text-[#187434] text-xs">
                            RC-2048
                          </span>
                        </div>
                        <div className="mb-6 flex items-start gap-4 rounded-[5px] bg-[#edf9df] px-5 py-5 text-[#145b2b]">
                          <CircleCheck className="mt-0.5 h-5 w-5" />
                          <p className="font-semibold text-sm">
                            Contact autorisé aujourd'hui
                            <br />
                            <span className="font-medium">8h - 20h</span>
                          </p>
                        </div>
                        <div className="space-y-5 text-sm">
                          <div>
                            <p className="mb-2 font-bold">Canal conseillé</p>
                            <p className="flex items-center gap-3">
                              <Phone className="h-5 w-5" />
                              Appel sortant
                            </p>
                          </div>
                          <div>
                            <p className="mb-2 font-bold">Alternative</p>
                            <p className="flex items-center gap-3">
                              <Mail className="h-5 w-5" />
                              Email de confirmation
                            </p>
                          </div>
                        </div>
                      </section>

                      <a
                        href={assistantHref}
                        className="flex w-full items-center gap-4 rounded-[6px] border border-[#f1d8ab] bg-[linear-gradient(90deg,#fff8ec,#fff2de)] p-6 text-left shadow-[0_2px_8px_rgba(0,0,0,0.05)] transition hover:bg-[#ffefcf]"
                      >
                        <Sparkles className="h-7 w-7 text-[#071044]" />
                        <span>
                          <span className="block font-bold text-sm">
                            Besoin d'aide sur un dossier ?
                          </span>
                          <span className="mt-1 block text-xs">
                            Consultez les règles applicables
                          </span>
                        </span>
                        <ChevronRight className="ml-auto h-5 w-5" />
                      </a>
                    </aside>
                  </div>
                </div>
              </div>
            </main>
          </div>
        </div>
      </div>
    </div>
  );
}
