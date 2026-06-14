"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  ClipboardCheck,
  Database,
  Download,
  FileText,
  Flag,
  GitCompare,
  Languages,
  Maximize2,
  Meh,
  MessageSquare,
  MessageSquarePlus,
  Mic,
  Plus,
  RefreshCcw,
  RotateCcw,
  SendHorizontal,
  ShieldAlert,
  ShieldCheck,
  Smile,
  SmilePlus,
  Sparkles,
  Terminal,
  ThumbsDown,
  ThumbsUp,
  Wrench,
  X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type { ComponentType, ReactNode } from "react";

import {
  TemporalRail,
  useRailTimeline,
  useTemporalState,
} from "@/components/overview/temporal-rail";
import { fetchAssistantOverview } from "@/lib/api/client";
import type { AssistantOverview as AssistantOverviewData } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

type Tab = "chat" | "console";
type T = ReturnType<typeof useTranslations<"assistant">>;
type Data = AssistantOverviewData;
type Icon = ComponentType<{ className?: string }>;

const ACCENT = "bg-[#6d4aed] text-white hover:bg-[#7c5cf5]";
const GUARD_BADGE: Record<string, string> = {
  warn: "border-amber-500/40 bg-amber-500/15 text-amber-300",
  crit: "border-red-500/40 bg-red-500/15 text-red-300",
  ok: "border-emerald-500/40 bg-emerald-500/15 text-emerald-300",
};

export function AssistantOverview() {
  const t = useTranslations("assistant");
  const temporal = useTemporalState();
  const railTimeline = useRailTimeline();
  const [tab, setTab] = useState<Tab>("chat");
  const { data } = useQuery({
    queryKey: ["assistant-overview"],
    queryFn: ({ signal }) => fetchAssistantOverview(signal),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        …
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pb-1 text-[var(--tessera-text)]">
      <CommandBar t={t} tab={tab} setTab={setTab} data={data} />
      {tab === "console" ? (
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
      ) : null}

      <div className="grid gap-3 xl:grid-cols-12">
        <section className="flex min-w-0 flex-col gap-3 xl:col-span-8">
          <Conversation t={t} tab={tab} data={data} />
        </section>
        <aside className="flex min-w-0 flex-col gap-3 xl:col-span-4">
          {tab === "chat" ? <ChatRail t={t} data={data} /> : <ConsoleRail t={t} data={data} />}
        </aside>
      </div>
    </div>
  );
}

// ── command bar ───────────────────────────────────────────────────────────────

function CommandBar({
  t,
  tab,
  setTab,
  data,
}: { t: T; tab: Tab; setTab: (tab: Tab) => void; data: Data }) {
  const s = data.session;
  const pills =
    tab === "chat"
      ? [
          { icon: Bot, label: t("pill.model"), value: s.model },
          { icon: Database, label: t("pill.sources"), value: s.sources_snapshot },
          { icon: ShieldCheck, label: t("pill.guardrails"), value: s.guardrails_version },
          { icon: Languages, label: t("pill.language"), value: s.language },
        ]
      : [
          { icon: Bot, label: t("pill.model"), value: s.model },
          { icon: Sparkles, label: t("pill.prompt"), value: s.prompt_version },
          { icon: Database, label: t("pill.sources"), value: s.sources_snapshot },
          { icon: ShieldCheck, label: t("pill.guardrails"), value: s.guardrails_version },
          { icon: ClipboardCheck, label: t("pill.trace"), value: s.trace },
        ];

  return (
    <section className="flex min-h-[54px] shrink-0 flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <div className="flex h-9 shrink-0 items-center gap-0.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-0.5">
        {(["chat", "console"] as const).map((tb) => (
          <button
            key={tb}
            type="button"
            onClick={() => setTab(tb)}
            className={cn(
              "h-8 rounded px-3 text-xs font-medium transition-colors",
              tab === tb
                ? "bg-[#6d4aed] text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.18)]"
                : "text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
            )}
          >
            {t(`tabs.${tb}`)}
          </button>
        ))}
      </div>

      <SessionPill t={t} id={s.id} />
      {pills.map((p) => (
        <Pill key={p.label} icon={p.icon} label={p.label} value={p.value} />
      ))}

      <div className="ml-auto flex shrink-0 items-center gap-2">
        <button
          type="button"
          className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          <RotateCcw className="h-3.5 w-3.5" /> {t("replayAt")}
          <span className="text-[var(--tessera-text)]">{s.replay_at}</span>
        </button>
        {tab === "console" ? (
          <span className="flex h-9 items-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text-muted)]">
            {t("period24h")}
          </span>
        ) : null}
        <button
          type="button"
          className={cn(
            "flex h-9 items-center gap-2 rounded-md border border-[#7c5cf5] px-3 text-xs font-medium shadow-[inset_0_1px_0_rgba(255,255,255,0.18)]",
            ACCENT,
          )}
        >
          <Plus className="h-4 w-4" /> {t("newSession")}
        </button>
      </div>
    </section>
  );
}

function SessionPill({ t, id }: { t: T; id: string }) {
  return (
    <div className="flex h-9 shrink-0 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5">
      <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]" />
      <div className="leading-tight">
        <p className="text-[0.78rem] font-medium text-[var(--tessera-text)]">
          {t("sessionActive")}
        </p>
        <p className="text-[0.6rem] text-[var(--tessera-text-muted)]">
          {t("pill.id")}: {id}
        </p>
      </div>
    </div>
  );
}

function Pill({ icon: I, label, value }: { icon: Icon; label: string; value: string }) {
  return (
    <div className="flex h-9 shrink-0 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5">
      <I className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)]" />
      <div className="leading-tight">
        <p className="text-[0.6rem] text-[var(--tessera-text-muted)]">{label}</p>
        <p className="text-[0.74rem] font-medium text-[var(--tessera-text)]">{value}</p>
      </div>
    </div>
  );
}

// ── conversation (shared left column) ─────────────────────────────────────────

function Conversation({ t, tab, data }: { t: T; tab: Tab; data: Data }) {
  const isConsole = tab === "console";
  return (
    <div className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
      {/* header */}
      <div className="flex items-start gap-3 border-b border-[var(--tessera-border)] p-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-[#7c5cf5]/40 bg-[#6d4aed]/15 text-[#b9a6ff]">
          {isConsole ? <Terminal className="h-4 w-4" /> : <MessageSquare className="h-4 w-4" />}
        </span>
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-[var(--tessera-text)]">
            {t(isConsole ? "console.title" : "chat.title")}
          </h2>
          <p className="mt-0.5 text-xs text-[var(--tessera-text-muted)]">
            {t(isConsole ? "console.subtitle" : "chat.subtitle")}
          </p>
        </div>
      </div>

      {/* messages */}
      <div className="flex flex-col gap-4 p-4">
        {data.messages.map((m) =>
          m.role === "user" ? (
            <UserMessage key={`${m.role}-${m.time}`} t={t} time={m.time} text={m.text ?? ""} />
          ) : (
            <AssistantMessage key={`${m.role}-${m.time}`} t={t} isConsole={isConsole} message={m} />
          ),
        )}

        {/* sources / chips under the answer */}
        {isConsole ? <ConsoleAnswerMeta t={t} data={data} /> : <ChatAnswerMeta t={t} data={data} />}
      </div>

      {/* suggestions (chat only) */}
      {!isConsole ? (
        <div className="flex flex-wrap gap-2 px-4 pb-3">
          {data.suggestions.map((sug) => (
            <button
              key={sug}
              type="button"
              className="rounded-full border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 py-1.5 text-xs text-[var(--tessera-text-muted)] hover:border-[#7c5cf5]/50 hover:text-[var(--tessera-text)]"
            >
              {sug}
            </button>
          ))}
        </div>
      ) : null}

      {/* composer */}
      <div className="px-4 pb-2">
        <Composer t={t} />
        <p className="mt-1.5 text-center text-[0.65rem] text-[var(--tessera-text-muted)]">
          {t("disclaimer")}
        </p>
      </div>

      {/* console replay actions */}
      {isConsole ? (
        <div className="flex flex-wrap gap-2 border-t border-[var(--tessera-border)] px-4 py-2.5">
          <GhostAction icon={RefreshCcw} label={t("replaySession")} />
          <GhostAction icon={GitCompare} label={t("compareVersion")} />
          <GhostAction icon={Download} label={t("exportSession")} />
          <GhostAction icon={X} label={t("closeSession")} />
        </div>
      ) : null}

      {/* status bar */}
      <StatusBar t={t} isConsole={isConsole} data={data} />
    </div>
  );
}

function UserMessage({ t, time, text }: { t: T; time: string; text: string }) {
  return (
    <div className="flex flex-col items-end gap-1">
      <p className="text-[0.66rem] text-[var(--tessera-text-muted)]">
        {t("you")} · {time}
      </p>
      <div className="max-w-[78%] rounded-2xl rounded-tr-sm border border-[#7c5cf5]/35 bg-[#241c52] px-3.5 py-2.5 text-sm leading-relaxed text-[#e7e1ff]">
        {text}
      </div>
    </div>
  );
}

function AssistantMessage({
  t,
  isConsole,
  message,
}: { t: T; isConsole: boolean; message: Data["messages"][number] }) {
  return (
    <div className="flex gap-3">
      <span
        className={cn(
          "grid h-7 w-7 shrink-0 place-items-center rounded-full border",
          isConsole
            ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-300"
            : "border-[#7c5cf5]/40 bg-[#6d4aed]/15 text-[#b9a6ff]",
        )}
      >
        {isConsole ? <CheckCircle2 className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[0.66rem] text-[var(--tessera-text-muted)]">
          {t("assistant")} · {message.time}
          {isConsole && message.latency ? (
            <span className="text-[var(--tessera-text-muted)]"> · {message.latency}</span>
          ) : null}
        </p>
        <div className="mt-1.5 text-sm leading-relaxed text-[var(--tessera-text)]">
          {message.intro ? <p>{message.intro}</p> : null}
          {message.points ? (
            <ol className="mt-2 flex flex-col gap-1.5">
              {message.points.map((p, i) => (
                <li key={p.label} className="flex gap-2">
                  <span className="text-[var(--tessera-text-muted)]">{i + 1}.</span>
                  <span>
                    <span className="font-medium text-[#9fe3cf]">{p.label}</span>
                    <span className="text-[var(--tessera-text-muted)]"> : </span>
                    <span className="text-[var(--tessera-text)]">{p.body}</span>
                  </span>
                </li>
              ))}
            </ol>
          ) : null}
          {message.outro ? (
            <p className="mt-2 text-[var(--tessera-text-muted)]">{message.outro}</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function ChatAnswerMeta({ t, data }: { t: T; data: Data }) {
  return (
    <div className="ml-10 flex flex-col gap-3">
      <SourceChipRow t={t} sources={data.sources} />
      <div className="flex flex-wrap items-center gap-2">
        <Vote t={t} />
        <GhostAction icon={Download} label={t("exportResponse")} className="ml-auto" />
      </div>
    </div>
  );
}

function ConsoleAnswerMeta({ t, data }: { t: T; data: Data }) {
  return (
    <div className="ml-10 flex flex-col gap-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <CountChip icon={FileText} label={t("pill.sources")} n={data.sources.length} />
        <CountChip icon={Wrench} label={t("toolsLabel")} n={data.tools.length} />
        <CountChip icon={ShieldAlert} label={t("guardrailsLabel")} n={data.guardrails.length} />
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <GhostAction icon={ClipboardCheck} label={t("addToEval")} />
          <GhostAction icon={AlertTriangle} label={t("createIncident")} />
          <GhostAction icon={Download} label={t("exportResponse")} />
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Vote t={t} />
        <span className="ml-auto text-[0.7rem] text-[var(--tessera-text-muted)]">
          {data.messages.find((m) => m.role === "assistant")?.tokens}
        </span>
      </div>
    </div>
  );
}

function SourceChipRow({ t, sources }: { t: T; sources: Data["sources"] }) {
  return (
    <div>
      <p className="mb-1.5 text-[0.7rem] font-medium text-[#9fe3cf]">
        {t("pill.sources")} ({sources.length})
      </p>
      <div className="flex flex-wrap gap-2">
        {sources.map((src) => (
          <span
            key={src.title}
            className="flex max-w-[220px] items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1 text-[0.7rem] text-[var(--tessera-text-muted)]"
          >
            <FileText className="h-3.5 w-3.5 shrink-0 text-[#9fe3cf]" />
            <span className="truncate">{src.title}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function CountChip({ icon: I, label, n }: { icon: Icon; label: string; n: number }) {
  return (
    <span className="flex items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1 text-[0.7rem] text-[var(--tessera-text-muted)]">
      <I className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
      {label} ({n})
    </span>
  );
}

function Vote({ t }: { t: T }) {
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        className="flex items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1 text-[0.7rem] text-[var(--tessera-text-muted)] hover:text-emerald-300"
      >
        <ThumbsUp className="h-3.5 w-3.5" /> {t("useful")}
      </button>
      <button
        type="button"
        className="flex items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1 text-[0.7rem] text-[var(--tessera-text-muted)] hover:text-red-300"
      >
        <ThumbsDown className="h-3.5 w-3.5" /> {t("notUseful")}
      </button>
    </div>
  );
}

function Composer({ t }: { t: T }) {
  return (
    <div className="flex items-center gap-2 rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 py-2">
      <Mic className="h-4 w-4 shrink-0 text-[var(--tessera-text-muted)]" />
      <span className="min-w-0 flex-1 truncate text-sm text-[var(--tessera-text-muted)]">
        {t("composerPlaceholder")}
      </span>
      <button
        type="button"
        className={cn(
          "grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-[#7c5cf5]",
          ACCENT,
        )}
      >
        <SendHorizontal className="h-4 w-4" />
      </button>
    </div>
  );
}

function StatusBar({ t, isConsole, data }: { t: T; isConsole: boolean; data: Data }) {
  const s = data.session;
  return (
    <footer className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-[var(--tessera-border)] px-4 py-2 text-[0.66rem] text-[var(--tessera-text-muted)]">
      <span className="flex items-center gap-1.5">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
        {t("sessionActiveAt")} {s.started_at}
      </span>
      <span className="flex items-center gap-1.5 text-emerald-300">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> {t("live")}
      </span>
      {isConsole ? (
        <>
          <span>
            {t("rail.context")} {t("contextValue")}
          </span>
          <span>
            {t("pill.language")} {s.language}
          </span>
        </>
      ) : (
        <>
          <span>
            {t("pill.model")} {s.model}
          </span>
          <span>
            {t("pill.sources")}: {s.sources_snapshot}
          </span>
          <span>
            {t("pill.guardrails")}: {s.guardrails_version}
          </span>
        </>
      )}
    </footer>
  );
}

// ── chat right rail ───────────────────────────────────────────────────────────

function ChatRail({ t, data }: { t: T; data: Data }) {
  const c = data.context;
  const quickActions: { icon: Icon; label: string }[] = [
    { icon: MessageSquarePlus, label: t("qa.followUp") },
    { icon: FileText, label: t("qa.summary") },
    { icon: Maximize2, label: t("qa.openConsole") },
    { icon: AlertTriangle, label: t("qa.createIncident") },
    { icon: ClipboardCheck, label: t("qa.addEval") },
    { icon: Download, label: t("qa.exportSession") },
  ];
  return (
    <>
      <Card title={t("sessionContext")}>
        <div className="flex flex-col gap-2 text-xs">
          <KV label={t("ctx.user")} value={c.user} />
          <KV label={t("ctx.environment")} value={c.environment} />
          <KV label={t("ctx.objective")} value={c.objective} />
          <div className="flex items-start justify-between gap-2">
            <span className="text-[var(--tessera-text-muted)]">{t("ctx.tags")}</span>
            <div className="flex flex-wrap justify-end gap-1.5">
              {c.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-0.5 text-[0.66rem] text-[var(--tessera-text-muted)]"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>
      </Card>

      <Card title={`${t("sourcesUsed")} (${data.sources.length})`}>
        <SourceList sources={data.sources} />
      </Card>

      <Card title={t("quickActions")}>
        <ul className="flex flex-col gap-0.5">
          {quickActions.map((a) => (
            <li key={a.label}>
              <button
                type="button"
                className="flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-xs text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]"
              >
                <a.icon className="h-3.5 w-3.5 shrink-0 text-[#b9a6ff]" />
                {a.label}
              </button>
            </li>
          ))}
        </ul>
      </Card>

      <Card title={t("feedbackTitle")}>
        <p className="mb-2.5 text-[0.7rem] text-[var(--tessera-text-muted)]">
          {t("feedbackSubtitle")}
        </p>
        <div className="grid grid-cols-3 gap-2">
          <FeedbackButton icon={SmilePlus} label={t("fb.veryUseful")} tone="text-emerald-300" />
          <FeedbackButton icon={Smile} label={t("fb.useful")} tone="text-[#b9a6ff]" />
          <FeedbackButton
            icon={Meh}
            label={t("fb.neutral")}
            tone="text-[var(--tessera-text-muted)]"
          />
        </div>
        <button
          type="button"
          className="mt-2.5 flex w-full items-center justify-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] py-1.5 text-[0.72rem] text-[var(--tessera-text-muted)] hover:text-amber-300"
        >
          <Flag className="h-3.5 w-3.5" /> {t("reportProblem")}
        </button>
      </Card>
    </>
  );
}

function FeedbackButton({ icon: I, label, tone }: { icon: Icon; label: string; tone: string }) {
  return (
    <button
      type="button"
      className="flex flex-col items-center gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] py-2 text-[0.66rem] text-[var(--tessera-text-muted)] hover:border-[#7c5cf5]/40 hover:text-[var(--tessera-text)]"
    >
      <I className={cn("h-4 w-4", tone)} />
      {label}
    </button>
  );
}

// ── console right rail ────────────────────────────────────────────────────────

function ConsoleRail({ t, data }: { t: T; data: Data }) {
  const tabs = ["context", "sources", "tools", "guardrails"] as const;
  return (
    <>
      <div className="grid grid-cols-2 gap-2.5">
        {data.rail_kpis.map((k) => (
          <div
            key={k.key}
            className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5"
          >
            <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{t(`rail.${k.key}`)}</p>
            <p className="mt-1 text-base font-semibold text-emerald-300">{k.value}</p>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-0.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-0.5">
        {tabs.map((tb, i) => (
          <span
            key={tb}
            className={cn(
              "flex-1 rounded px-2 py-1.5 text-center text-[0.7rem] font-medium",
              i === 0 ? "bg-[#6d4aed]/20 text-[#cbbcff]" : "text-[var(--tessera-text-muted)]",
            )}
          >
            {t(`rail.tab.${tb}`)}
          </span>
        ))}
      </div>

      <Card title={t("qualityTitle")}>
        <div className="flex flex-col gap-2.5">
          {data.quality.map((q) => (
            <ScoreBar key={q.key} label={t(`quality.${q.key}`)} value={q.value} />
          ))}
        </div>
      </Card>

      <Card title={`${t("sourcesUsed")} (${data.sources.length})`}>
        <SourceList sources={data.sources} />
      </Card>

      <Card title={`${t("toolsCalled")} (${data.tools.length})`}>
        <ul className="flex flex-col gap-1.5">
          {data.tools.map((tool) => (
            <li
              key={tool.name}
              className="flex items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1.5 text-[0.72rem] text-[var(--tessera-text)]"
            >
              <Wrench className="h-3.5 w-3.5 shrink-0 text-[#b9a6ff]" />
              <span className="truncate font-mono">{tool.name}</span>
            </li>
          ))}
        </ul>
      </Card>

      <Card title={`${t("guardrailsTriggered")} (${data.guardrails.length})`}>
        <div className="flex flex-col gap-2">
          {data.guardrails.map((g) => (
            <div
              key={g.name}
              className="rounded-md border border-amber-500/25 bg-amber-500/10 p-2.5"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-1.5 text-[0.74rem] font-medium text-amber-200">
                  <ShieldAlert className="h-3.5 w-3.5" /> {g.name}
                </span>
                <span
                  className={cn(
                    "rounded-full border px-1.5 py-0.5 text-[0.58rem] font-semibold uppercase",
                    GUARD_BADGE[g.level],
                  )}
                >
                  {t("guardWarn")}
                </span>
              </div>
              <p className="mt-1 text-[0.68rem] text-[var(--tessera-text-muted)]">{g.detail}</p>
            </div>
          ))}
        </div>
      </Card>

      <Card title={t("traceTitle")}>
        <ul className="flex flex-col gap-2">
          {data.trace.map((step) => (
            <li key={step.key} className="flex items-center gap-2 text-[0.74rem]">
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
              <span className="text-[var(--tessera-text)]">{t(`trace.${step.key}`)}</span>
            </li>
          ))}
        </ul>
      </Card>

      <p className="px-1 text-[0.64rem] text-[var(--tessera-text-muted)]">
        {t("tenant")} {data.tenant} · {t("sessionShort")}: {data.session.id}
      </p>
    </>
  );
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const pct = Math.max(0, Math.min(100, value * 10));
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-[0.72rem]">
        <span className="text-[var(--tessera-text-muted)]">{label}</span>
        <span className="font-medium text-[var(--tessera-text)]">{value.toFixed(1)}/10</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-[var(--tessera-bg)]">
        <div className="h-full rounded-full bg-emerald-400/80" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

// ── shared atoms ──────────────────────────────────────────────────────────────

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <h3 className="mb-2.5 text-[0.78rem] font-semibold text-[var(--tessera-text)]">{title}</h3>
      {children}
    </div>
  );
}

function KV({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="shrink-0 text-[var(--tessera-text-muted)]">{label}</span>
      <span className="truncate text-[var(--tessera-text)]">{value}</span>
    </div>
  );
}

function SourceList({ sources }: { sources: Data["sources"] }) {
  return (
    <ul className="flex flex-col gap-1.5">
      {sources.map((src) => (
        <li
          key={src.title}
          className="flex items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1.5 text-[0.72rem] text-[var(--tessera-text)]"
        >
          <FileText className="h-3.5 w-3.5 shrink-0 text-[#9fe3cf]" />
          <span className="truncate">{src.title}</span>
        </li>
      ))}
    </ul>
  );
}

function GhostAction({
  icon: I,
  label,
  className,
}: { icon: Icon; label: string; className?: string }) {
  return (
    <button
      type="button"
      className={cn(
        "flex items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1 text-[0.7rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
        className,
      )}
    >
      <I className="h-3.5 w-3.5" /> {label}
    </button>
  );
}
