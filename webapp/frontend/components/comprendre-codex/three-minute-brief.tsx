import {
  ArrowDown,
  ArrowRight,
  Bot,
  Check,
  ClipboardCheck,
  Clock3,
  FileCheck2,
  FileText,
  Fingerprint,
  Gauge,
  Hand,
  LockKeyhole,
  Radar,
  Scale,
  ShieldCheck,
  Sparkles,
  UserRoundCheck,
  UsersRound,
} from "lucide-react";
import type { ReactNode } from "react";

import { Link } from "@/i18n/navigation";
import { TimelineNav } from "./timeline-nav";

export interface ThreeMinuteCopy {
  eyebrow: string;
  heroTitle: string;
  heroLead: string;
  heroSummary: string;
  readTime: string;
  outcomeLabel: string;
  outcome: string;
  questions: string[];
  timeline: {
    label: string;
    items: Array<{ target: string; time: string; label: string }>;
  };
  problem: {
    time: string;
    eyebrow: string;
    title: string;
    body: string;
    beforeLabel: string;
    afterLabel: string;
    contrastBefore: string;
    contrastAfter: string;
  };
  journey: {
    time: string;
    eyebrow: string;
    title: string;
    body: string;
    customer: string;
    agent: string;
    checkpoint: string;
    requestLabel: string;
    agentLabel: string;
    checkpointLabel: string;
    evidenceLabel: string;
    checks: string[];
    allowed: string;
    review: string;
    evidence: string;
    receipt: {
      eyebrow: string;
      title: string;
      status: string;
      rows: Array<{ label: string; value: string }>;
    };
  };
  phases: {
    time: string;
    eyebrow: string;
    title: string;
    body: string;
    items: Array<{ marker: string; title: string; body: string }>;
  };
  roles: {
    time: string;
    eyebrow: string;
    title: string;
    body: string;
    items: Array<{ title: string; question: string; answer: string }>;
    sharedTruth: string;
  };
  honesty: {
    time: string;
    eyebrow: string;
    title: string;
    body: string;
    statuses: Array<{ label: string; condition: string }>;
    boundaryTitle: string;
    boundary: string;
  };
  close: {
    time: string;
    eyebrow: string;
    title: string;
    body: string;
    verbs: string[];
    businessCta: string;
    cockpitCta: string;
    footnote: string;
  };
}

const phaseIcons = [ClipboardCheck, LockKeyhole, UserRoundCheck, FileCheck2] as const;
const roleIcons = [Gauge, UsersRound, Scale] as const;

export function ThreeMinuteBrief({ copy }: { copy: ThreeMinuteCopy }) {
  return (
    <article className="relative isolate pb-36 sm:pb-28" aria-labelledby="three-minute-title">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 -top-5 -z-10 h-[34rem] overflow-hidden"
      >
        <div className="absolute top-[-17rem] left-[8%] h-[31rem] w-[31rem] rounded-full bg-[radial-gradient(circle,rgba(0,200,120,0.12),transparent_66%)] blur-2xl" />
        <div className="absolute top-[-20rem] right-[2%] h-[34rem] w-[34rem] rounded-full bg-[radial-gradient(circle,rgba(59,130,246,0.1),transparent_68%)] blur-3xl" />
      </div>

      <section className="mx-auto grid max-w-[1320px] gap-8 border-b border-[var(--tessera-border)] pt-3 pb-12 lg:grid-cols-[minmax(0,1.45fr)_minmax(19rem,0.55fr)] lg:items-end lg:gap-14">
        <div>
          <div className="mb-7 flex flex-wrap items-center gap-3">
            <span className="inline-flex items-center gap-2 rounded-full border border-[rgba(0,200,120,0.28)] bg-[rgba(0,200,120,0.07)] px-3 py-1.5 font-mono text-[0.67rem] font-semibold tracking-[0.14em] text-[var(--tessera-green)] uppercase">
              <Sparkles className="size-3.5" aria-hidden="true" />
              {copy.eyebrow}
            </span>
            <span className="inline-flex items-center gap-2 text-xs text-[var(--tessera-text-muted)]">
              <Clock3 className="size-3.5" aria-hidden="true" />
              {copy.readTime}
            </span>
          </div>

          <h2
            id="three-minute-title"
            className="max-w-5xl text-balance font-serif text-[clamp(2.7rem,5.3vw,5.8rem)] leading-[0.98] font-medium tracking-[-0.045em] text-[var(--tessera-text)]"
          >
            {copy.heroTitle}
          </h2>
          <p className="mt-7 max-w-3xl text-pretty text-[clamp(1.05rem,1.45vw,1.3rem)] leading-relaxed text-[var(--tessera-text-muted)]">
            {copy.heroLead}
          </p>
          <p className="mt-5 flex items-center gap-2 text-sm font-medium text-[var(--tessera-text)]">
            <span className="h-px w-7 bg-[var(--tessera-green)]" aria-hidden="true" />
            {copy.heroSummary}
          </p>
        </div>

        <aside className="relative overflow-hidden rounded-2xl border border-[var(--tessera-border-strong)] bg-[linear-gradient(145deg,var(--tessera-surface-elevated),var(--tessera-surface))] p-6 shadow-[var(--shadow-card-elevated)]">
          <div
            aria-hidden="true"
            className="absolute -top-10 -right-10 h-36 w-36 rounded-full border border-[rgba(0,200,120,0.16)]"
          />
          <p className="font-mono text-[0.66rem] font-semibold tracking-[0.15em] text-[var(--tessera-green)] uppercase">
            {copy.outcomeLabel}
          </p>
          <p className="mt-4 max-w-xs font-serif text-2xl leading-snug font-medium text-[var(--tessera-text)]">
            {copy.outcome}
          </p>
          <div className="mt-7 space-y-3">
            {copy.questions.map((question, index) => (
              <div
                key={question}
                className="flex items-center gap-3 border-t border-[var(--tessera-border)] pt-3 text-sm text-[var(--tessera-text-muted)]"
              >
                <span className="font-mono text-[0.64rem] text-[var(--tessera-green)]">
                  0{index + 1}
                </span>
                <span>{question}</span>
              </div>
            ))}
          </div>
          <a
            href="#story"
            className="mt-6 inline-flex items-center gap-2 text-xs font-semibold text-[var(--tessera-text)] transition-colors hover:text-[var(--tessera-green)]"
          >
            {copy.problem.eyebrow}
            <ArrowDown className="size-3.5" aria-hidden="true" />
          </a>
        </aside>
      </section>

      <TimelineNav label={copy.timeline.label} items={copy.timeline.items} />

      <div id="story" className="mx-auto max-w-[1320px] scroll-mt-6">
        <StorySection
          id="problem"
          time={copy.problem.time}
          eyebrow={copy.problem.eyebrow}
          title={copy.problem.title}
          body={copy.problem.body}
        >
          <div className="grid gap-px overflow-hidden rounded-2xl border border-[var(--tessera-border)] bg-[var(--tessera-border)] md:grid-cols-2">
            <div className="bg-[var(--tessera-surface)] p-6 sm:p-8">
              <p className="mb-5 font-mono text-[0.65rem] tracking-[0.14em] text-[var(--tessera-text-subtle)] uppercase">
                {copy.problem.beforeLabel}
              </p>
              <p className="max-w-lg text-lg leading-relaxed text-[var(--tessera-text-muted)]">
                {copy.problem.contrastBefore}
              </p>
            </div>
            <div className="relative overflow-hidden bg-[var(--tessera-surface)] p-6 sm:p-8">
              <div
                aria-hidden="true"
                className="absolute inset-y-0 left-0 w-px bg-[linear-gradient(transparent,var(--tessera-green),transparent)]"
              />
              <p className="mb-5 flex items-center gap-2 font-mono text-[0.65rem] tracking-[0.14em] text-[var(--tessera-green)] uppercase">
                <ShieldCheck className="size-4" aria-hidden="true" />
                {copy.problem.afterLabel}
              </p>
              <p className="max-w-lg text-lg leading-relaxed text-[var(--tessera-text)]">
                {copy.problem.contrastAfter}
              </p>
            </div>
          </div>
        </StorySection>

        <StorySection
          id="journey"
          time={copy.journey.time}
          eyebrow={copy.journey.eyebrow}
          title={copy.journey.title}
          body={copy.journey.body}
        >
          <div className="overflow-hidden rounded-2xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] shadow-[var(--shadow-card)]">
            <div className="grid gap-0 lg:grid-cols-[0.9fr_auto_0.9fr_auto_1.25fr] lg:items-stretch">
              <JourneyNode
                icon={UsersRound}
                label={`01 · ${copy.journey.requestLabel}`}
                text={copy.journey.customer}
              />
              <JourneyArrow />
              <JourneyNode
                icon={Bot}
                label={`02 · ${copy.journey.agentLabel}`}
                text={copy.journey.agent}
              />
              <JourneyArrow />
              <div className="relative border-t border-[var(--tessera-border)] bg-[linear-gradient(145deg,rgba(0,200,120,0.08),transparent_62%)] p-6 lg:border-t-0 lg:border-l">
                <div className="flex items-center gap-3">
                  <span className="grid size-10 place-items-center rounded-xl border border-[rgba(0,200,120,0.25)] bg-[rgba(0,200,120,0.09)] text-[var(--tessera-green)]">
                    <Fingerprint className="size-5" aria-hidden="true" />
                  </span>
                  <div>
                    <p className="font-mono text-[0.62rem] tracking-[0.13em] text-[var(--tessera-green)]">
                      03 · {copy.journey.checkpointLabel}
                    </p>
                    <h4 className="mt-1 text-lg font-semibold text-[var(--tessera-text)]">
                      {copy.journey.checkpoint}
                    </h4>
                  </div>
                </div>
                <ul className="mt-5 grid gap-2 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
                  {copy.journey.checks.map((check) => (
                    <li
                      key={check}
                      className="flex items-start gap-2 text-xs leading-relaxed text-[var(--tessera-text-muted)]"
                    >
                      <Check className="mt-0.5 size-3.5 shrink-0 text-[var(--tessera-green)]" />
                      {check}
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="grid border-t border-[var(--tessera-border)] md:grid-cols-2">
              <div className="flex items-center gap-3 border-b border-[var(--tessera-border)] p-5 md:border-r md:border-b-0">
                <span className="grid size-9 shrink-0 place-items-center rounded-full bg-[var(--tessera-green-muted)] text-[var(--tessera-green)]">
                  <Check className="size-4" aria-hidden="true" />
                </span>
                <p className="text-sm font-medium text-[var(--tessera-text)]">
                  {copy.journey.allowed}
                </p>
              </div>
              <div className="flex items-center gap-3 p-5">
                <span className="grid size-9 shrink-0 place-items-center rounded-full bg-[rgba(229,147,8,0.12)] text-[var(--color-warning-500)]">
                  <Hand className="size-4" aria-hidden="true" />
                </span>
                <p className="text-sm font-medium text-[var(--tessera-text)]">
                  {copy.journey.review}
                </p>
              </div>
            </div>

            <div className="flex flex-col gap-3 border-t border-[var(--tessera-border)] bg-[var(--tessera-bg-soft)] px-5 py-4 sm:flex-row sm:items-center">
              <span className="inline-flex shrink-0 items-center gap-2 font-mono text-[0.62rem] tracking-[0.13em] text-[#8bb7ff] uppercase">
                <FileCheck2 className="size-4" aria-hidden="true" />
                {copy.journey.evidenceLabel}
              </span>
              <span className="hidden h-4 w-px bg-[var(--tessera-border-strong)] sm:block" />
              <p className="text-xs leading-relaxed text-[var(--tessera-text-muted)]">
                {copy.journey.evidence}
              </p>
            </div>

            <div className="grid gap-6 border-t border-[var(--tessera-border)] bg-[linear-gradient(135deg,rgba(139,183,255,0.07),transparent_58%)] p-5 sm:p-7 lg:grid-cols-[0.82fr_1.18fr] lg:items-start">
              <div>
                <p className="font-mono text-[0.62rem] font-semibold tracking-[0.14em] text-[#8bb7ff] uppercase">
                  {copy.journey.receipt.eyebrow}
                </p>
                <div className="mt-4 flex items-start gap-3">
                  <span className="grid size-10 shrink-0 place-items-center rounded-xl border border-[rgba(139,183,255,0.24)] bg-[rgba(139,183,255,0.08)] text-[#8bb7ff]">
                    <FileText className="size-5" aria-hidden="true" />
                  </span>
                  <div>
                    <h4 className="font-serif text-xl leading-snug font-medium text-[var(--tessera-text)]">
                      {copy.journey.receipt.title}
                    </h4>
                    <span className="mt-4 inline-flex items-center gap-2 rounded-full border border-[rgba(229,147,8,0.28)] bg-[rgba(229,147,8,0.1)] px-3 py-1.5 text-xs font-semibold text-[var(--color-warning-500)]">
                      <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
                      {copy.journey.receipt.status}
                    </span>
                  </div>
                </div>
              </div>

              <dl className="grid overflow-hidden rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-bg-soft)] sm:grid-cols-2">
                {copy.journey.receipt.rows.map((row) => (
                  <div
                    key={row.label}
                    className="border-b border-[var(--tessera-border)] p-4 last:border-b-0 sm:odd:border-r sm:[&:nth-last-child(-n+2)]:border-b-0"
                  >
                    <dt className="font-mono text-[0.59rem] tracking-[0.12em] text-[var(--tessera-text-subtle)] uppercase">
                      {row.label}
                    </dt>
                    <dd className="mt-2 text-sm leading-relaxed font-medium text-[var(--tessera-text)]">
                      {row.value}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </StorySection>

        <StorySection
          id="phases"
          time={copy.phases.time}
          eyebrow={copy.phases.eyebrow}
          title={copy.phases.title}
          body={copy.phases.body}
        >
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {copy.phases.items.map((item, index) => {
              const Icon = phaseIcons[index] ?? ShieldCheck;
              return (
                <div
                  key={item.title}
                  className="group rounded-2xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-5 transition-[border-color,transform] duration-200 hover:-translate-y-0.5 hover:border-[var(--tessera-border-strong)]"
                >
                  <div className="flex items-center justify-between">
                    <span className="grid size-10 place-items-center rounded-xl bg-[var(--tessera-muted)] text-[var(--tessera-green)]">
                      <Icon className="size-5" aria-hidden="true" />
                    </span>
                    <span className="font-mono text-[0.62rem] tracking-[0.13em] text-[var(--tessera-text-subtle)] uppercase">
                      {item.marker}
                    </span>
                  </div>
                  <h4 className="mt-6 font-serif text-xl font-medium text-[var(--tessera-text)]">
                    {item.title}
                  </h4>
                  <p className="mt-3 text-sm leading-relaxed text-[var(--tessera-text-muted)]">
                    {item.body}
                  </p>
                </div>
              );
            })}
          </div>
        </StorySection>

        <StorySection
          id="roles"
          time={copy.roles.time}
          eyebrow={copy.roles.eyebrow}
          title={copy.roles.title}
          body={copy.roles.body}
        >
          <div className="grid gap-4 lg:grid-cols-3">
            {copy.roles.items.map((item, index) => {
              const Icon = roleIcons[index] ?? Radar;
              return (
                <div
                  key={item.title}
                  className="rounded-2xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-6"
                >
                  <div className="flex items-center gap-3">
                    <span className="grid size-9 place-items-center rounded-full border border-[var(--tessera-border-strong)] text-[var(--tessera-text-muted)]">
                      <Icon className="size-4" aria-hidden="true" />
                    </span>
                    <h4 className="text-base font-semibold text-[var(--tessera-text)]">
                      {item.title}
                    </h4>
                  </div>
                  <p className="mt-6 font-serif text-xl leading-snug text-[var(--tessera-text)]">
                    “{item.question}”
                  </p>
                  <p className="mt-4 border-l border-[var(--tessera-green)] pl-4 text-sm leading-relaxed text-[var(--tessera-text-muted)]">
                    {item.answer}
                  </p>
                </div>
              );
            })}
          </div>
          <div className="mt-4 flex items-start gap-3 rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-bg-soft)] px-5 py-4">
            <Radar
              className="mt-0.5 size-4 shrink-0 text-[var(--tessera-green)]"
              aria-hidden="true"
            />
            <p className="text-sm leading-relaxed text-[var(--tessera-text-muted)]">
              {copy.roles.sharedTruth}
            </p>
          </div>
        </StorySection>

        <StorySection
          id="honesty"
          time={copy.honesty.time}
          eyebrow={copy.honesty.eyebrow}
          title={copy.honesty.title}
          body={copy.honesty.body}
        >
          <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-2xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-6 sm:p-8">
              <div className="grid gap-3">
                {copy.honesty.statuses.map((status, index) => (
                  <div
                    key={status.label}
                    className="grid gap-2 rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-bg-soft)] p-4 sm:grid-cols-[10rem_1fr] sm:items-center"
                  >
                    <span className="flex items-center gap-2 text-sm font-semibold text-[var(--tessera-text)]">
                      <span
                        aria-hidden="true"
                        className={`size-2 rounded-full ${
                          index === 0
                            ? "bg-[var(--tessera-green)]"
                            : index === 1
                              ? "bg-[#8bb7ff]"
                              : "bg-[var(--color-warning-500)]"
                        }`}
                      />
                      {status.label}
                    </span>
                    <span className="text-xs leading-relaxed text-[var(--tessera-text-muted)]">
                      {status.condition}
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <aside className="relative overflow-hidden rounded-2xl border border-[rgba(215,190,138,0.28)] bg-[linear-gradient(145deg,rgba(215,190,138,0.1),transparent_65%)] p-6 sm:p-8">
              <Fingerprint className="size-7 text-gold-500" aria-hidden="true" />
              <h4 className="mt-6 font-serif text-2xl font-medium text-[var(--tessera-text)]">
                {copy.honesty.boundaryTitle}
              </h4>
              <p className="mt-4 text-sm leading-relaxed text-[var(--tessera-text-muted)]">
                {copy.honesty.boundary}
              </p>
            </aside>
          </div>
        </StorySection>

        <section
          id="close"
          className="mt-16 scroll-mt-32 overflow-hidden rounded-[1.4rem] border border-[var(--tessera-border-strong)] bg-[linear-gradient(135deg,var(--tessera-surface-elevated),var(--tessera-surface))] shadow-[var(--shadow-card-elevated)]"
        >
          <div className="grid gap-8 p-7 sm:p-10 lg:grid-cols-[1fr_auto] lg:items-end">
            <div>
              <div className="flex items-center gap-3">
                <span className="font-mono text-[0.68rem] font-semibold tracking-[0.16em] text-[var(--tessera-green)] uppercase">
                  {copy.close.time}
                </span>
                <span className="h-px w-8 bg-[var(--tessera-border-strong)]" />
                <span className="font-mono text-[0.64rem] tracking-[0.13em] text-[var(--tessera-text-muted)] uppercase">
                  {copy.close.eyebrow}
                </span>
              </div>
              <h3 className="mt-5 max-w-4xl text-balance font-serif text-[clamp(2rem,4vw,4rem)] leading-tight font-medium tracking-[-0.035em] text-[var(--tessera-text)]">
                {copy.close.title}
              </h3>
              <p className="mt-5 max-w-3xl text-base leading-relaxed text-[var(--tessera-text-muted)]">
                {copy.close.body}
              </p>
              <div className="mt-7 flex flex-wrap gap-2">
                {copy.close.verbs.map((verb) => (
                  <span
                    key={verb}
                    className="rounded-full border border-[var(--tessera-border-strong)] bg-[var(--tessera-bg-soft)] px-4 py-2 font-serif text-base text-[var(--tessera-text)]"
                  >
                    {verb}
                  </span>
                ))}
              </div>
            </div>
            <div className="flex min-w-[15rem] flex-col gap-3">
              <Link
                href="/recouvrement"
                className="inline-flex min-h-11 items-center justify-between gap-3 rounded-xl bg-[var(--tessera-green)] px-5 py-3 text-sm font-semibold text-[#031810] transition-[filter,transform] hover:-translate-y-0.5 hover:brightness-110"
              >
                {copy.close.businessCta}
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
              <Link
                href="/select-space"
                className="inline-flex min-h-11 items-center justify-between gap-3 rounded-xl border border-[var(--tessera-border-strong)] bg-[var(--tessera-bg-soft)] px-5 py-3 text-sm font-semibold text-[var(--tessera-text)] transition-colors hover:border-[var(--tessera-green)]"
              >
                {copy.close.cockpitCta}
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </div>
          </div>
          <div className="border-t border-[var(--tessera-border)] px-7 py-4 sm:px-10">
            <p className="text-[0.68rem] leading-relaxed text-[var(--tessera-text-subtle)]">
              {copy.close.footnote}
            </p>
          </div>
        </section>
      </div>
    </article>
  );
}

function StorySection({
  id,
  time,
  eyebrow,
  title,
  body,
  children,
}: {
  id: string;
  time: string;
  eyebrow: string;
  title: string;
  body: string;
  children: ReactNode;
}) {
  return (
    <section
      id={id}
      className="grid scroll-mt-32 gap-7 border-b border-[var(--tessera-border)] py-14 lg:grid-cols-[13rem_minmax(0,1fr)] lg:gap-10 lg:py-20"
    >
      <header>
        <div className="sticky top-0">
          <p className="font-mono text-[0.7rem] font-semibold tracking-[0.14em] text-[var(--tessera-green)]">
            {time}
          </p>
          <p className="mt-2 font-mono text-[0.63rem] tracking-[0.13em] text-[var(--tessera-text-subtle)] uppercase">
            {eyebrow}
          </p>
        </div>
      </header>
      <div>
        <h3 className="max-w-4xl text-balance font-serif text-[clamp(1.9rem,3.2vw,3.3rem)] leading-tight font-medium tracking-[-0.03em] text-[var(--tessera-text)]">
          {title}
        </h3>
        <p className="mt-4 mb-8 max-w-3xl text-pretty text-base leading-relaxed text-[var(--tessera-text-muted)]">
          {body}
        </p>
        {children}
      </div>
    </section>
  );
}

function JourneyNode({
  icon: Icon,
  label,
  text,
}: {
  icon: typeof Bot;
  label: string;
  text: string;
}) {
  return (
    <div className="p-6">
      <span className="grid size-10 place-items-center rounded-xl bg-[var(--tessera-muted)] text-[var(--tessera-text-muted)]">
        <Icon className="size-5" aria-hidden="true" />
      </span>
      <p className="mt-6 font-mono text-[0.62rem] tracking-[0.13em] text-[var(--tessera-text-subtle)]">
        {label}
      </p>
      <p className="mt-2 max-w-[15rem] text-sm leading-relaxed font-medium text-[var(--tessera-text)]">
        {text}
      </p>
    </div>
  );
}

function JourneyArrow() {
  return (
    <div className="hidden w-9 items-center justify-center border-x border-[var(--tessera-border)] bg-[var(--tessera-bg-soft)] lg:flex">
      <ArrowRight className="size-4 text-[var(--tessera-text-subtle)]" aria-hidden="true" />
    </div>
  );
}
