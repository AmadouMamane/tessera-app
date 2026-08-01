"use client";

import { useQuery } from "@tanstack/react-query";
import { Flame, ShieldCheck, TriangleAlert } from "lucide-react";
import type { Route } from "next";
import { useTranslations } from "next-intl";

import { useWindowStore } from "@/lib/stores/window-store";
import { useSearchParams } from "next/navigation";

import { AlertRibbon, type RibbonVariant } from "@/components/cockpit/alert-ribbon";
import { Link } from "@/i18n/navigation";
import { AGENT_SCOPE_PARAM, parseAgentScope } from "@/lib/agent-scope";
import { fetchSLO } from "@/lib/api/client";

const METRIC_KEY = {
  faithfulness: "metric.faithfulness",
  relevance: "metric.relevance",
  availability: "metric.availability",
  latency: "metric.latency",
} as const;

/**
 * P2 — Surveiller signal hero, rendered as the shared premium {@link AlertRibbon}:
 * leads the page with the **named breached signal** (the real SLO from
 * `/observability/slo`: metric, observed rate vs threshold, burn rate) + a direct
 * remediation link → AGIR Incidents. Honest: when no SLO is breaching it shows the
 * quiet green "respecté" state; nothing is fabricated. The redundant "SLO franchi ·"
 * prefix is dropped — the eyebrow already names the category.
 *
 * `variant` chooses the presentation (default `gauge`): `gauge` = band + budget
 * gauge; `slim` = a one-line status line.
 */
export function SignalBreachHero({
  variant = "gauge",
  orgWide = false,
}: {
  variant?: RibbonVariant;
  /** Force the fleet (org) SLO, ignoring ?agent=. Set on org-posture pages
   * (compliance / reliability / improvement) whose body is org-wide, so the hero
   * never reads one agent's SLO over an org dashboard. */
  orgWide?: boolean;
}) {
  const t = useTranslations("signalHero");
  // The hero leads the page with the SLO; under an agent scope it reads THAT agent's
  // own SLO (same ?agent= filter the cards use), so the headline never disagrees with
  // the per-agent KPI grid below it — unless `orgWide` pins it to the fleet SLO.
  const searchParams = useSearchParams();
  const scope = orgWide ? "all" : parseAgentScope(searchParams.get(AGENT_SCOPE_PARAM));
  // …and under the same PERIOD, for exactly the same reason. The agent scope was wired here
  // and the window was not, so on 2026-08-01 — the day the period first reached the data —
  // this ribbon announced "Fidélité 73,1 %, 18 réponses sur 67 sous l'objectif" directly above
  // a table reading "100 %, 1/1 conformes". Both were correct about different weeks, which is
  // the worst way for two numbers to disagree: neither looks wrong.
  const period = useWindowStore((s) => s.period);
  const { data } = useQuery({
    queryKey: ["slo-hero", scope, period],
    queryFn: ({ signal }) => fetchSLO(signal, undefined, scope, period),
    staleTime: 30_000,
  });

  if (!data) return null;
  const pct = (n: number) => `${(n * 100).toFixed(1).replace(".", ",")} %`;
  // Tight (no space before %) for the gauge marker flag: a trailing " %" widens the
  // box on the right and shifts the visible digits left of the vertical marker.
  const pctTight = (n: number) => `${(n * 100).toFixed(1).replace(".", ",")}%`;
  const metricKey = METRIC_KEY[data.metric as keyof typeof METRIC_KEY];
  const metric = metricKey ? t(metricKey) : data.metric;

  if (!data.breaching) {
    const okTitle = t("okShort", {
      metric,
      rate: pct(data.good_rate),
      threshold: pct(data.target),
    });
    if (variant === "slim") {
      return (
        <AlertRibbon
          variant="slim"
          severity="ok"
          icon={ShieldCheck}
          eyebrow={t("title")}
          title={okTitle}
        />
      );
    }
    return (
      <AlertRibbon
        variant="gauge"
        severity="ok"
        icon={ShieldCheck}
        eyebrow={t("title")}
        title={okTitle}
        gauge={{
          value: data.good_rate,
          threshold: data.target,
          thresholdLabel: pctTight(data.target),
        }}
      />
    );
  }

  const title = t("breachedShort", {
    metric,
    rate: pct(data.good_rate),
    threshold: pct(data.target),
  });
  const burn = t("burn", {
    x: data.burn_rate.toFixed(1).replace(".", ","),
    bad: data.n_bad,
    n: data.n,
  });
  const remediate = (
    <Link
      href={"/agir/incidents-playbooks" as Route}
      className="inline-flex h-7 shrink-0 items-center gap-1.5 rounded-md border border-[#e0566f]/55 bg-[#e0566f]/15 px-3 text-[11px] font-medium text-[var(--tessera-fg-danger)] transition-colors hover:bg-[#e0566f]/25 hover:text-[var(--tessera-text-strong)]"
    >
      {t("remediate")} →
    </Link>
  );

  if (variant === "slim") {
    return (
      <AlertRibbon
        variant="slim"
        severity="critical"
        icon={TriangleAlert}
        eyebrow={t("title")}
        title={title}
        meta={
          <span className="inline-flex items-center gap-1.5 tabular-nums">
            <Flame className="h-3 w-3 shrink-0 text-[var(--tessera-fg-danger)]" aria-hidden />
            {burn}
          </span>
        }
        action={remediate}
      />
    );
  }

  return (
    <AlertRibbon
      variant="gauge"
      pulse
      pulseStopLabel={t("stopPulse")}
      severity="critical"
      icon={TriangleAlert}
      eyebrow={t("title")}
      title={title}
      gauge={{
        value: data.good_rate,
        threshold: data.target,
        thresholdLabel: pctTight(data.target),
        caption: (
          <span className="inline-flex items-center gap-1.5">
            <Flame className="h-3 w-3 shrink-0 text-[var(--tessera-fg-danger)]" aria-hidden />
            {burn}
          </span>
        ),
      }}
      action={remediate}
    />
  );
}
