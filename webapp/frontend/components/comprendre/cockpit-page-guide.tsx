import {
  ArrowLeft,
  ArrowUpRight,
  CircleAlert,
  Database,
  Eye,
  ScanSearch,
  Sparkles,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import type { ContextualHelpSection } from "@/lib/contextual-help";

const ICON_STROKE_WIDTH = 1.75;
const STEP_ICONS = [Eye, ScanSearch, ArrowUpRight] as const;
const GUIDE_BACKGROUND = {
  background:
    "radial-gradient(circle at 16% 32%, rgba(34, 211, 238, 0.08), transparent 28%), radial-gradient(circle at 78% 72%, rgba(167, 139, 250, 0.07), transparent 26%)",
} as const;

interface ReadingStep {
  title: string;
  body: string;
}

export function CockpitPageGuide({
  backHref,
  guideKey,
  section,
}: {
  backHref: string;
  guideKey: string;
  section: ContextualHelpSection;
}) {
  const t = useTranslations("pageHelp");
  const readingSteps = t.raw(`sharedGuide.reading.${section}`) as ReadingStep[];

  return (
    <article className="mx-auto w-full max-w-[90rem] pb-12">
      <nav className="flex flex-wrap items-center justify-between gap-3 pb-5">
        <Link
          href={backHref}
          className="inline-flex items-center gap-2 text-[0.78rem] font-medium text-cyan-200 transition-colors hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          {t("sharedGuide.back", { page: t(`guides.${guideKey}.title`) })}
        </Link>
        <span className="font-mono text-[0.62rem] uppercase tracking-[0.24em] text-[var(--tessera-text-muted)]">
          {t("sharedGuide.eyebrow")}
        </span>
      </nav>

      <section className="relative overflow-hidden border-[var(--tessera-border)] border-y py-10 lg:grid lg:grid-cols-[minmax(0,0.82fr)_minmax(26rem,1.18fr)] lg:gap-16 lg:py-14">
        <div className="pointer-events-none absolute inset-0 opacity-70" style={GUIDE_BACKGROUND} />
        <div className="relative">
          <div className="mb-5 flex h-10 w-10 items-center justify-center rounded-full border border-cyan-300/30 text-cyan-200">
            <Sparkles className="h-[18px] w-[18px]" strokeWidth={ICON_STROKE_WIDTH} aria-hidden />
          </div>
          <p className="font-mono text-[0.62rem] uppercase tracking-[0.2em] text-cyan-200/70">
            {t("sharedGuide.purpose")}
          </p>
          <h2 className="mt-3 max-w-[38rem] font-semibold text-[1.35rem] leading-snug text-[var(--tessera-text)]">
            {t(`guides.${guideKey}.question`)}
          </h2>
        </div>

        <div className="relative mt-10 border-cyan-300/35 border-l pl-5 lg:mt-0 lg:self-end">
          <p className="font-mono text-[0.62rem] uppercase tracking-[0.2em] text-cyan-200/70">
            {t("sharedGuide.start")}
          </p>
          <p className="mt-3 max-w-[48rem] text-[0.9rem] leading-7 text-[var(--tessera-text-muted)]">
            {t(`guides.${guideKey}.start`)}
          </p>
        </div>
      </section>

      <section className="py-11 lg:py-14">
        <div className="mb-8 max-w-[44rem]">
          <p className="font-mono text-[0.62rem] uppercase tracking-[0.2em] text-cyan-200/70">
            {t("sharedGuide.readingEyebrow")}
          </p>
          <h2 className="mt-3 font-semibold text-[1.18rem] text-[var(--tessera-text)]">
            {t("sharedGuide.readingTitle")}
          </h2>
        </div>

        <div className="relative grid gap-0 lg:grid-cols-3">
          <div className="absolute left-[8%] right-[8%] top-5 hidden h-px bg-gradient-to-r from-cyan-300/35 via-emerald-300/45 to-violet-300/35 lg:block" />
          {readingSteps.map((step, index) => {
            const Icon = STEP_ICONS[index] ?? Eye;
            return (
              <div
                key={step.title}
                className="relative border-[var(--tessera-border)] border-t py-5 lg:border-t-0 lg:px-6 lg:py-0"
              >
                <span className="relative z-10 mb-4 flex h-10 w-10 items-center justify-center rounded-full border border-cyan-300/35 bg-[var(--tessera-bg)] text-cyan-200">
                  <Icon className="h-4 w-4" strokeWidth={ICON_STROKE_WIDTH} aria-hidden />
                </span>
                <h3 className="text-[0.88rem] font-semibold text-[var(--tessera-text)]">
                  {step.title}
                </h3>
                <p className="mt-2 max-w-[30rem] text-[0.78rem] leading-6 text-[var(--tessera-text-muted)]">
                  {step.body}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      <section className="grid gap-8 border-[var(--tessera-border)] border-y py-9 lg:grid-cols-[minmax(12rem,0.32fr)_minmax(0,1fr)] lg:gap-16">
        <div>
          <p className="font-mono text-[0.62rem] uppercase tracking-[0.2em] text-emerald-200/75">
            {t("sharedGuide.actionEyebrow")}
          </p>
          <h2 className="mt-3 font-semibold text-[1.08rem] text-[var(--tessera-text)]">
            {t("sharedGuide.actionTitle")}
          </h2>
        </div>
        <p className="border-emerald-300/35 border-l pl-5 text-[0.9rem] leading-7 text-[var(--tessera-text-muted)]">
          {t(`guides.${guideKey}.action`)}
        </p>
      </section>

      <section className="py-10">
        <details className="group border-[var(--tessera-border)] border-b pb-8">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-5 py-3 text-[0.86rem] font-medium text-[var(--tessera-text)]">
            <span className="inline-flex items-center gap-3">
              <Database
                className="h-[18px] w-[18px] text-cyan-200"
                strokeWidth={ICON_STROKE_WIDTH}
                aria-hidden
              />
              {t("sharedGuide.dataTitle")}
            </span>
            <span className="text-[var(--tessera-text-muted)] transition-transform group-open:rotate-45">
              +
            </span>
          </summary>
          <div className="grid gap-8 pt-6 lg:grid-cols-2 lg:gap-14">
            <div>
              <p className="font-mono text-[0.6rem] uppercase tracking-[0.18em] text-cyan-200/70">
                {t("sharedGuide.dataOrigin")}
              </p>
              <p className="mt-3 text-[0.8rem] leading-6 text-[var(--tessera-text-muted)]">
                {t(`guides.${guideKey}.data`)}
              </p>
            </div>
            <div>
              <p className="inline-flex items-center gap-2 font-mono text-[0.6rem] uppercase tracking-[0.18em] text-amber-200/75">
                <CircleAlert className="h-3.5 w-3.5" aria-hidden />
                {t("sharedGuide.dataLimit")}
              </p>
              <p className="mt-3 text-[0.8rem] leading-6 text-[var(--tessera-text-muted)]">
                {t(`guides.${guideKey}.limit`)}
              </p>
            </div>
          </div>
        </details>
      </section>
    </article>
  );
}
