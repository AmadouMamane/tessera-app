"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ChevronDown,
  ChevronRight,
  Cpu,
  Database,
  History,
  MessageSquare,
  Paperclip,
  Plus,
  Shield,
  ShieldCheck,
  Tag,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import {
  TemporalRail,
  useRailTimeline,
  useTemporalState,
} from "@/components/overview/temporal-rail";
import { fetchAgentConsole } from "@/lib/api/client";
import type { AgentConsole as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

type T = ReturnType<typeof useTranslations<"agentConsole">>;

const FIELD_ICONS: LucideIcon[] = [Cpu, Tag, Database, Shield, Activity];

const CHIP_TONE: Record<string, string> = {
  info: "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]",
  warn: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  ghost: "border-[var(--tessera-border)] bg-transparent text-[var(--tessera-text-muted)]",
};
const SCORE_TONE: Record<string, string> = {
  good: "text-emerald-300",
  warn: "text-amber-300",
  crit: "text-red-300",
};
const STATUS_TONE: Record<string, string> = {
  good: "text-emerald-400",
  warn: "text-amber-300",
  crit: "text-red-400",
};
const BADGE_TONE: Record<string, string> = {
  good: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  warn: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  crit: "border-red-500/30 bg-red-500/15 text-red-300",
};

export function AgentConsole() {
  const t = useTranslations("agentConsole");
  const temporal = useTemporalState();
  const railTimeline = useRailTimeline();
  const { data } = useQuery({
    queryKey: ["agent-console"],
    queryFn: ({ signal }) => fetchAgentConsole(signal),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  if (!data?.available) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        {data ? t("unavailable") : t("loading")}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      <StatusBar data={data} />

      <div className="grid gap-3 xl:grid-cols-12">
        <div className="flex min-w-0 flex-col gap-3 xl:col-span-8">
          <TemporalRail
            mode={temporal.mode}
            liveStatus={t("realtime")}
            timeline={railTimeline.data}
            selectedAt={temporal.selectedAt}
            onSelectedAtChange={temporal.setSelectedAt}
            periodKey={temporal.periodKey}
            onPeriodChange={temporal.setPeriodKey}
            onModeChange={temporal.changeMode}
          />
          <ChatCard data={data} />
        </div>

        <div className="flex min-w-0 flex-col gap-3 xl:col-span-4">
          <KpiRow data={data} />
          <Inspector data={data} t={t} />
        </div>
      </div>
    </div>
  );
}

// ── status sub-bar ───────────────────────────────────────────────────────────

function StatusBar({ data }: { data: Data }) {
  const s = data.status;
  const a = data.actions;
  if (!s || !a) return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2">
      <div className="flex min-w-0 flex-wrap items-center gap-x-5 gap-y-1.5 text-[0.72rem]">
        <span className="inline-flex items-center gap-1.5 font-medium text-emerald-300">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Session active
        </span>
        <span className="text-[var(--tessera-text-muted)]">
          ID: <span className="tabular-nums text-[var(--tessera-text)]">{s.session_id}</span>
        </span>
        {s.fields.map((f, i) => {
          const Icon: LucideIcon = FIELD_ICONS[i % FIELD_ICONS.length] ?? Cpu;
          return (
            <span key={f.label} className="inline-flex items-center gap-1.5">
              <Icon className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
              <span className="text-[var(--tessera-text-muted)]">{f.label}</span>
              <span className="font-medium text-[var(--tessera-text)]">{f.value}</span>
            </span>
          );
        })}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <button
          type="button"
          className="flex h-8 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[0.72rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          <History className="h-3.5 w-3.5" /> {a.replay}
        </button>
        <button
          type="button"
          className="flex h-8 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[0.72rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          24h <ChevronDown className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          className="flex h-8 items-center gap-1.5 rounded-md border border-[#7c5cf5] bg-[#6d4aed] px-3 text-[0.72rem] font-medium text-white hover:bg-[#7c5cf5]"
        >
          <Plus className="h-3.5 w-3.5" /> {a.new_session}
        </button>
      </div>
    </div>
  );
}

// ── chat ─────────────────────────────────────────────────────────────────────

function ChatCard({ data }: { data: Data }) {
  const a = data.actions;
  const f = data.footer;
  return (
    <section className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
      <div className="flex items-start gap-3 border-b border-[var(--tessera-border)] p-3.5">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[#7c5cf5]/40 bg-[#6d4aed]/15 text-[#b9a6ff]">
          <MessageSquare className="h-4.5 w-4.5" />
        </span>
        <div className="min-w-0">
          <h2 className="text-[0.95rem] font-semibold text-[var(--tessera-text)]">{data.title}</h2>
          <p className="text-[0.72rem] text-[var(--tessera-text-muted)]">{data.subtitle}</p>
        </div>
      </div>

      <div className="flex flex-col gap-4 p-3.5">
        {(data.transcript ?? []).map((m) =>
          m.role === "user" ? (
            <UserMsg key={`u-${m.time}`} time={m.time} text={m.text ?? ""} />
          ) : (
            <AssistantMsg key={`a-${m.time}`} m={m} />
          ),
        )}
      </div>

      <div className="border-t border-[var(--tessera-border)] p-3.5">
        <div className="flex items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 py-2.5">
          <span className="flex-1 truncate text-[0.74rem] text-[var(--tessera-text-muted)]">
            {a?.input_placeholder}
          </span>
          <Paperclip className="h-4 w-4 shrink-0 text-[var(--tessera-text-muted)]" />
        </div>
        <div className="mt-2.5 flex flex-wrap items-center gap-2">
          {(a?.footer_actions ?? []).map((label) => (
            <button
              key={label}
              type="button"
              className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1.5 text-[0.68rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {f ? (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-[var(--tessera-border)] px-3.5 py-2 text-[0.66rem] text-[var(--tessera-text-muted)]">
          <span>{f.started}</span>
          <span className="inline-flex items-center gap-1.5 text-emerald-300">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Live
          </span>
          <span>Contexte : {f.context}</span>
          <span className="inline-flex items-center gap-1">
            Langue : <span className="text-[var(--tessera-text)]">{f.language}</span>
            <ChevronDown className="h-3 w-3" />
          </span>
        </div>
      ) : null}
    </section>
  );
}

function UserMsg({ time, text }: { time: string; text: string }) {
  return (
    <div className="flex flex-col items-end gap-1">
      <span className="text-[0.66rem] text-[var(--tessera-text-muted)]">
        <span className="font-medium text-[var(--tessera-text)]">Vous</span> {time}
      </span>
      <p className="max-w-[85%] rounded-xl rounded-tr-sm border border-[#7c5cf5]/30 bg-[#6d4aed]/12 px-3 py-2 text-[0.78rem] leading-relaxed text-[var(--tessera-text)]">
        {text}
      </p>
    </div>
  );
}

function AssistantMsg({ m }: { m: NonNullable<Data["transcript"]>[number] }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="inline-flex items-center gap-1.5 text-[0.66rem] text-[var(--tessera-text-muted)]">
        <span className="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400">
          <ShieldCheck className="h-3 w-3" />
        </span>
        <span className="font-medium text-[var(--tessera-text)]">Assistant</span> {m.time}
        {m.latency ? <span>- {m.latency}</span> : null}
      </span>
      <div className="rounded-xl rounded-tl-sm border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3.5 py-3 text-[0.78rem] leading-relaxed text-[var(--tessera-text)]">
        {m.intro ? <p>{m.intro}</p> : null}
        {m.points ? (
          <ol className="mt-2 flex list-decimal flex-col gap-1.5 pl-4 marker:text-[var(--tessera-text-muted)]">
            {m.points.map((p) => (
              <li key={p.ref}>
                <span className="font-medium text-[#e0a23a]">
                  {p.title} ({p.ref})
                </span>{" "}
                : {p.body}
              </li>
            ))}
          </ol>
        ) : null}
        {m.closing ? <p className="mt-2">{m.closing}</p> : null}

        {m.chips ? (
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            {m.chips.map((c) => (
              <span
                key={c.label}
                className={cn(
                  "rounded-md border px-2 py-1 text-[0.64rem]",
                  CHIP_TONE[c.kind] ?? CHIP_TONE.info,
                )}
              >
                {c.label}
              </span>
            ))}
          </div>
        ) : null}
      </div>
      <div className="flex items-center gap-3 text-[0.66rem] text-[var(--tessera-text-muted)]">
        <button type="button" className="inline-flex items-center gap-1 hover:text-emerald-300">
          <ThumbsUp className="h-3.5 w-3.5" /> Utile
        </button>
        <button type="button" className="inline-flex items-center gap-1 hover:text-red-300">
          <ThumbsDown className="h-3.5 w-3.5" /> Pas utile
        </button>
      </div>
    </div>
  );
}

// ── right: KPIs + inspector ────────────────────────────────────────────────

function KpiRow({ data }: { data: Data }) {
  const a = data.actions;
  return (
    <div className="flex items-stretch gap-2.5">
      {(data.kpis ?? []).map((k) => (
        <div
          key={k.key}
          className="flex flex-1 flex-col justify-center rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2"
        >
          <p className="truncate text-[0.64rem] text-[var(--tessera-text-muted)]">{k.label}</p>
          <p className="mt-0.5 text-[1.1rem] font-semibold tabular-nums text-emerald-300">
            {k.value}
          </p>
        </div>
      ))}
      <button
        type="button"
        className="flex shrink-0 items-center rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 text-[0.7rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
      >
        {a?.timeline_incidents}
      </button>
    </div>
  );
}

function Inspector({ data, t }: { data: Data; t: T }) {
  const tabs = data.tabs ?? [];
  const [active, setActive] = useState(tabs[0] ?? "Contexte");
  return (
    <section className="flex min-w-0 flex-1 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
      <nav className="flex items-center gap-4 border-b border-[var(--tessera-border)] px-3.5">
        {tabs.map((tab) => {
          const on = tab === active;
          return (
            <button
              key={tab}
              type="button"
              onClick={() => setActive(tab)}
              className={cn(
                "-mb-px border-b-2 py-2.5 text-[0.72rem] transition-colors",
                on
                  ? "border-[#e0a23a] font-medium text-[#e0a23a]"
                  : "border-transparent text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
              )}
            >
              {tab}
            </button>
          );
        })}
      </nav>

      <div className="flex flex-col divide-y divide-[var(--tessera-border)]">
        {(active === "Contexte" || active === "Trace") && data.quality && active === "Contexte" ? (
          <Quality q={data.quality} />
        ) : null}
        {(active === "Contexte" || active === "Sources") && data.sources ? (
          <SourcesPanel s={data.sources} />
        ) : null}
        {(active === "Contexte" || active === "Outils") && data.tools ? (
          <ToolsPanel tl={data.tools} />
        ) : null}
        {(active === "Contexte" || active === "Garde-fous") && data.guardrails ? (
          <GuardrailsPanel g={data.guardrails} />
        ) : null}
        {(active === "Contexte" || active === "Trace") && data.trace ? (
          <TracePanel tr={data.trace} />
        ) : null}
      </div>
      <div className="mt-auto border-t border-[var(--tessera-border)] px-3.5 py-2 text-[0.64rem] text-[var(--tessera-text-muted)]">
        {t("idSession")}: <span className="tabular-nums">{data.footer?.session_id}</span>
      </div>
    </section>
  );
}

function PanelHead({ title, cta }: { title: string; cta?: string }) {
  return (
    <div className="mb-2 flex items-center justify-between gap-2">
      <h3 className="text-[0.74rem] font-semibold text-[var(--tessera-text)]">{title}</h3>
      {cta ? (
        <button
          type="button"
          className="inline-flex items-center gap-0.5 text-[0.64rem] text-[#b9a6ff] hover:text-white"
        >
          {cta} <ChevronRight className="h-3 w-3" />
        </button>
      ) : null}
    </div>
  );
}

function Quality({ q }: { q: NonNullable<Data["quality"]> }) {
  return (
    <div className="p-3.5">
      <div className="mb-2.5 flex items-center justify-between gap-2">
        <h3 className="text-[0.74rem] font-semibold text-[var(--tessera-text)]">{q.title}</h3>
        <span
          className={cn(
            "rounded-full border px-2 py-0.5 text-[0.6rem] font-medium",
            BADGE_TONE[q.badge_tone] ?? BADGE_TONE.good,
          )}
        >
          {q.badge}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2.5">
        {q.rows.map((r) => (
          <div
            key={r.label}
            className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5"
          >
            <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{r.label}</p>
            <p className="mt-1 tabular-nums">
              <span className={cn("text-[1.05rem] font-semibold", SCORE_TONE[r.tone])}>
                {r.value}
              </span>
              <span className="text-[0.62rem] text-[var(--tessera-text-muted)]">{r.scale}</span>
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function SourcesPanel({ s }: { s: NonNullable<Data["sources"]> }) {
  return (
    <div className="p-3.5">
      <PanelHead title={s.title} cta={s.cta} />
      <ul className="flex flex-col gap-1.5 text-[0.72rem]">
        {s.rows.map((r) => (
          <li key={r.label} className="flex items-center justify-between gap-2">
            <span className="min-w-0 truncate text-[var(--tessera-text)]">{r.label}</span>
            <span className="shrink-0 text-[0.64rem] text-[var(--tessera-text-muted)]">
              {r.scope}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ToolsPanel({ tl }: { tl: NonNullable<Data["tools"]> }) {
  return (
    <div className="p-3.5">
      <PanelHead title={tl.title} />
      <ul className="flex flex-col gap-1.5 text-[0.72rem]">
        {tl.rows.map((r) => (
          <li key={r.name} className="flex items-center justify-between gap-2">
            <span className="min-w-0 truncate font-mono text-[0.68rem] text-[var(--tessera-text)]">
              {r.name}
            </span>
            <span className="flex shrink-0 items-center gap-3">
              <span className={cn("text-[0.66rem] font-medium", STATUS_TONE[r.tone])}>
                {r.status}
              </span>
              <span className="tabular-nums text-[var(--tessera-text-muted)]">{r.latency}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function GuardrailsPanel({ g }: { g: NonNullable<Data["guardrails"]> }) {
  return (
    <div className="p-3.5">
      <PanelHead title={g.title} />
      <ul className="flex flex-col gap-2">
        {g.rows.map((r) => (
          <li key={r.name} className="flex flex-col gap-1">
            <div className="flex items-center justify-between gap-2 text-[0.72rem]">
              <span className="font-medium text-[var(--tessera-text)]">{r.name}</span>
              <span
                className={cn(
                  "rounded-full border px-2 py-0.5 text-[0.6rem] font-medium",
                  BADGE_TONE[r.tone] ?? BADGE_TONE.warn,
                )}
              >
                {r.status}
              </span>
            </div>
            <p className="text-[0.64rem] text-[var(--tessera-text-muted)]">{r.detail}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function TracePanel({ tr }: { tr: NonNullable<Data["trace"]> }) {
  return (
    <div className="p-3.5">
      <PanelHead title={tr.title} cta={tr.cta} />
      <ul className="flex flex-col gap-1.5 text-[0.72rem]">
        {tr.rows.map((r) => (
          <li key={r.label} className="flex items-center justify-between gap-2">
            <span className="inline-flex min-w-0 items-center gap-2 text-[var(--tessera-text)]">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[#6d4aed]" />
              <span className="truncate">{r.label}</span>
            </span>
            <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
              {r.value}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
