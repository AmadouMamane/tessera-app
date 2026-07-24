import {
  ArrowLeft,
  ArrowUpRight,
  BookOpenCheck,
  ChevronDown,
  CircleAlert,
  Code2,
  Database,
  Eye,
  FileCheck2,
  ListChecks,
  Network,
  RefreshCw,
  ScanSearch,
  Sparkles,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import type { ContextualHelpSection } from "@/lib/contextual-help";
import {
  CONTEXTUAL_HELP_VIEW_GROUPS,
  activeHelpView,
  contextualHelpViewAnchor,
  sourceHrefForHelpView,
} from "@/lib/contextual-help-views";

const ICON_STROKE_WIDTH = 1.75;
const STEP_ICONS = [Eye, ScanSearch, ArrowUpRight] as const;
const DATA_ICONS = [Database, Network, RefreshCw, CircleAlert] as const;
const GUIDE_BACKGROUND = {
  background:
    "radial-gradient(circle at 16% 32%, rgba(34, 211, 238, 0.08), transparent 28%), radial-gradient(circle at 78% 72%, rgba(167, 139, 250, 0.07), transparent 26%)",
} as const;

interface ReadingStep {
  title: string;
  body: string;
}

const TECHNICAL_ITEMS = ["reading", "scope", "time", "operation", "validation", "limits"] as const;

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
  const all = useTranslations();
  const readingSteps = t.raw(`sharedGuide.reading.${section}`) as ReadingStep[];
  const examples = t.raw(`sharedGuide.examples.${section}.items`) as ReadingStep[];
  const viewGroups = CONTEXTUAL_HELP_VIEW_GROUPS[guideKey] ?? [];

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

      <section className="relative overflow-hidden border-[var(--tessera-border)] border-y px-5 py-10 lg:grid lg:grid-cols-[minmax(0,0.82fr)_minmax(26rem,1.18fr)] lg:gap-16 lg:py-14">
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

      {viewGroups.length ? (
        <section className="grid gap-10 py-11 lg:grid-cols-[minmax(16rem,0.34fr)_minmax(0,1fr)] lg:gap-16 lg:py-14">
          <div>
            <p className="font-mono text-[0.62rem] uppercase tracking-[0.2em] text-violet-200/75">
              {t("viewAtlas.eyebrow")}
            </p>
            <h2 className="mt-3 font-semibold text-[1.18rem] text-[var(--tessera-text)]">
              {t("viewAtlas.title")}
            </h2>
            <p className="mt-3 max-w-[30rem] text-[0.82rem] leading-6 text-[var(--tessera-text-muted)]">
              {t("viewAtlas.lead")}
            </p>
          </div>

          <div className="space-y-9">
            {viewGroups.map((group) => {
              const active = activeHelpView(backHref, group);
              return (
                <section key={group.key} aria-labelledby={`guide-group-${guideKey}-${group.key}`}>
                  <div className="mb-2 flex items-center gap-3 border-[var(--tessera-border)] border-b pb-3">
                    <BookOpenCheck
                      className="h-4 w-4 text-violet-200"
                      strokeWidth={ICON_STROKE_WIDTH}
                      aria-hidden
                    />
                    <h3
                      id={`guide-group-${guideKey}-${group.key}`}
                      className="text-[0.86rem] font-semibold text-[var(--tessera-text)]"
                    >
                      {all(group.titleKey)}
                    </h3>
                  </div>
                  <div className="divide-y divide-[var(--tessera-border)]">
                    {group.views.map((view) => {
                      const current = active === view.key;
                      const anchor = contextualHelpViewAnchor(guideKey, group.key, view.key);
                      return (
                        <div
                          key={view.key}
                          id={anchor}
                          className={`grid scroll-mt-24 gap-3 py-4 md:grid-cols-[minmax(10rem,0.28fr)_minmax(0,1fr)_auto] md:items-start md:gap-7 ${
                            current ? "border-cyan-300/45 border-l pl-4" : ""
                          }`}
                        >
                          <div>
                            <h4 className="text-[0.82rem] font-semibold text-[var(--tessera-text)]">
                              {all(view.labelKey)}
                            </h4>
                            {current ? (
                              <span className="mt-1 inline-block font-mono text-[0.58rem] uppercase tracking-[0.16em] text-cyan-200">
                                {t("viewAtlas.current")}
                              </span>
                            ) : null}
                          </div>
                          <p className="text-[0.78rem] leading-6 text-[var(--tessera-text-muted)]">
                            {t(`viewDescriptions.${guideKey}.${group.key}.${view.key}`)}
                          </p>
                          <Link
                            href={sourceHrefForHelpView(backHref, group, view.key)}
                            aria-label={t("viewAtlas.open", { view: all(view.labelKey) })}
                            className="inline-flex items-center gap-2 text-[0.72rem] font-medium text-violet-200 transition-colors hover:text-white"
                          >
                            {t("viewAtlas.see")}
                            <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
                          </Link>
                        </div>
                      );
                    })}
                  </div>
                </section>
              );
            })}
          </div>
        </section>
      ) : null}

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
          <div className="absolute inset-x-0 top-5 hidden h-px bg-gradient-to-r from-cyan-300/35 via-emerald-300/45 to-violet-300/35 lg:block" />
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
        <details className="group border-[var(--tessera-border)] border-y">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-5 py-6 text-[0.86rem] font-medium text-[var(--tessera-text)] marker:content-none">
            <span className="inline-flex items-center gap-3">
              <Database
                className="h-[18px] w-[18px] text-cyan-200"
                strokeWidth={ICON_STROKE_WIDTH}
                aria-hidden
              />
              {t("sharedGuide.dataTitle")}
            </span>
            <ChevronDown className="h-4 w-4 text-[var(--tessera-text-muted)] transition-transform group-open:rotate-180" />
          </summary>
          <div className="grid gap-x-10 gap-y-8 border-[var(--tessera-border)] border-t py-8 md:grid-cols-2 xl:grid-cols-4">
            {(["origin", "scope", "freshness", "limit"] as const).map((key, index) => {
              const Icon = DATA_ICONS[index] ?? Database;
              const body =
                key === "origin"
                  ? t(`guides.${guideKey}.data`)
                  : key === "limit"
                    ? t(`guides.${guideKey}.limit`)
                    : t(`sharedGuide.dataFoundations.${key}.body`);
              return (
                <div
                  key={key}
                  className={`${key === "limit" ? "border-amber-200/25" : "border-cyan-200/20"} border-l pl-4`}
                >
                  <Icon
                    className={`h-4 w-4 ${key === "limit" ? "text-amber-200" : "text-cyan-200"}`}
                    strokeWidth={ICON_STROKE_WIDTH}
                    aria-hidden
                  />
                  <h3 className="mt-3 text-[0.82rem] font-semibold text-[var(--tessera-text)]">
                    {t(`sharedGuide.dataFoundations.${key}.title`)}
                  </h3>
                  <p className="mt-2 text-[0.76rem] leading-6 text-[var(--tessera-text-muted)]">
                    {body}
                  </p>
                </div>
              );
            })}
            <div className="md:col-span-2 xl:col-span-4">
              <p className="border-cyan-200/20 border-l pl-4 text-[0.76rem] leading-6 text-cyan-100/75">
                {t("sharedGuide.dataReadingRule")}
              </p>
            </div>
          </div>

          <div className="grid gap-8 border-[var(--tessera-border)] border-t py-9 lg:grid-cols-[minmax(14rem,0.3fr)_minmax(0,1fr)] lg:gap-14">
            <div>
              <p className="font-mono text-[0.62rem] uppercase tracking-[0.2em] text-emerald-200/75">
                {t("sharedGuide.examples.eyebrow")}
              </p>
              <h3 className="mt-3 text-[0.94rem] font-semibold text-[var(--tessera-text)]">
                {t("sharedGuide.examples.title")}
              </h3>
              <p className="mt-3 text-[0.78rem] leading-6 text-[var(--tessera-text-muted)]">
                {t("sharedGuide.examples.lead")}
              </p>
            </div>
            <div className="divide-y divide-[var(--tessera-border)]">
              {examples.map((example) => (
                <div
                  key={example.title}
                  className="grid gap-2 py-4 first:pt-0 last:pb-0 md:grid-cols-[minmax(11rem,0.32fr)_minmax(0,1fr)] md:gap-7"
                >
                  <h4 className="text-[0.8rem] font-medium text-[var(--tessera-text)]">
                    {example.title}
                  </h4>
                  <p className="text-[0.76rem] leading-6 text-[var(--tessera-text-muted)]">
                    {example.body}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <details className="group/contract border-[var(--tessera-border)] border-t">
            <summary className="flex cursor-pointer list-none items-center gap-3 py-5 marker:content-none focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-300/60">
              <Code2
                className="h-4 w-4 text-violet-200"
                strokeWidth={ICON_STROKE_WIDTH}
                aria-hidden
              />
              <span className="flex-1 text-[0.78rem] font-medium text-violet-100">
                {t("sharedGuide.contract.title")}
              </span>
              <ChevronDown
                className="h-4 w-4 text-[var(--tessera-text-muted)] transition-transform group-open/contract:rotate-180"
                strokeWidth={ICON_STROKE_WIDTH}
                aria-hidden
              />
            </summary>
            <div className="grid gap-x-10 gap-y-7 border-violet-200/20 border-l pb-7 pl-5 md:grid-cols-2 xl:grid-cols-3">
              {TECHNICAL_ITEMS.map((key) => {
                const body =
                  key === "reading"
                    ? t(`guides.${guideKey}.data`)
                    : key === "scope"
                      ? t("sharedGuide.dataFoundations.scope.body")
                      : key === "time"
                        ? t("sharedGuide.dataFoundations.freshness.body")
                        : key === "operation"
                          ? t(`sharedGuide.contract.operation.${section}`)
                          : key === "limits"
                            ? t(`guides.${guideKey}.limit`)
                            : t("sharedGuide.contract.validation.body");
                return (
                  <div key={key}>
                    <h4 className="font-mono text-[0.6rem] uppercase tracking-[0.16em] text-violet-200/80">
                      {t(`sharedGuide.contract.items.${key}`)}
                    </h4>
                    <p className="mt-2 text-[0.74rem] leading-6 text-[var(--tessera-text-muted)]">
                      {body}
                    </p>
                  </div>
                );
              })}
            </div>
          </details>
        </details>
      </section>

      <footer className="grid gap-6 border-[var(--tessera-border)] border-t pt-9 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
        <div className="max-w-[58rem]">
          <p className="flex items-center gap-2 font-mono text-[0.62rem] uppercase tracking-[0.2em] text-cyan-200/70">
            <ListChecks className="h-4 w-4" aria-hidden />
            {t("sharedGuide.closing.eyebrow")}
          </p>
          <p className="mt-3 text-[0.92rem] leading-7 text-[var(--tessera-text)]">
            {t(`sharedGuide.closing.body.${section}`, {
              page: t(`guides.${guideKey}.title`),
            })}
          </p>
          <p className="mt-2 flex items-start gap-2 text-[0.76rem] leading-6 text-[var(--tessera-text-muted)]">
            <FileCheck2 className="mt-1 h-3.5 w-3.5 shrink-0 text-emerald-200" aria-hidden />
            {t(`guides.${guideKey}.action`)}
          </p>
        </div>
        <Link
          href="/comprendre"
          className="inline-flex items-center gap-2 text-[0.78rem] font-medium text-cyan-200 transition-colors hover:text-white"
        >
          {t("sharedGuide.closing.global")}
          <ArrowUpRight className="h-4 w-4" aria-hidden />
        </Link>
      </footer>
    </article>
  );
}
