import { ArrowRight, Bot, User } from "lucide-react";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { auth } from "@/auth";
import { MessageContent } from "@/components/chat/message-content";
import { SessionDetailSchema } from "@/lib/api/schemas";
import { canReadSubjectData, operatorSurfaceForRole } from "@/lib/auth/roles";
import { backendHeaders, backendUrl } from "@/lib/server/backend";
import { OPERATOR_ASSERTION_HEADER, mintOperatorAssertion } from "@/lib/server/operator-assertion";

interface PageProps {
  params: Promise<{ locale: string; agentId: string; sessionId: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { locale, sessionId } = await params;
  const t = await getTranslations({ locale, namespace: "assistant" });
  return { title: `${t("sessionDetail.title")} ${sessionId}` };
}

// Per-turn agent accent: a conversation that spans agents reads as a hand-over.
const AGENT_ACCENT: Record<string, string> = {
  "support-client": "border-[#6d4aed]/40 bg-[#6d4aed]/15 text-[#b9a6ff]",
  onboarding: "border-cyan-500/40 bg-cyan-500/15 text-cyan-300",
  recouvrement: "border-amber-500/40 bg-amber-500/15 text-amber-300",
};
const accent = (id: string) =>
  AGENT_ACCENT[id] ?? "border-slate-500/40 bg-slate-500/15 text-slate-300";

/**
 * Load one conversation's turn-by-turn detail — as a VERIFIED operator.
 *
 * Audit 2026-07-12, **P1 F-4**. This is a server component, so it calls the agent directly
 * and used to send only the service bearer — which says the call came from our frontend and
 * never says who asked. The route is subject-scoped (every turn carries the customer's
 * question and the agent's answer), so the agent now demands the signed operator assertion,
 * and this page must mint it from the session it already has.
 *
 * Returns a discriminated result, not `null`, because the old `null` collapsed two very
 * different truths into one screen: "there is no such conversation" and "you may not read
 * it". Gating the endpoint without fixing this caller would have traded a security hole for
 * a lie — an anonymous visitor would have been told the conversation was empty.
 */
type DetailResult =
  | { kind: "ok"; data: ReturnType<typeof SessionDetailSchema.parse> }
  | { kind: "denied" }
  | { kind: "empty" };

async function loadDetail(conversationId: string): Promise<DetailResult> {
  const session = await auth();
  const role = session?.user?.role ?? null;
  if (!canReadSubjectData(role)) return { kind: "denied" };

  const surface = operatorSurfaceForRole(role);
  const assertion = surface
    ? mintOperatorAssertion(session?.user?.name ?? String(role), String(role), surface)
    : null;
  if (!assertion) return { kind: "denied" };

  try {
    const q = `?conversation_id=${encodeURIComponent(conversationId)}`;
    const res = await fetch(`${backendUrl()}/observability/session-detail${q}`, {
      cache: "no-store",
      headers: backendHeaders({
        Accept: "application/json",
        [OPERATOR_ASSERTION_HEADER]: assertion,
      }),
    });
    if (res.status === 401 || res.status === 403) return { kind: "denied" };
    if (!res.ok) return { kind: "empty" };
    return { kind: "ok", data: SessionDetailSchema.parse(await res.json()) };
  } catch {
    return { kind: "empty" };
  }
}

export default async function SessionDetailPage({ params }: PageProps) {
  const { locale, sessionId } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "assistant" });
  const result = await loadDetail(sessionId);

  // "You may not see this" is never rendered as "there is nothing to see" (audit F-4).
  if (result.kind === "denied") {
    return (
      <div className="flex min-h-[40vh] flex-col items-center justify-center gap-2 text-center">
        <p className="text-sm font-medium text-[var(--tessera-text)]">
          {t("sessionDetail.denied")}
        </p>
        <p className="max-w-md text-sm text-[var(--tessera-text-muted)]">
          {t("sessionDetail.deniedBody")}
        </p>
      </div>
    );
  }

  const data = result.kind === "ok" ? result.data : null;

  if (!data?.available || !data.turns?.length) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        {t("sessionDetail.empty")}
      </div>
    );
  }

  const agents = data.agents ?? [];
  const handoffs = data.handoffs ?? [];

  return (
    <div className="flex flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      {/* Header: conversation + involved agents */}
      <section className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4">
        <p className="truncate text-[0.95rem] font-semibold">{data.title}</p>
        <p className="mt-1 font-mono text-[0.66rem] text-[var(--tessera-text-muted)]">
          {data.conversation_id}
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {agents.map((a) => (
            <span
              key={a.id}
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[0.7rem] ${accent(a.id)}`}
            >
              <Bot className="h-3.5 w-3.5" /> {a.name}
            </span>
          ))}
          {data.spans_agents ? (
            <span className="rounded-full border border-emerald-500/40 bg-emerald-500/15 px-2.5 py-1 text-[0.7rem] text-emerald-300">
              {t("sessionDetail.spansAgents")}
            </span>
          ) : null}
        </div>
      </section>

      {/* Handoff events (S1, distinct from human escalation) */}
      {handoffs.map((h, i) => (
        <div
          key={`${h.from}-${h.to}-${i}`}
          className="flex flex-wrap items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-2.5 text-[0.78rem]"
        >
          <span className="font-medium text-emerald-300">{t("sessionDetail.handoff")}</span>
          <span className="inline-flex items-center gap-1.5">
            {h.from_name} <ArrowRight className="h-3.5 w-3.5" /> {h.to_name}
          </span>
          <span className="text-[var(--tessera-text-muted)]">· {h.reason}</span>
        </div>
      ))}

      {/* CT-01 Conversation Timeline Rail (internal code): turns in order, each
          attributed to the agent that handled it (per-turn agent_id). */}
      <p className="mt-1 text-[0.66rem] font-semibold uppercase tracking-wide text-[var(--tessera-text-muted)]">
        Chronologie de la session
      </p>
      {/* Turns, each attributed to the agent that handled it */}
      <ol className="flex flex-col gap-2.5">
        {data.turns.map((turn) => (
          <li
            key={turn.turn}
            className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3.5"
          >
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="text-[0.66rem] text-[var(--tessera-text-muted)]">
                {t("sessionDetail.turn")} {turn.turn} · {turn.time}
              </span>
              <span
                className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[0.66rem] ${accent(turn.agent_id)}`}
                title={
                  turn.routing_reason
                    ? `${t("sessionDetail.routedBy")}: ${turn.routing_reason}`
                    : undefined
                }
              >
                <Bot className="h-3 w-3" /> {turn.agent_name}
              </span>
            </div>
            {turn.routing_reason ? (
              <p className="mb-1.5 text-[0.62rem] text-[var(--tessera-text-muted)]">
                {t("sessionDetail.routedBy")}: {turn.routing_reason}
              </p>
            ) : null}
            {/* Client-faithful, read-only rendering: the customer's exact view
                  (Markdown for the assistant reply), reusing the shared
                  <MessageContent>. No composer/edit, no operator debug here. */}
            <div className="flex gap-2">
              <User className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)]" />
              <div className="min-w-0 flex-1">
                <MessageContent speaker="user" content={turn.question} />
              </div>
            </div>
            <div className="mt-2 flex gap-2 text-[var(--tessera-text-muted)]">
              <Bot className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <div className="min-w-0 flex-1">
                <MessageContent speaker="assistant" content={turn.answer} />
              </div>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
