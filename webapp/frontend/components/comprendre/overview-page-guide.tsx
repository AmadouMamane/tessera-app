import {
  Activity,
  ArrowLeft,
  ArrowUpRight,
  CalendarRange,
  ChevronDown,
  CircleAlert,
  Clock,
  Code2,
  Database,
  FileCheck2,
  Gauge,
  GitBranch,
  Layers3,
  ListChecks,
  Network,
  RefreshCw,
  ScanSearch,
  ShieldCheck,
  Sigma,
  Sparkles,
  UsersRound,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";

const ICON_STROKE_WIDTH = 1.75;
const INTRO_BACKGROUND = {
  background:
    "radial-gradient(circle at 82% 42%, rgba(34, 211, 238, 0.08), transparent 28%), radial-gradient(circle at 58% 72%, rgba(167, 139, 250, 0.07), transparent 24%)",
} as const;

const ZONES = [
  { key: "objective", icon: Gauge, tone: "text-[var(--tessera-fg-danger)]", dot: "bg-rose-300" },
  {
    key: "rail",
    icon: CalendarRange,
    tone: "text-[var(--tessera-fg-warning)]",
    dot: "bg-amber-300",
  },
  { key: "agents", icon: UsersRound, tone: "text-[var(--tessera-fg-teal)]", dot: "bg-cyan-300" },
  {
    key: "signals",
    icon: Activity,
    tone: "text-[var(--tessera-fg-success)]",
    dot: "bg-emerald-300",
  },
  { key: "detail", icon: ScanSearch, tone: "text-[var(--tessera-fg-info)]", dot: "bg-blue-300" },
  {
    key: "decision",
    icon: FileCheck2,
    tone: "text-[var(--tessera-fg-accent)]",
    dot: "bg-violet-300",
  },
] as const;

const MODES = [
  { key: "now", icon: Activity },
  { key: "history", icon: CalendarRange },
  { key: "instant", icon: Clock },
] as const;

const HONESTY_NOTES = [
  { key: "dash", icon: CircleAlert },
  { key: "live", icon: Activity },
  { key: "scope", icon: Network },
  { key: "refresh", icon: Layers3 },
] as const;

const DECISIONS = [
  { key: "quality", href: "/surveiller/qualite-ia", icon: Gauge },
  { key: "risk", href: "/agir/incidents-playbooks", icon: CircleAlert },
  { key: "release", href: "/agir/release-control", icon: GitBranch },
  { key: "proof", href: "/prouver/etat-a-date", icon: ShieldCheck },
] as const;

const DATA_FOUNDATIONS = [
  { key: "origin", icon: Database },
  { key: "scope", icon: Network },
  { key: "calculation", icon: Sigma },
  { key: "freshness", icon: RefreshCw },
  { key: "limits", icon: CircleAlert },
] as const;

const CALCULATION_NOTES = ["fleet", "quality", "controls", "risks"] as const;

const TECHNICAL_CONTRACT = ["fleet", "snapshot", "time", "live", "validation"] as const;

export function OverviewPageGuide({ backHref }: { backHref: string }) {
  const t = useTranslations("pageHelp.overview");

  return (
    <article className="mx-auto w-full max-w-[90rem] pb-12">
      <nav className="flex flex-wrap items-center justify-between gap-3 pb-5">
        <Link
          href={backHref}
          className="inline-flex items-center gap-2 text-[0.78rem] font-medium text-[var(--tessera-fg-teal)] transition-colors hover:text-[var(--tessera-text-strong)]"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          {t("back")}
        </Link>
        <span className="font-mono text-xs uppercase tracking-[0.24em] text-[var(--tessera-text-muted)]">
          {t("eyebrow")}
        </span>
      </nav>

      <section className="relative overflow-hidden border-[var(--tessera-border)] border-y py-9 lg:grid lg:grid-cols-[minmax(0,0.82fr)_minmax(34rem,1.18fr)] lg:gap-14 lg:py-12">
        <div className="pointer-events-none absolute inset-0 opacity-60" style={INTRO_BACKGROUND} />
        <div className="relative flex flex-col justify-center">
          <div className="mb-5 flex h-10 w-10 items-center justify-center rounded-full border border-cyan-300/30 text-[var(--tessera-fg-teal)]">
            <Sparkles className="h-[18px] w-[18px]" strokeWidth={ICON_STROKE_WIDTH} aria-hidden />
          </div>
          <h2 className="max-w-[34rem] font-semibold text-[1.35rem] leading-snug text-[var(--tessera-text)]">
            {t("intro.title")}
          </h2>
          <p className="mt-4 max-w-[42rem] text-[0.9rem] leading-7 text-[var(--tessera-text-muted)]">
            {t("intro.body")}
          </p>
          <p className="mt-5 max-w-[40rem] border-cyan-300/50 border-l pl-4 text-[0.82rem] leading-6 text-[var(--tessera-fg-teal)]/80">
            {t("intro.note")}
          </p>
        </div>

        <div className="relative mt-10 lg:mt-0">
          <p className="mb-5 font-mono text-xs uppercase tracking-[0.2em] text-[var(--tessera-fg-teal)]/70">
            {t("flow.label")}
          </p>
          <div className="relative grid gap-0 sm:grid-cols-3">
            <div className="absolute inset-x-0 top-5 hidden h-px bg-gradient-to-r from-rose-300/40 via-cyan-300/50 to-violet-300/40 sm:block" />
            {(["notice", "understand", "act"] as const).map((key) => (
              <div
                key={key}
                className="relative border-[var(--tessera-border)] border-t py-4 sm:border-t-0 sm:px-4 sm:py-0"
              >
                <span className="relative z-10 mb-4 flex h-10 w-10 items-center justify-center rounded-full border border-cyan-300/35 bg-[var(--tessera-bg)] font-mono text-xs text-[var(--tessera-fg-teal)]">
                  <span className="h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_14px_rgba(103,232,249,0.7)]" />
                </span>
                <h3 className="text-[0.86rem] font-semibold text-[var(--tessera-text)]">
                  {t(`flow.${key}.title`)}
                </h3>
                <p className="mt-2 text-[0.76rem] leading-5 text-[var(--tessera-text-muted)]">
                  {t(`flow.${key}.body`)}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-10 py-10 lg:grid-cols-[minmax(16rem,0.42fr)_minmax(0,1fr)] lg:gap-16 lg:py-14">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--tessera-fg-teal)]/70">
            {t("journey.eyebrow")}
          </p>
          <h2 className="mt-3 font-semibold text-[1.2rem] text-[var(--tessera-text)]">
            {t("journey.title")}
          </h2>
          <p className="mt-3 max-w-[30rem] text-[0.84rem] leading-6 text-[var(--tessera-text-muted)]">
            {t("journey.lead")}
          </p>
        </div>

        <div className="relative">
          <div className="absolute bottom-5 left-5 top-5 w-px bg-gradient-to-b from-rose-300/50 via-cyan-300/40 to-violet-300/50" />
          {ZONES.map(({ key, icon: Icon, tone, dot }) => (
            <div
              key={key}
              className="relative grid gap-3 border-[var(--tessera-border)] border-b py-5 pl-14 first:pt-0 last:border-b-0 last:pb-0 md:grid-cols-[minmax(12rem,0.38fr)_minmax(0,1fr)] md:gap-8"
            >
              <span
                className={`absolute left-[0.82rem] top-5 z-10 flex h-7 w-7 items-center justify-center rounded-full border border-current bg-[var(--tessera-bg)] ${tone} first:top-0`}
              >
                <Icon className="h-3.5 w-3.5" strokeWidth={ICON_STROKE_WIDTH} aria-hidden />
              </span>
              <div>
                <span className={`mb-2 block h-1.5 w-1.5 rounded-full ${dot}`} aria-hidden />
                <h3 className="text-[0.88rem] font-semibold text-[var(--tessera-text)]">
                  {t(`journey.zones.${key}.title`)}
                </h3>
              </div>
              <div>
                <p className="text-[0.82rem] leading-6 text-[var(--tessera-text-muted)]">
                  {t(`journey.zones.${key}.body`)}
                </p>
                <p className="mt-2 text-[0.75rem] leading-5 text-[var(--tessera-fg-teal)]/75">
                  {t(`journey.zones.${key}.question`)}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="border-[var(--tessera-border)] border-y py-10 lg:grid lg:grid-cols-[minmax(16rem,0.42fr)_minmax(0,1fr)] lg:gap-16 lg:py-14">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--tessera-fg-warning)]/70">
            {t("time.eyebrow")}
          </p>
          <h2 className="mt-3 font-semibold text-[1.2rem] text-[var(--tessera-text)]">
            {t("time.title")}
          </h2>
          <p className="mt-3 max-w-[30rem] text-[0.84rem] leading-6 text-[var(--tessera-text-muted)]">
            {t("time.lead")}
          </p>
          <div className="mt-6 border-amber-300/40 border-l pl-4">
            <p className="text-[0.78rem] font-medium text-[var(--tessera-fg-warning)]">
              {t("time.scopeTitle")}
            </p>
            <p className="mt-2 text-[0.76rem] leading-5 text-[var(--tessera-text-muted)]">
              {t("time.scopeBody")}
            </p>
          </div>
        </div>

        <div className="mt-8 divide-y divide-[var(--tessera-border)] border-[var(--tessera-border)] border-y lg:mt-0">
          {MODES.map(({ key, icon: Icon }) => (
            <div
              key={key}
              className="grid gap-3 py-5 md:grid-cols-[2.5rem_minmax(10rem,0.34fr)_minmax(0,1fr)] md:items-start md:gap-5"
            >
              <Icon
                className="h-[18px] w-[18px] text-[var(--tessera-fg-warning)]"
                strokeWidth={ICON_STROKE_WIDTH}
                aria-hidden
              />
              <h3 className="text-[0.86rem] font-semibold text-[var(--tessera-text)]">
                {t(`time.modes.${key}.title`)}
              </h3>
              <p className="text-[0.8rem] leading-6 text-[var(--tessera-text-muted)]">
                {t(`time.modes.${key}.body`)}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-10 py-10 lg:grid-cols-[minmax(16rem,0.42fr)_minmax(0,1fr)] lg:gap-16 lg:py-14">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--tessera-fg-success)]/70">
            {t("honesty.eyebrow")}
          </p>
          <h2 className="mt-3 font-semibold text-[1.2rem] text-[var(--tessera-text)]">
            {t("honesty.title")}
          </h2>
          <p className="mt-3 max-w-[30rem] text-[0.84rem] leading-6 text-[var(--tessera-text-muted)]">
            {t("honesty.lead")}
          </p>
        </div>

        <div className="grid gap-x-8 gap-y-7 md:grid-cols-2">
          {HONESTY_NOTES.map(({ key, icon: Icon }) => (
            <div key={key} className="border-emerald-200/20 border-l pl-4">
              <Icon
                className="h-4 w-4 text-[var(--tessera-fg-success)]"
                strokeWidth={ICON_STROKE_WIDTH}
                aria-hidden
              />
              <h3 className="mt-3 text-[0.86rem] font-semibold text-[var(--tessera-text)]">
                {t(`honesty.notes.${key}.title`)}
              </h3>
              <p className="mt-2 text-[0.78rem] leading-6 text-[var(--tessera-text-muted)]">
                {t(`honesty.notes.${key}.body`)}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-[var(--tessera-border)] border-y py-10 lg:grid lg:grid-cols-[minmax(16rem,0.42fr)_minmax(0,1fr)] lg:gap-16 lg:py-14">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--tessera-fg-accent)]/70">
            {t("decisions.eyebrow")}
          </p>
          <h2 className="mt-3 font-semibold text-[1.2rem] text-[var(--tessera-text)]">
            {t("decisions.title")}
          </h2>
          <p className="mt-3 max-w-[30rem] text-[0.84rem] leading-6 text-[var(--tessera-text-muted)]">
            {t("decisions.lead")}
          </p>
        </div>

        <div className="mt-8 divide-y divide-[var(--tessera-border)] lg:mt-0">
          {DECISIONS.map(({ key, href, icon: Icon }) => (
            <Link
              key={key}
              href={href}
              className="group grid gap-3 py-4 first:pt-0 last:pb-0 md:grid-cols-[2.5rem_minmax(11rem,0.38fr)_minmax(0,1fr)_auto] md:items-center md:gap-5"
            >
              <Icon
                className="h-[18px] w-[18px] text-[var(--tessera-fg-accent)]"
                strokeWidth={ICON_STROKE_WIDTH}
                aria-hidden
              />
              <span className="text-[0.84rem] font-semibold text-[var(--tessera-text)]">
                {t(`decisions.items.${key}.title`)}
              </span>
              <span className="text-[0.78rem] leading-5 text-[var(--tessera-text-muted)]">
                {t(`decisions.items.${key}.body`)}
              </span>
              <ArrowUpRight
                className="h-4 w-4 text-[var(--tessera-text-muted)] transition-colors group-hover:text-[var(--tessera-fg-accent)]"
                aria-hidden
              />
            </Link>
          ))}
        </div>
      </section>

      <details className="group border-[var(--tessera-border)] border-y">
        <summary className="flex cursor-pointer list-none items-center gap-4 py-6 marker:content-none focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cyan-300/60">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-cyan-300/30 text-[var(--tessera-fg-teal)]">
            <Database className="h-4 w-4" strokeWidth={ICON_STROKE_WIDTH} aria-hidden />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-[0.88rem] font-semibold text-[var(--tessera-text)]">
              {t("data.title")}
            </span>
            <span className="mt-1 block text-[0.76rem] leading-5 text-[var(--tessera-text-muted)]">
              {t("data.lead")}
            </span>
          </span>
          <ChevronDown
            className="h-4 w-4 shrink-0 text-[var(--tessera-text-muted)] transition-transform group-open:rotate-180"
            strokeWidth={ICON_STROKE_WIDTH}
            aria-hidden
          />
        </summary>

        <div className="border-[var(--tessera-border)] border-t pb-10 pt-8">
          <div className="grid gap-x-10 gap-y-8 md:grid-cols-2 xl:grid-cols-5">
            {DATA_FOUNDATIONS.map(({ key, icon: Icon }) => (
              <div key={key} className="border-cyan-200/20 border-l pl-4">
                <Icon
                  className="h-4 w-4 text-[var(--tessera-fg-teal)]"
                  strokeWidth={ICON_STROKE_WIDTH}
                  aria-hidden
                />
                <h3 className="mt-3 text-[0.84rem] font-semibold text-[var(--tessera-text)]">
                  {t(`data.foundations.${key}.title`)}
                </h3>
                <p className="mt-2 text-[0.76rem] leading-6 text-[var(--tessera-text-muted)]">
                  {t(`data.foundations.${key}.body`)}
                </p>
              </div>
            ))}
          </div>

          <div className="mt-10 grid gap-8 border-[var(--tessera-border)] border-t pt-8 lg:grid-cols-[minmax(14rem,0.3fr)_minmax(0,1fr)] lg:gap-14">
            <div>
              <p className="font-mono text-xs uppercase tracking-[0.2em] text-[var(--tessera-fg-teal)]/70">
                {t("data.calculations.eyebrow")}
              </p>
              <h3 className="mt-3 text-[0.92rem] font-semibold text-[var(--tessera-text)]">
                {t("data.calculations.title")}
              </h3>
              <p className="mt-3 text-[0.78rem] leading-6 text-[var(--tessera-text-muted)]">
                {t("data.calculations.lead")}
              </p>
            </div>
            <div className="divide-y divide-[var(--tessera-border)]">
              {CALCULATION_NOTES.map((key) => (
                <div
                  key={key}
                  className="grid gap-2 py-4 first:pt-0 last:pb-0 md:grid-cols-[minmax(10rem,0.3fr)_minmax(0,1fr)] md:gap-7"
                >
                  <h4 className="text-[0.8rem] font-medium text-[var(--tessera-text)]">
                    {t(`data.calculations.items.${key}.title`)}
                  </h4>
                  <p className="text-[0.76rem] leading-6 text-[var(--tessera-text-muted)]">
                    {t(`data.calculations.items.${key}.body`)}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <details className="group/contract mt-9 border-[var(--tessera-border)] border-t">
            <summary className="flex cursor-pointer list-none items-center gap-3 py-5 marker:content-none focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-300/60">
              <Code2
                className="h-4 w-4 text-[var(--tessera-fg-accent)]"
                strokeWidth={ICON_STROKE_WIDTH}
                aria-hidden
              />
              <span className="flex-1 text-[0.78rem] font-medium text-[var(--tessera-fg-accent)]">
                {t("data.contract.title")}
              </span>
              <ChevronDown
                className="h-4 w-4 text-[var(--tessera-text-muted)] transition-transform group-open/contract:rotate-180"
                strokeWidth={ICON_STROKE_WIDTH}
                aria-hidden
              />
            </summary>
            <div className="grid gap-x-10 gap-y-6 border-violet-200/20 border-l pb-2 pl-5 md:grid-cols-2">
              {TECHNICAL_CONTRACT.map((key) => (
                <div key={key}>
                  <h4 className="font-mono text-xs uppercase tracking-[0.16em] text-[var(--tessera-fg-accent)]/80">
                    {t(`data.contract.items.${key}.title`)}
                  </h4>
                  <p className="mt-2 text-xs leading-6 text-[var(--tessera-text-muted)]">
                    {t(`data.contract.items.${key}.body`)}
                  </p>
                </div>
              ))}
            </div>
          </details>
        </div>
      </details>

      <footer className="grid gap-6 pt-10 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
        <div className="max-w-[58rem]">
          <p className="flex items-center gap-2 font-mono text-xs uppercase tracking-[0.2em] text-[var(--tessera-fg-teal)]/70">
            <ListChecks className="h-4 w-4" aria-hidden />
            {t("closing.eyebrow")}
          </p>
          <p className="mt-3 text-[0.92rem] leading-7 text-[var(--tessera-text)]">
            {t("closing.body")}
          </p>
        </div>
        <Link
          href="/comprendre"
          className="inline-flex items-center gap-2 text-[0.78rem] font-medium text-[var(--tessera-fg-teal)] transition-colors hover:text-[var(--tessera-text-strong)]"
        >
          {t("closing.global")}
          <ArrowUpRight className="h-4 w-4" aria-hidden />
        </Link>
      </footer>
    </article>
  );
}
