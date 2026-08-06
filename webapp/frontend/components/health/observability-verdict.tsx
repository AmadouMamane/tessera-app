"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Eye, EyeOff, XCircle } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";

import { observedAt } from "@/components/health/observability-shared";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchComponents } from "@/lib/api/client";

const POLL_MS = 15_000;

/**
 * The page's verdict, in one sentence.
 *
 * Twenty rows is not an answer; it is the raw material for one, and it makes the reader do the
 * assembling. The sentence below is what they were assembling: *"I observe 12 of 12 components;
 * 2 signals cannot be read."*
 *
 * Two counts, never one. "18/20 ok" collapses the distinction the whole surface exists to carry:
 * a component that is DOWN and a component nobody could LOOK AT are different sentences with
 * different repairs, and a single ratio hides which of them is on the screen. So failures and
 * blind spots are counted separately and the headline names whichever is worse — a failure
 * outranks a blind spot, because "something is down" is the actionable one.
 */
export function ObservabilityVerdict() {
  const t = useTranslations("health.verdict");
  const format = useFormatter();

  const query = useQuery({
    queryKey: ["components"],
    queryFn: ({ signal }) => fetchComponents(signal),
    refetchInterval: POLL_MS,
  });

  if (query.isPending) {
    return (
      <Card>
        <CardContent className="py-3">
          <Skeleton className="h-8 w-2/3" />
        </CardContent>
      </Card>
    );
  }

  // A failed READ of the verdict is not a clear verdict. It is the one state this card must
  // never render as reassurance, and the reason it gets its own branch rather than an `?? 0`.
  if (query.error || !query.data) {
    return (
      <Card className="border-[var(--tessera-fg-warning)]/40">
        <CardContent className="flex items-center gap-2.5 py-3">
          <EyeOff className="h-5 w-5 shrink-0 text-[var(--tessera-fg-warning)]" />
          <p className="text-sm font-medium text-[var(--foreground)]">{t("unreadable")}</p>
        </CardContent>
      </Card>
    );
  }

  const { counts, verdict, observed_at, chain } = query.data;
  const Icon = verdict === "clear" ? CheckCircle2 : verdict === "fail" ? XCircle : AlertTriangle;
  const accent =
    verdict === "clear"
      ? "text-[var(--tessera-fg-success)]"
      : verdict === "fail"
        ? "text-[var(--tessera-fg-danger)]"
        : "text-[var(--tessera-fg-warning)]";
  // Signals that no longer reach a store. Counted from the chain rather than from the component
  // tally, because they are not the same number: three dead nodes on one severed branch cost
  // ONE signal, and the operator acts on the signal.
  const signals = Object.entries(chain.signals);
  const lostSignals = signals.filter(([, state]) => state === "lost").map(([name]) => name);
  const unknownSignals = signals
    .filter(([, state]) => state === "cannot_say")
    .map(([name]) => name);

  return (
    <Card className={verdict === "clear" ? undefined : "border-current/30"}>
      <CardContent className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3">
        <Icon className={`h-5 w-5 shrink-0 ${accent}`} />
        <p className="min-w-0 flex-1 text-sm leading-snug text-[var(--foreground)]">
          <span className="font-medium">
            {t("observing", { ok: counts.stack_ok, total: counts.stack_total })}
          </span>
          {/* Every clause below is scoped to THE STACK, like the one it follows. The
              preconditions are a different question — "can this process serve a turn?" — and
              they get their own clause rather than being folded into these counts. */}
          {counts.stack_fail > 0 ? (
            <span className="text-[var(--tessera-fg-danger)]">
              {" · "}
              {t("down", { n: counts.stack_fail })}
            </span>
          ) : null}
          {counts.stack_blind > 0 ? (
            <span className="text-[var(--tessera-fg-warning)]">
              {" · "}
              {t("blind", { n: counts.stack_blind })}
            </span>
          ) : null}
          {counts.stack_fail === 0 && counts.stack_blind === 0 ? (
            <span className="text-[var(--muted-foreground)]">
              {" · "}
              {t("allClear")}
            </span>
          ) : null}
          {counts.precondition_ok < counts.precondition_total ? (
            <span className="text-[var(--tessera-fg-danger)]">
              {" · "}
              {t("preconditions", {
                bad: counts.precondition_total - counts.precondition_ok,
                total: counts.precondition_total,
              })}
            </span>
          ) : null}
        </p>
        <div className="flex shrink-0 flex-wrap items-center gap-1.5">
          {lostSignals.length > 0 ? (
            <Badge tone="danger">
              {t("signalsLost", { list: lostSignals.map((s) => t(`signal.${s}`)).join(", ") })}
            </Badge>
          ) : null}
          {unknownSignals.length > 0 ? (
            <Badge tone="warning">
              {t("signalsUnknown", {
                list: unknownSignals.map((s) => t(`signal.${s}`)).join(", "),
              })}
            </Badge>
          ) : null}
          {/* The observation instant, not the render instant: the probe is cached, and a verdict
              that cannot say when it last looked invites the reader to assume "now". */}
          <span className="flex items-center gap-1 text-[0.66rem] text-[var(--muted-foreground)]">
            <Eye className="h-3 w-3" />
            {t("checked", { when: format.relativeTime(observedAt(observed_at)) })}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
