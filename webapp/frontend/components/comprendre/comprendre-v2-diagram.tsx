"use client";

import {
  Activity,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  Bot,
  Building2,
  ClipboardCheck,
  FileCheck2,
  FlaskConical,
  HandCoins,
  KeyRound,
  Landmark,
  type LucideIcon,
  MessagesSquare,
  Network,
  Radar,
  ScrollText,
  ShieldCheck,
  UserPlus,
} from "lucide-react";
import { useTranslations } from "next-intl";

interface DiagramColumn {
  title: string;
  items: string[];
  caption?: string;
}

interface DiagramFlow {
  label: string;
  detail: string;
}

interface PanelTone {
  border: string;
  glow: string;
  heading: string;
  icon: string;
  item: string;
}

const panelIcons: LucideIcon[][] = [
  [Landmark, HandCoins],
  [MessagesSquare, UserPlus, HandCoins, Network],
  [Activity, FlaskConical, ClipboardCheck, FileCheck2],
];

const panelHeaderIcons = [Building2, Bot, Radar] satisfies [LucideIcon, LucideIcon, LucideIcon];

const panelTones = [
  {
    border: "border-sky-400/35",
    glow: "bg-sky-400/10",
    heading: "text-sky-300",
    icon: "border-sky-400/25 bg-sky-400/10 text-sky-300",
    item: "border-sky-400/15 bg-sky-400/[0.045]",
  },
  {
    border: "border-emerald-400/35",
    glow: "bg-emerald-400/10",
    heading: "text-emerald-300",
    icon: "border-emerald-400/25 bg-emerald-400/10 text-emerald-300",
    item: "border-emerald-400/15 bg-emerald-400/[0.045]",
  },
  {
    border: "border-violet-400/35",
    glow: "bg-violet-400/10",
    heading: "text-violet-300",
    icon: "border-violet-400/25 bg-violet-400/10 text-violet-300",
    item: "border-violet-400/15 bg-violet-400/[0.045]",
  },
] satisfies [PanelTone, PanelTone, PanelTone];

const legendTones = ["bg-sky-400", "bg-cyan-400", "bg-violet-400", "bg-amber-400"];

/** A readable map of Tessera's business, agent, governance and evidence planes. */
export function ComprendreV2Diagram() {
  const t = useTranslations("comprendreV2.diagram");
  const columns = t.raw("columns") as DiagramColumn[];
  const flows = t.raw("flows") as DiagramFlow[];
  const lastColumn = columns.at(-1);
  const fallbackTone = panelTones.at(-1);
  const cockpitCaption = lastColumn?.caption;

  return (
    <figure className="relative overflow-hidden rounded-2xl border border-[var(--tessera-border-strong)] bg-[linear-gradient(145deg,var(--tessera-surface-elevated),var(--tessera-surface))] shadow-[var(--shadow-card-elevated)]">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-48 left-[38%] h-96 w-96 rounded-full bg-[radial-gradient(circle,rgba(52,211,153,0.1),transparent_68%)] blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-32 top-16 h-80 w-80 rounded-full bg-[radial-gradient(circle,rgba(167,139,250,0.09),transparent_70%)] blur-3xl"
      />

      <header className="relative flex flex-wrap items-center justify-between gap-4 border-[var(--tessera-border)] border-b bg-[rgba(4,15,27,0.28)] px-5 py-4 sm:px-7">
        <div className="flex items-center gap-3">
          <span className="grid size-10 place-items-center rounded-xl border border-emerald-400/25 bg-emerald-400/10 text-emerald-300">
            <Radar className="size-5" aria-hidden="true" />
          </span>
          <div>
            <p className="text-base font-semibold text-[var(--tessera-text)]">{cockpitCaption}</p>
            <p className="mt-0.5 text-xs text-[var(--tessera-text-subtle)]">{t("legend")}</p>
          </div>
        </div>
        <div aria-hidden="true" className="flex items-center gap-2">
          <span className="h-1.5 w-8 rounded-full bg-sky-400/80" />
          <span className="h-1.5 w-8 rounded-full bg-emerald-400/80" />
          <span className="h-1.5 w-8 rounded-full bg-violet-400/80" />
          <span className="h-1.5 w-8 rounded-full bg-amber-400/80" />
        </div>
      </header>

      <div className="relative p-5 sm:p-7">
        <div className="grid items-stretch gap-3 xl:grid-cols-[minmax(0,0.9fr)_7.5rem_minmax(0,1.08fr)_8.5rem_minmax(0,0.98fr)]">
          {columns.map((column, index) => {
            const icons = panelIcons[index] ?? [Bot];
            const tone = panelTones[index] ?? fallbackTone;
            const HeaderIcon = panelHeaderIcons[index] ?? Bot;
            const captionInHeader = column === lastColumn;

            if (!tone) return null;
            return (
              <div key={column.title} className="contents">
                <ArchitecturePanel
                  column={column}
                  icons={icons}
                  tone={tone}
                  headerIcon={HeaderIcon}
                  captionInHeader={captionInHeader}
                />
                {index === 0 ? <GuardBridge label={t("shield")} /> : null}
                {index === 1 ? <ExchangeBridge flows={flows} /> : null}
              </div>
            );
          })}
        </div>

        <div className="relative mx-auto h-7 w-px bg-gradient-to-b from-violet-400/60 to-amber-400/70">
          <ArrowDown
            className="absolute -bottom-1 left-1/2 size-4 -translate-x-1/2 text-amber-300"
            aria-hidden="true"
          />
        </div>

        <section className="relative overflow-hidden rounded-xl border border-amber-400/30 bg-amber-400/[0.045] px-5 py-4">
          <div
            aria-hidden="true"
            className="absolute inset-y-0 left-0 w-1 bg-gradient-to-b from-amber-300 to-sky-400"
          />
          <div className="flex items-start gap-4">
            <span className="grid size-10 shrink-0 place-items-center rounded-xl border border-amber-400/25 bg-amber-400/10 text-amber-300">
              <ScrollText className="size-5" aria-hidden="true" />
            </span>
            <div>
              <h3 className="text-sm font-semibold text-amber-200">{t("audit.title")}</h3>
              <p className="mt-1 text-xs leading-6 text-[var(--tessera-text-muted)]">
                {t("audit.body")}
              </p>
            </div>
          </div>
        </section>

        <figcaption className="relative mt-5 border-[var(--tessera-border)] border-t pt-5">
          <p className="font-mono text-[0.62rem] tracking-[0.13em] text-[var(--tessera-text-subtle)] uppercase">
            {t("legend")}
          </p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {flows.map((flow, index) => (
              <div
                key={flow.label}
                className="rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-bg-soft)] px-4 py-3"
              >
                <div className="flex items-center gap-2.5">
                  <span
                    aria-hidden="true"
                    className={`size-1.5 rounded-full ${legendTones[index] ?? "bg-slate-400"}`}
                  />
                  <strong className="text-xs font-semibold text-[var(--tessera-text)]">
                    {flow.label}
                  </strong>
                </div>
                <p className="mt-1.5 pl-4 text-xs leading-5 text-[var(--tessera-text-muted)]">
                  {flow.detail}
                </p>
              </div>
            ))}
          </div>

          <div className="mt-4 flex items-start gap-3 rounded-xl border border-[var(--tessera-border)] border-dashed bg-[rgba(4,15,27,0.2)] px-4 py-3">
            <KeyRound
              className="mt-0.5 size-4 shrink-0 text-[var(--tessera-text-subtle)]"
              aria-hidden="true"
            />
            <p className="text-xs leading-5 text-[var(--tessera-text-muted)]">{t("door")}</p>
          </div>
        </figcaption>
      </div>
    </figure>
  );
}

function ArchitecturePanel({
  column,
  icons,
  tone,
  headerIcon: HeaderIcon,
  captionInHeader,
}: {
  column: DiagramColumn;
  icons: LucideIcon[];
  tone: PanelTone;
  headerIcon: LucideIcon;
  captionInHeader: boolean;
}) {
  return (
    <section
      className={`relative flex min-w-0 flex-col overflow-hidden rounded-xl border bg-[rgba(4,15,27,0.24)] ${tone.border}`}
    >
      <div aria-hidden="true" className={`absolute inset-x-0 top-0 h-16 blur-2xl ${tone.glow}`} />
      <div className="relative flex items-center gap-3 border-white/5 border-b px-4 py-3.5">
        <span className={`grid size-9 place-items-center rounded-lg border ${tone.icon}`}>
          <HeaderIcon className="size-4" aria-hidden="true" />
        </span>
        <h3 className={`text-sm font-semibold ${tone.heading}`}>{column.title}</h3>
      </div>
      <ul className="relative grid flex-1 content-center gap-2 p-3.5">
        {column.items.map((item, index) => {
          const Icon = icons[index] ?? Network;
          return (
            <li
              key={item}
              className={`flex min-h-11 items-center gap-3 rounded-lg border px-3 py-2 text-xs leading-5 text-[var(--tessera-text)] ${tone.item}`}
            >
              <Icon className={`size-4 shrink-0 ${tone.heading}`} aria-hidden="true" />
              <span>{item}</span>
            </li>
          );
        })}
      </ul>
      {column.caption && !captionInHeader ? (
        <p className="relative border-white/5 border-t px-4 py-3 text-center text-[0.68rem] leading-5 text-[var(--tessera-text-muted)]">
          {column.caption}
        </p>
      ) : null}
    </section>
  );
}

function GuardBridge({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center py-1 xl:flex-col xl:py-0">
      <div className="relative flex w-full items-center justify-center xl:h-px">
        <span
          aria-hidden="true"
          className="absolute inset-x-3 top-1/2 h-px bg-gradient-to-r from-sky-400/55 via-emerald-300/80 to-emerald-400/55"
        />
        <ArrowRight className="absolute right-1 size-4 text-emerald-300" aria-hidden="true" />
        <span className="relative z-10 grid size-10 place-items-center rounded-xl border border-emerald-400/35 bg-[#09231f] text-emerald-300 shadow-[0_0_24px_rgba(52,211,153,0.16)]">
          <ShieldCheck className="size-5" aria-hidden="true" />
        </span>
      </div>
      <p className="mt-2 max-w-[8rem] text-center text-[0.64rem] leading-4 text-emerald-200/80">
        {label}
      </p>
    </div>
  );
}

function ExchangeBridge({ flows }: { flows: DiagramFlow[] }) {
  const telemetry = flows.at(1);
  const tests = flows.at(2);

  return (
    <div className="flex flex-col justify-center gap-3 rounded-xl border border-[var(--tessera-border)] bg-[rgba(4,15,27,0.18)] p-3 xl:border-0 xl:bg-transparent xl:p-0">
      <FlowRail flow={telemetry} direction="right" variant="telemetry" />
      <FlowRail flow={tests} direction="left" variant="test" />
    </div>
  );
}

function FlowRail({
  flow,
  direction,
  variant,
}: {
  flow?: DiagramFlow;
  direction: "left" | "right";
  variant: "telemetry" | "test";
}) {
  if (!flow) return null;
  const Icon = direction === "right" ? ArrowRight : ArrowLeft;
  const tone = variant === "telemetry" ? "text-sky-300" : "text-violet-300";
  const line = variant === "telemetry" ? "bg-sky-400/60" : "bg-violet-400/60";

  return (
    <div>
      <div className={`flex items-center gap-1 ${direction === "left" ? "flex-row-reverse" : ""}`}>
        <span aria-hidden="true" className={`h-px flex-1 ${line}`} />
        <Icon className={`size-4 shrink-0 ${tone}`} aria-hidden="true" />
      </div>
      <p className={`mt-1.5 text-center text-[0.62rem] leading-4 ${tone}`}>{flow.label}</p>
    </div>
  );
}
