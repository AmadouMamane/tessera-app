"use client";

import {
  Activity,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  Bot,
  Building2,
  ClipboardCheck,
  Database,
  FileCheck2,
  FlaskConical,
  HandCoins,
  KeyRound,
  Landmark,
  type LucideIcon,
  MessagesSquare,
  Network,
  Orbit,
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

interface VisualTone {
  border: string;
  glow: string;
  icon: string;
  text: string;
}

const businessIcons = [Landmark, HandCoins] satisfies LucideIcon[];
const agentIcons = [MessagesSquare, UserPlus, HandCoins, Network] satisfies LucideIcon[];
const cockpitIcons = [Activity, FlaskConical, ClipboardCheck, FileCheck2] satisfies LucideIcon[];
const agentFoundationIcons = [Database, ShieldCheck] satisfies LucideIcon[];

const agentTones = [
  {
    border: "border-sky-400/30",
    glow: "from-sky-400/18",
    icon: "border-sky-300/35 bg-sky-400/15 text-[var(--tessera-fg-info)]",
    text: "text-[var(--tessera-fg-info)]",
  },
  {
    border: "border-cyan-400/25",
    glow: "from-cyan-400/16",
    icon: "border-cyan-300/35 bg-cyan-400/15 text-[var(--tessera-fg-teal)]",
    text: "text-[var(--tessera-fg-teal)]",
  },
  {
    border: "border-emerald-400/25",
    glow: "from-emerald-400/16",
    icon: "border-emerald-300/35 bg-emerald-400/15 text-[var(--tessera-fg-success)]",
    text: "text-[var(--tessera-fg-success)]",
  },
  {
    border: "border-violet-400/25",
    glow: "from-violet-400/16",
    icon: "border-violet-300/35 bg-violet-400/15 text-[var(--tessera-fg-accent)]",
    text: "text-[var(--tessera-fg-accent)]",
  },
] satisfies VisualTone[];

const flowVisuals = [
  { icon: KeyRound, text: "text-[var(--tessera-fg-info)]", line: "bg-sky-400/60" },
  { icon: Activity, text: "text-[var(--tessera-fg-teal)]", line: "bg-cyan-400/60" },
  {
    icon: FlaskConical,
    text: "text-[var(--tessera-fg-accent)]",
    line: "bg-violet-400/60",
  },
  {
    icon: ScrollText,
    text: "text-[var(--tessera-fg-warning)]",
    line: "bg-amber-400/60",
  },
];

const fallbackAgentTone = agentTones.at(-1);
const fallbackFlowVisual = flowVisuals.at(-1);
const panelGlowTones = {
  business: "bg-sky-400/10",
  agents: "bg-emerald-400/14",
  cockpit: "bg-violet-400/10",
};

/** A readable map of Tessera's business, agent, governance and evidence planes. */
export function ComprendreV2Diagram() {
  const app = useTranslations("app");
  const t = useTranslations("comprendreV2.diagram");
  const columns = t.raw("columns") as DiagramColumn[];
  const flows = t.raw("flows") as DiagramFlow[];
  const agentFoundations = t.raw("agentFoundations") as string[];
  const [business, agents, cockpit] = columns;
  const accessFlow = flows.at(0);

  if (!business || !agents || !cockpit) return null;

  return (
    <figure className="relative overflow-hidden rounded-2xl border border-[var(--tessera-border-strong)] bg-[linear-gradient(145deg,var(--tessera-surface-elevated),var(--tessera-surface))] shadow-[var(--shadow-card-elevated)]">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-48 left-[43%] h-96 w-96 rounded-full bg-[radial-gradient(circle,rgba(52,211,153,0.13),transparent_68%)] blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -left-40 top-32 h-80 w-80 rounded-full bg-[radial-gradient(circle,rgba(56,189,248,0.08),transparent_70%)] blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-32 top-24 h-80 w-80 rounded-full bg-[radial-gradient(circle,rgba(167,139,250,0.09),transparent_70%)] blur-3xl"
      />

      <header className="relative flex items-center border-[var(--tessera-border)] border-b bg-[rgba(4,15,27,0.3)] px-5 py-5 sm:px-7">
        <div className="flex min-w-0 items-center gap-4">
          <span className="relative grid size-11 shrink-0 place-items-center rounded-xl border border-cyan-400/30 bg-cyan-400/10 text-[var(--tessera-fg-teal)] shadow-[0_0_28px_rgba(34,211,238,0.12)]">
            <Orbit className="size-6" aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="font-mono text-[0.66rem] tracking-[0.17em] text-[var(--tessera-fg-teal)] uppercase">
              {app("title")}
            </p>
            <p className="mt-1 max-w-[48rem] text-sm font-medium leading-6 text-[var(--tessera-text)]">
              {t("caption")}
            </p>
          </div>
        </div>
      </header>

      <div className="relative p-5 sm:p-7">
        <div className="grid items-stretch gap-3 xl:grid-cols-[minmax(0,0.82fr)_7rem_minmax(0,1.32fr)_8.5rem_minmax(0,0.96fr)]">
          <BusinessPanel column={business} />
          <GuardBridge label={t("shield")} />
          <AgentPanel column={agents} foundations={agentFoundations} />
          <ExchangeBridge flows={flows} />
          <CockpitPanel column={cockpit} />
        </div>

        <div className="grid xl:grid-cols-[minmax(0,0.82fr)_7rem_minmax(0,1.32fr)_8.5rem_minmax(0,0.96fr)]">
          <div className="xl:col-start-3">
            <div className="relative mx-auto h-8 w-px bg-gradient-to-b from-emerald-300/65 to-amber-300/80">
              <ArrowDown
                className="absolute -bottom-1 left-1/2 size-4 -translate-x-1/2 text-[var(--tessera-fg-warning)]"
                aria-hidden="true"
              />
            </div>
            <AuditLedger title={t("audit.title")} body={t("audit.body")} />
          </div>
        </div>

        <figcaption className="relative mt-5 border-[var(--tessera-border)] border-t pt-5">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {flows.map((flow, index) => {
              const visual = flowVisuals[index] ?? fallbackFlowVisual;
              const FlowIcon = visual?.icon ?? Network;
              const isAccessFlow = flow === accessFlow;

              return (
                <div
                  key={flow.label}
                  className="group relative overflow-hidden rounded-xl border border-[var(--tessera-border)] bg-[rgba(4,15,27,0.34)] px-4 py-4"
                >
                  <span
                    aria-hidden="true"
                    className={`absolute inset-x-0 top-0 h-px ${visual?.line ?? "bg-slate-400/50"}`}
                  />
                  <div className="flex items-start gap-3">
                    <span
                      className={`grid size-9 shrink-0 place-items-center rounded-lg border border-white/10 bg-white/[0.035] ${visual?.text ?? "text-[var(--tessera-text-muted)]"}`}
                    >
                      <FlowIcon className="size-4" aria-hidden="true" />
                    </span>
                    <div className="min-w-0">
                      <strong className="text-xs font-semibold text-[var(--tessera-text)]">
                        {flow.label}
                      </strong>
                      <p className="mt-1 text-[0.68rem] leading-5 text-[var(--tessera-text-muted)]">
                        {flow.detail}
                      </p>
                    </div>
                  </div>
                  {isAccessFlow ? (
                    <p
                      data-contrast-label="door"
                      className="mt-3 border-white/[0.06] border-t pt-2.5 text-[0.6rem] leading-4 font-medium text-[var(--tessera-text-muted)]"
                    >
                      {t("door")}
                    </p>
                  ) : null}
                </div>
              );
            })}
          </div>
        </figcaption>
      </div>
    </figure>
  );
}

function BusinessPanel({ column }: { column: DiagramColumn }) {
  return (
    <section
      data-diagram-plane="business"
      className="relative flex min-w-0 flex-col overflow-hidden rounded-xl border border-sky-400/35 bg-[linear-gradient(155deg,rgba(14,62,96,0.2),rgba(4,15,27,0.34)_58%)]"
    >
      <PanelGlow tone={panelGlowTones.business} />
      <PanelHeading icon={Building2} title={column.title} tone="sky" />
      <ul className="relative grid flex-1 content-center gap-3 p-4">
        {column.items.map((item, index) => {
          const Icon = businessIcons[index] ?? Landmark;
          return (
            <li
              key={item}
              className="flex min-h-14 items-center gap-3 rounded-xl border border-sky-400/20 bg-sky-400/[0.055] px-3 py-3 text-xs leading-5 text-[var(--tessera-text)]"
            >
              <span className="grid size-9 shrink-0 place-items-center rounded-lg border border-sky-300/25 bg-sky-400/10 text-[var(--tessera-fg-info)]">
                <Icon className="size-4" aria-hidden="true" />
              </span>
              <span>{item}</span>
            </li>
          );
        })}
      </ul>
      {column.caption ? (
        <p className="relative border-sky-300/10 border-t px-4 py-3 text-center text-[0.66rem] leading-5 text-[var(--tessera-fg-info)]/55">
          {column.caption}
        </p>
      ) : null}
    </section>
  );
}

function AgentPanel({ column, foundations }: { column: DiagramColumn; foundations: string[] }) {
  return (
    <section
      data-diagram-plane="agents"
      className="relative min-w-0 overflow-hidden rounded-xl border border-emerald-300/45 bg-[linear-gradient(145deg,rgba(6,78,67,0.22),rgba(4,15,27,0.42)_62%)] shadow-[0_0_38px_rgba(52,211,153,0.07)]"
    >
      <PanelGlow tone={panelGlowTones.agents} />
      <div
        aria-hidden="true"
        className="absolute inset-0 opacity-35 [background-image:radial-gradient(circle_at_center,rgba(110,231,183,0.22)_0,rgba(110,231,183,0.22)_1px,transparent_1px)] [background-size:22px_22px]"
      />
      <PanelHeading icon={Bot} title={column.title} tone="emerald" featured />

      <div className="relative p-4">
        <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-2">
          {column.items.map((item, index) => {
            const Icon = agentIcons[index] ?? Bot;
            const tone = agentTones[index] ?? fallbackAgentTone;
            return (
              <li
                key={item}
                data-agent-node="true"
                className={`relative overflow-hidden rounded-xl border bg-[rgba(4,15,27,0.52)] p-4 text-center ${tone?.border ?? "border-emerald-400/25"}`}
              >
                <span
                  aria-hidden="true"
                  className={`absolute inset-x-0 top-0 h-14 bg-gradient-to-b ${tone?.glow ?? "from-emerald-400/15"} to-transparent`}
                />
                <span
                  className={`relative mx-auto grid size-12 place-items-center rounded-xl border shadow-[0_8px_24px_rgba(0,0,0,0.2)] ${tone?.icon ?? "border-emerald-300/35 bg-emerald-400/15 text-[var(--tessera-fg-success)]"}`}
                >
                  <Icon className="size-6" aria-hidden="true" />
                </span>
                <span className="relative mt-3 block text-xs font-medium leading-5 text-[var(--tessera-text)]">
                  {item}
                </span>
              </li>
            );
          })}
        </ul>
        <ul className="mt-3 grid gap-2 sm:grid-cols-2">
          {foundations.map((foundation, index) => {
            const FoundationIcon = agentFoundationIcons[index] ?? ShieldCheck;
            return (
              <li
                key={foundation}
                data-agent-foundation="true"
                className="flex min-h-10 items-center justify-center gap-2 rounded-lg border border-emerald-300/20 bg-emerald-400/[0.055] px-3 py-2 text-center text-[0.68rem] font-medium text-[var(--tessera-fg-success)]/85"
              >
                <FoundationIcon
                  className="size-4 shrink-0 text-[var(--tessera-fg-success)]"
                  aria-hidden="true"
                />
                <span>{foundation}</span>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}

function CockpitPanel({ column }: { column: DiagramColumn }) {
  return (
    <section
      data-diagram-plane="cockpit"
      className="relative flex min-w-0 flex-col overflow-hidden rounded-xl border border-violet-400/35 bg-[linear-gradient(155deg,rgba(64,45,115,0.2),rgba(4,15,27,0.34)_58%)]"
    >
      <PanelGlow tone={panelGlowTones.cockpit} />
      <PanelHeading icon={Radar} title={column.title} tone="violet" />
      <ul className="relative grid flex-1 content-center gap-2.5 p-4">
        {column.items.map((item, index) => {
          const Icon = cockpitIcons[index] ?? Radar;
          return (
            <li
              key={item}
              className="flex min-h-12 items-center gap-3 rounded-xl border border-violet-400/20 bg-violet-400/[0.055] px-3 py-2.5 text-xs leading-5 text-[var(--tessera-text)]"
            >
              <span className="grid size-8 shrink-0 place-items-center rounded-lg border border-violet-300/20 bg-violet-400/10 text-[var(--tessera-fg-accent)]">
                <Icon className="size-4" aria-hidden="true" />
              </span>
              <span>{item}</span>
            </li>
          );
        })}
      </ul>
      {column.caption ? (
        <p className="relative border-violet-300/10 border-t px-4 py-3 text-center text-[0.66rem] leading-5 text-[var(--tessera-fg-accent)]/55">
          {column.caption}
        </p>
      ) : null}
    </section>
  );
}

function PanelHeading({
  icon: Icon,
  title,
  tone,
  featured = false,
}: {
  icon: LucideIcon;
  title: string;
  tone: "sky" | "emerald" | "violet";
  featured?: boolean;
}) {
  const iconStyles = {
    sky: "border-sky-300/25 bg-sky-400/10 text-[var(--tessera-fg-info)]",
    emerald: "border-emerald-300/30 bg-emerald-400/12 text-[var(--tessera-fg-success)]",
    violet: "border-violet-300/25 bg-violet-400/10 text-[var(--tessera-fg-accent)]",
  };
  const textStyles = {
    sky: "text-[var(--tessera-fg-info)]",
    emerald: "text-[var(--tessera-fg-success)]",
    violet: "text-[var(--tessera-fg-accent)]",
  };

  return (
    <div className="relative flex items-center justify-center gap-3 border-white/[0.06] border-b px-4 py-4">
      <span className={`grid size-9 place-items-center rounded-lg border ${iconStyles[tone]}`}>
        <Icon className="size-4" aria-hidden="true" />
      </span>
      <h3 className={`${featured ? "text-base" : "text-sm"} font-semibold ${textStyles[tone]}`}>
        {title}
      </h3>
    </div>
  );
}

function PanelGlow({ tone }: { tone: string }) {
  return <div aria-hidden="true" className={`absolute inset-x-0 top-0 h-24 blur-3xl ${tone}`} />;
}

function GuardBridge({ label }: { label: string }) {
  return (
    <div
      data-diagram-guard="true"
      className="flex items-center justify-center py-2 xl:flex-col xl:py-0"
    >
      <div className="relative flex w-full items-center justify-center xl:h-12">
        <span
          aria-hidden="true"
          className="absolute inset-x-2 top-1/2 h-px bg-gradient-to-r from-sky-400/65 via-emerald-300/85 to-emerald-400/65"
        />
        <ArrowRight
          className="absolute right-0 size-4 text-[var(--tessera-fg-success)]"
          aria-hidden="true"
        />
        <span className="relative z-10 grid size-11 place-items-center rounded-xl border border-emerald-300/45 bg-[#09261f] text-emerald-200 shadow-[0_0_28px_rgba(52,211,153,0.2)]">
          <ShieldCheck className="size-5" aria-hidden="true" />
        </span>
      </div>
      <p
        data-diagram-guard-label="true"
        className="mt-2 max-w-[7.5rem] text-center text-[0.6rem] leading-4 text-[var(--tessera-fg-success)]/80"
      >
        {label}
      </p>
    </div>
  );
}

function ExchangeBridge({ flows }: { flows: DiagramFlow[] }) {
  const telemetry = flows.at(1);
  const tests = flows.at(2);

  return (
    <div className="flex flex-col justify-center gap-4 rounded-xl border border-[var(--tessera-border)] bg-[rgba(4,15,27,0.2)] p-3 xl:border-0 xl:bg-transparent xl:p-0">
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
  const tone =
    variant === "telemetry" ? "text-[var(--tessera-fg-teal)]" : "text-[var(--tessera-fg-accent)]";
  const line = variant === "telemetry" ? "bg-cyan-400/65" : "bg-violet-400/65";

  return (
    <div>
      <p className={`mb-1.5 text-center text-[0.62rem] font-medium leading-4 ${tone}`}>
        {flow.label}
      </p>
      <div className={`flex items-center gap-1 ${direction === "left" ? "flex-row-reverse" : ""}`}>
        <span aria-hidden="true" className={`h-px flex-1 ${line}`} />
        <Icon className={`size-4 shrink-0 ${tone}`} aria-hidden="true" />
      </div>
    </div>
  );
}

function AuditLedger({ title, body }: { title: string; body: string }) {
  return (
    <section className="relative overflow-hidden rounded-xl border border-amber-400/30 bg-[linear-gradient(145deg,rgba(120,73,12,0.14),rgba(4,15,27,0.42))] px-4 py-4 shadow-[0_10px_30px_rgba(0,0,0,0.12)]">
      <div
        aria-hidden="true"
        className="absolute inset-y-0 left-0 w-1 bg-gradient-to-b from-amber-300 via-emerald-300 to-sky-400"
      />
      <div className="flex items-start gap-3">
        <span className="grid size-9 shrink-0 place-items-center rounded-lg border border-amber-400/25 bg-amber-400/10 text-[var(--tessera-fg-warning)]">
          <ScrollText className="size-4" aria-hidden="true" />
        </span>
        <div>
          <h3 className="text-xs font-semibold text-[var(--tessera-fg-warning)]">{title}</h3>
          <p className="mt-1 text-[0.66rem] leading-5 text-[var(--tessera-text-muted)]">{body}</p>
        </div>
      </div>
    </section>
  );
}
