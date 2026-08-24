"use client";

import { Brain } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";

import type { UnderstandingSummary } from "@/lib/api/schemas";

/**
 * The layer-1 understanding plane on SCREEN (ADR 0053, ADR 0017 §A5.3): over the recent
 * classified turns, how often the model and the word lists agreed, every failure NAMED
 * by kind, the model's median latency, the last classified turn's date, and whether the
 * model decides (active) or observes (shadow). COUNTS only — this ruler never shares a
 * denominator with the business signals beside it, so no percentage may appear here.
 * `null` data means the agent has no classified turns: the card renders nothing rather
 * than an empty score.
 */
export function UnderstandingCard({ data }: { data: UnderstandingSummary | null }) {
  const t = useTranslations("agentMetier.understanding");
  const format = useFormatter();
  if (!data || data.observed === 0) return null;

  const failureCount = Object.values(data.failures).reduce((total, n) => total + n, 0);
  const failureDetail = Object.entries(data.failures)
    .sort(([, a], [, b]) => b - a)
    .map(([kind, n]) => `${t.has(`kind.${kind}`) ? t(`kind.${kind}`) : kind} ${n}`)
    .join(" · ");
  const latestAt = data.latest_at ? new Date(data.latest_at) : null;

  return (
    <section
      aria-label={t("title")}
      className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-4 py-3"
    >
      <div className="flex flex-wrap items-baseline gap-x-2">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold">
          <Brain className="h-4 w-4 shrink-0 text-[var(--tessera-text-muted)]" aria-hidden />
          {t("title")}
        </h3>
        <span className="text-xs text-[var(--tessera-text-muted)]">
          {data.latest_mode === "active" ? t("modeActive") : t("modeShadow")}
          {data.latest_model ? ` · ${data.latest_model}` : null}
        </span>
      </div>
      <p className="mt-1 text-xs text-[var(--tessera-text-muted)]">{t("subtitle")}</p>
      <ul className="mt-2 flex flex-col gap-1 text-sm">
        <li>
          {t("population", { observed: data.observed })}{" "}
          {t("agreement", { agree: data.agree, disagree: data.disagree })}
        </li>
        <li className="text-[var(--tessera-text-muted)]">
          {failureCount > 0
            ? t("failures", { count: failureCount, detail: failureDetail })
            : t("noFailures")}
          {data.latency_ms_p50 != null
            ? ` · ${t("latency", { seconds: format.number(data.latency_ms_p50 / 1000, { maximumFractionDigits: 1 }) })}`
            : null}
        </li>
        {latestAt ? (
          <li className="text-xs text-[var(--tessera-text-muted)]">
            {t("freshness", {
              date: format.dateTime(latestAt, { dateStyle: "medium", timeStyle: "short" }),
            })}
          </li>
        ) : null}
      </ul>
    </section>
  );
}
