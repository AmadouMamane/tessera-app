"use client";

import {
  ArrowRight,
  Bot,
  Check,
  ClipboardCheck,
  FileCheck2,
  FileText,
  Gauge,
  Hand,
  Radar,
  Scale,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { ComprendreV2Diagram } from "@/components/comprendre/comprendre-v2-diagram";
import { Link } from "@/i18n/navigation";
import type { ComprendreResponse } from "@/lib/api/schemas";
import { fetchComprendreFacts } from "@/lib/comprendre-client";

interface JourneyCopy {
  title: string;
  body: string;
  steps: Array<{ label: string; body?: string }>;
  checks: string[];
  allowed: string;
  review: string;
  evidence: string;
  illustrative: {
    label: string;
    rows: Array<{ label: string; value: string }>;
    status: string;
  };
  after: string;
  mechanismLead: string;
}

interface LiveCardCopy {
  title: string;
  body: string;
}

interface DetailCopy {
  title: string;
  moment: string;
  body: string;
  chips: string[];
  cta: string;
}

interface RoleCopy {
  title: string;
  question: string;
  answer: string;
}

interface RuleCopy {
  title: string;
  body: string;
  chip?: string;
}

type T = ReturnType<typeof useTranslations>;

const liveIcons = [Gauge, ShieldCheck, ClipboardCheck, FileCheck2] as const;
const detailIcons = [Gauge, ShieldCheck, ClipboardCheck, FileCheck2] as const;
const roleIcons = [Gauge, UsersRound, Scale] as const;
const proofRoutes = ["/agents", "/surveiller", "/eval", "/prouver"] as const;
const detailRoutes = ["/agents", "/surveiller", "/eval", "/prouver"] as const;

function elapsed(t: T, generatedAt: string, observedAt: string): string {
  const generated = Date.parse(generatedAt);
  const observed = Date.parse(observedAt);
  const totalSeconds = Math.max(0, Math.floor((generated - observed) / 1000));
  if (totalSeconds < 60) return t("time.seconds", { count: totalSeconds });
  const totalMinutes = Math.floor(totalSeconds / 60);
  if (totalMinutes < 60) return t("time.minutes", { count: totalMinutes });
  return t("time.hours", { count: Math.floor(totalMinutes / 60) });
}

function liveFacts(t: T, response: ComprendreResponse): string[] {
  if (!response.available) {
    return [
      t("live.fleet.empty"),
      t("live.guard.empty"),
      t("live.evaluations.empty"),
      t("live.audit.empty"),
    ];
  }

  const fleet = response.fleet;
  const fleetFact =
    fleet.observed_agents === null || fleet.last_signal_at === null
      ? t("live.fleet.empty")
      : t("live.fleet.fact", {
          count: fleet.observed_agents,
          freshness: elapsed(t, response.generated_at, fleet.last_signal_at),
          silent: fleet.is_silent ? "true" : "false",
        });
  const guard = response.guard;
  const guardFact =
    guard.controlled_today === null || guard.blocked_today === null
      ? t("live.guard.empty")
      : t("live.guard.fact", {
          controlled: guard.controlled_today,
          blocked: guard.blocked_today,
        });
  const evaluations = response.evaluations;
  const evaluationFact =
    evaluations.ready_agents === null || evaluations.review_agents === null
      ? t("live.evaluations.empty")
      : t("live.evaluations.fact", {
          ready: evaluations.ready_agents,
          review: evaluations.review_agents,
        });
  const auditFact = response.audit.last_verified_at
    ? t("live.audit.fact", {
        freshness: elapsed(t, response.generated_at, response.audit.last_verified_at),
      })
    : t("live.audit.empty");
  return [fleetFact, guardFact, evaluationFact, auditFact];
}

/** Approved `/comprendre` v2 content, paired with the six backend facts at read time. */
export function ComprendreV2Overview({ initialFacts }: { initialFacts: ComprendreResponse }) {
  const t = useTranslations("comprendreV2");
  const [facts, setFacts] = useState(initialFacts);
  const journey = t.raw("journey") as JourneyCopy;
  const cards = t.raw("live.cards") as LiveCardCopy[];
  const details = t.raw("details.items") as DetailCopy[];
  const roles = t.raw("roles.items") as RoleCopy[];
  const rules = t.raw("difference.items") as RuleCopy[];
  const questions = t.raw("hero.questions") as string[];
  const displayedFacts = liveFacts(t, facts);

  useEffect(() => {
    void fetchComprendreFacts().then((next) => {
      if (next) setFacts(next);
    });
  }, []);

  return (
    <article className="relative isolate mx-auto max-w-[82rem] pb-16">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 -top-12 -z-10 h-[38rem] overflow-hidden"
      >
        <div className="absolute -top-52 left-[12%] h-[34rem] w-[34rem] rounded-full bg-[radial-gradient(circle,rgba(0,200,120,0.12),transparent_68%)] blur-3xl" />
        <div className="absolute -top-56 right-[5%] h-[38rem] w-[38rem] rounded-full bg-[radial-gradient(circle,rgba(59,130,246,0.1),transparent_70%)] blur-3xl" />
      </div>

      <header className="grid gap-8 border-[var(--tessera-border)] border-b pt-5 pb-12 lg:grid-cols-[minmax(0,1.3fr)_minmax(18rem,0.7fr)] lg:items-end lg:gap-14">
        <div>
          <h1 className="max-w-5xl text-balance font-serif text-[clamp(2.7rem,5vw,5.5rem)] leading-[0.98] font-medium tracking-[-0.045em] text-[var(--tessera-text)]">
            {t("hero.title")}
          </h1>
          <p className="mt-7 max-w-3xl text-pretty text-[clamp(1.05rem,1.4vw,1.3rem)] leading-relaxed text-[var(--tessera-text-muted)]">
            {t("hero.lead")}
          </p>
          <p className="mt-5 max-w-4xl text-sm leading-relaxed text-[var(--tessera-text-muted)]">
            {t("hero.body")}
          </p>
          <p className="mt-5 flex max-w-4xl items-start gap-3 text-sm leading-relaxed font-medium text-[var(--tessera-text)]">
            <span className="mt-2 h-px w-8 shrink-0 bg-[var(--tessera-green)]" aria-hidden />
            {t("hero.summary")}
          </p>
        </div>
        <aside className="rounded-2xl border border-[var(--tessera-border-strong)] bg-[var(--tessera-surface)] p-6 shadow-[var(--shadow-card)]">
          <p className="font-mono text-[0.64rem] tracking-[0.14em] text-[var(--tessera-text-subtle)] uppercase">
            {t("hero.questionsLabel")}
          </p>
          <ul className="mt-4 space-y-3">
            {questions.map((question) => (
              <li
                key={question}
                className="flex items-start gap-3 border-[var(--tessera-border)] border-t pt-3 text-sm text-[var(--tessera-text)] first:border-t-0 first:pt-0"
              >
                <Check className="mt-0.5 size-4 shrink-0 text-[var(--tessera-green)]" aria-hidden />
                {question}
              </li>
            ))}
          </ul>
        </aside>
      </header>

      <section className="py-12">
        <ComprendreV2Diagram />
      </section>

      <section className="border-[var(--tessera-border)] border-t py-14">
        <SectionHeader title={journey.title} body={journey.body} />
        <div className="mt-8 overflow-hidden rounded-3xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] shadow-[var(--shadow-card)]">
          <div className="grid lg:grid-cols-4">
            {journey.steps.map((step, index) => {
              const Icon =
                index === 0
                  ? UsersRound
                  : index === 1
                    ? Bot
                    : index === 2
                      ? ShieldCheck
                      : FileCheck2;
              return (
                <div
                  key={step.label}
                  className="border-[var(--tessera-border)] border-b p-5 last:border-b-0 lg:border-r lg:border-b-0 lg:last:border-r-0"
                >
                  <Icon className="size-5 text-[var(--tessera-green)]" aria-hidden />
                  <p className="mt-5 font-mono text-[0.62rem] tracking-[0.12em] text-[var(--tessera-text-subtle)] uppercase">
                    {step.label}
                  </p>
                  {step.body ? (
                    <p className="mt-2 text-sm leading-relaxed font-medium text-[var(--tessera-text)]">
                      {step.body}
                    </p>
                  ) : null}
                  {index === 2 ? (
                    <ul className="mt-4 space-y-2">
                      {journey.checks.map((check) => (
                        <li
                          key={check}
                          className="flex items-start gap-2 text-xs leading-relaxed text-[var(--tessera-text-muted)]"
                        >
                          <Check className="mt-0.5 size-3.5 shrink-0 text-[var(--tessera-green)]" />
                          {check}
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              );
            })}
          </div>

          <div className="grid border-[var(--tessera-border)] border-t md:grid-cols-2">
            <p className="flex items-center gap-3 border-[var(--tessera-border)] border-b p-5 text-sm font-medium text-[var(--tessera-text)] md:border-r md:border-b-0">
              <span className="grid size-9 shrink-0 place-items-center rounded-full bg-[var(--tessera-green-muted)] text-[var(--tessera-green)]">
                <Check className="size-4" aria-hidden />
              </span>
              {journey.allowed}
            </p>
            <p className="flex items-center gap-3 p-5 text-sm font-medium text-[var(--tessera-text)]">
              <span className="grid size-9 shrink-0 place-items-center rounded-full bg-[rgba(229,147,8,0.12)] text-[var(--color-warning-500)]">
                <Hand className="size-4" aria-hidden />
              </span>
              {journey.review}
            </p>
          </div>

          <p className="border-[var(--tessera-border)] border-t bg-[var(--tessera-bg-soft)] px-5 py-4 text-sm leading-relaxed text-[var(--tessera-text-muted)]">
            {journey.evidence}
          </p>

          <div className="grid gap-6 border-[var(--tessera-border)] border-t bg-[linear-gradient(135deg,rgba(139,183,255,0.07),transparent_58%)] p-5 sm:p-7 lg:grid-cols-[0.8fr_1.2fr]">
            <div>
              <p className="font-mono text-[0.62rem] font-semibold tracking-[0.14em] text-[#8bb7ff] uppercase">
                {journey.illustrative.label}
              </p>
              <span className="mt-5 inline-flex items-center gap-2 rounded-full border border-[rgba(229,147,8,0.28)] bg-[rgba(229,147,8,0.1)] px-3 py-1.5 text-xs font-semibold text-[var(--color-warning-500)]">
                <FileText className="size-4" aria-hidden />
                {journey.illustrative.status}
              </span>
            </div>
            <dl className="grid overflow-hidden rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-bg-soft)] sm:grid-cols-2">
              {journey.illustrative.rows.map((row) => (
                <div
                  key={row.label}
                  className="border-[var(--tessera-border)] border-b p-4 last:border-b-0 sm:odd:border-r sm:[&:nth-last-child(-n+2)]:border-b-0"
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
        <p className="mt-6 max-w-5xl text-sm leading-relaxed text-[var(--tessera-text-muted)]">
          {journey.after}
        </p>
        <p className="mt-4 max-w-5xl text-sm leading-relaxed text-[var(--tessera-text-muted)] italic">
          {journey.mechanismLead}
        </p>
        <ProofLink href="/recouvrement" label={t("proofLabel")} />
      </section>

      <section
        data-testid="comprendre-live-section"
        className="border-[var(--tessera-border)] border-t py-14"
      >
        <SectionHeader title={t("live.title")} />
        <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {cards.map((card, index) => {
            const Icon = liveIcons[index] ?? Gauge;
            const windowTitle =
              index === 0 && facts.available
                ? t("live.fleet.window", { hours: facts.fleet.window_hours })
                : undefined;
            return (
              <article
                key={card.title}
                data-testid={`comprendre-live-tile-${index}`}
                className="flex min-h-full flex-col rounded-2xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-5"
              >
                <span className="grid size-10 place-items-center rounded-xl bg-[var(--tessera-muted)] text-[var(--tessera-green)]">
                  <Icon className="size-5" aria-hidden />
                </span>
                <h3 className="mt-5 font-serif text-xl font-medium text-[var(--tessera-text)]">
                  {card.title}
                </h3>
                <p
                  title={windowTitle}
                  className="mt-4 min-h-12 text-sm leading-relaxed font-semibold text-[var(--tessera-text)]"
                >
                  {displayedFacts[index]}
                </p>
                <p className="mt-3 flex-1 text-sm leading-relaxed text-[var(--tessera-text-muted)]">
                  {card.body}
                </p>
                <ProofLink href={proofRoutes[index] ?? "/agents"} label={t("proofLabel")} />
              </article>
            );
          })}
        </div>
        <p className="mt-5 rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-bg-soft)] px-5 py-4 text-sm font-medium text-[var(--tessera-text)]">
          {t("live.foundation")}
        </p>
      </section>

      <section className="border-[var(--tessera-border)] border-t py-14">
        <div className="divide-y divide-[var(--tessera-border)] rounded-3xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
          {details.map((detail, index) => {
            const Icon = detailIcons[index] ?? Gauge;
            return (
              <article
                key={detail.title}
                className="grid gap-5 p-5 sm:p-7 lg:grid-cols-[auto_1fr_auto]"
              >
                <span className="grid size-11 place-items-center rounded-xl border border-[var(--tessera-border-strong)] bg-[var(--tessera-bg-soft)] text-[var(--tessera-green)]">
                  <Icon className="size-5" aria-hidden />
                </span>
                <div>
                  <div className="flex flex-wrap items-center gap-3">
                    <h3 className="font-serif text-xl font-medium text-[var(--tessera-text)]">
                      {detail.title}
                    </h3>
                    <span className="rounded-full border border-[var(--tessera-border-strong)] px-2.5 py-1 font-mono text-[0.6rem] tracking-[0.1em] text-[var(--tessera-text-subtle)] uppercase">
                      {detail.moment}
                    </span>
                  </div>
                  <p className="mt-3 max-w-5xl text-sm leading-relaxed text-[var(--tessera-text-muted)]">
                    {detail.body}
                  </p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {detail.chips.map((chip) => (
                      <span
                        key={chip}
                        className="rounded-full bg-[var(--tessera-muted)] px-3 py-1.5 text-xs text-[var(--tessera-text-muted)]"
                      >
                        {chip}
                      </span>
                    ))}
                  </div>
                </div>
                <Link
                  href={detailRoutes[index] ?? "/agents"}
                  className="inline-flex items-center gap-2 self-start text-sm font-semibold text-[var(--tessera-green)] hover:text-[var(--tessera-text)]"
                >
                  {detail.cta}
                  <ArrowRight className="size-4" aria-hidden />
                </Link>
              </article>
            );
          })}
        </div>
      </section>

      <section className="border-[var(--tessera-border)] border-t py-14">
        <SectionHeader title={t("roles.title")} body={t("roles.lead")} />
        <div className="mt-8 grid gap-4 lg:grid-cols-3">
          {roles.map((role, index) => {
            const Icon = roleIcons[index] ?? Radar;
            return (
              <article
                key={role.title}
                className="rounded-2xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-6"
              >
                <div className="flex items-center gap-3">
                  <span className="grid size-9 place-items-center rounded-full border border-[var(--tessera-border-strong)] text-[var(--tessera-text-muted)]">
                    <Icon className="size-4" aria-hidden />
                  </span>
                  <h3 className="font-semibold text-[var(--tessera-text)]">{role.title}</h3>
                </div>
                <q className="mt-6 block font-serif text-xl leading-snug text-[var(--tessera-text)]">
                  {role.question}
                </q>
                <p className="mt-4 border-[var(--tessera-green)] border-l pl-4 text-sm leading-relaxed text-[var(--tessera-text-muted)]">
                  {role.answer}
                </p>
              </article>
            );
          })}
        </div>
        <p className="mt-4 flex items-start gap-3 rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-bg-soft)] px-5 py-4 text-sm leading-relaxed text-[var(--tessera-text-muted)]">
          <Radar className="mt-0.5 size-4 shrink-0 text-[var(--tessera-green)]" aria-hidden />
          {t("roles.truth")}
        </p>
      </section>

      <section className="border-[var(--tessera-border)] border-t py-14">
        <SectionHeader title={t("difference.title")} />
        <div className="mt-8 grid gap-4 md:grid-cols-2">
          {rules.map((rule) => (
            <article
              key={rule.title}
              className="rounded-2xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-6"
            >
              <h3 className="font-serif text-xl font-medium text-[var(--tessera-text)]">
                {rule.title}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-[var(--tessera-text-muted)]">
                {rule.body}
              </p>
              {rule.chip ? (
                <span className="mt-4 inline-flex rounded-full bg-[var(--tessera-muted)] px-3 py-1.5 text-xs text-[var(--tessera-text-muted)]">
                  {rule.chip}
                </span>
              ) : null}
            </article>
          ))}
        </div>
      </section>

      <section className="border-[var(--tessera-border)] border-t py-14">
        <SectionHeader title={t("further.title")} body={t("further.decisionRegister")} />
        <p className="mt-6 max-w-5xl text-sm leading-relaxed text-[var(--tessera-text-muted)]">
          {t("further.storiesLead")} <strong>{t("further.storyFork")}</strong>
          {t("further.storiesJoin")} <strong>{t("further.storyForeign")}</strong>
          {t("further.storiesEnd")}
        </p>
        <p className="mt-4 max-w-5xl text-sm leading-relaxed text-[var(--tessera-text-muted)]">
          {t("further.detailLead")}
          <Link
            href="/comprendre/en-detail"
            className="font-semibold text-[var(--tessera-green)] hover:text-[var(--tessera-text)]"
          >
            {t("further.detailLink")}
          </Link>
          {t("further.detailEnd")}
        </p>
      </section>

      <section className="overflow-hidden rounded-3xl border border-[var(--tessera-border-strong)] bg-[linear-gradient(135deg,var(--tessera-surface-elevated),var(--tessera-surface))] shadow-[var(--shadow-card-elevated)]">
        <div className="grid gap-8 p-7 sm:p-10 lg:grid-cols-[1fr_auto] lg:items-end">
          <div>
            <h2 className="max-w-4xl text-balance font-serif text-[clamp(2rem,4vw,4rem)] leading-tight font-medium tracking-[-0.035em] text-[var(--tessera-text)]">
              {t("closing.title")}
            </h2>
            <p className="mt-5 max-w-4xl text-base leading-relaxed text-[var(--tessera-text-muted)]">
              {t("closing.body")}
            </p>
          </div>
          <div className="flex min-w-[16rem] flex-col gap-3">
            <Link
              href="/surveiller/vue-ensemble"
              className="inline-flex min-h-11 items-center justify-between gap-3 rounded-xl bg-[var(--tessera-green)] px-5 py-3 text-sm font-semibold text-[#031810] hover:brightness-110"
            >
              {t("closing.cockpitCta")}
            </Link>
            <Link
              href="/espaces"
              className="inline-flex min-h-11 items-center justify-between gap-3 rounded-xl border border-[var(--tessera-border-strong)] bg-[var(--tessera-bg-soft)] px-5 py-3 text-sm font-semibold text-[var(--tessera-text)] hover:border-[var(--tessera-green)]"
            >
              {t("closing.businessCta")}
            </Link>
          </div>
        </div>
      </section>

      <footer className="mt-8 border border-[var(--tessera-border)] bg-[var(--tessera-bg-soft)] px-5 py-4 text-center text-xs leading-relaxed text-[var(--tessera-text-muted)] sm:rounded-2xl">
        {t("fiction")}
      </footer>
    </article>
  );
}

function SectionHeader({ title, body }: { title: string; body?: string }) {
  return (
    <header className="max-w-4xl">
      <h2 className="text-balance font-serif text-[clamp(1.9rem,3.2vw,3.3rem)] leading-tight font-medium tracking-[-0.03em] text-[var(--tessera-text)]">
        {title}
      </h2>
      {body ? (
        <p className="mt-4 text-pretty text-base leading-relaxed text-[var(--tessera-text-muted)]">
          {body}
        </p>
      ) : null}
    </header>
  );
}

function ProofLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      data-proof-link="true"
      className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-[var(--tessera-green)] hover:text-[var(--tessera-text)]"
    >
      {label}
      <ArrowRight className="size-4" aria-hidden />
    </Link>
  );
}
