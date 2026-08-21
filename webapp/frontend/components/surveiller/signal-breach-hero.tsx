"use client";

import { useQuery } from "@tanstack/react-query";
import { EyeOff, Flame, ShieldCheck, TriangleAlert } from "lucide-react";
import type { Route } from "next";
import { useTranslations } from "next-intl";

import { useDecimalFormat, usePercentFormat } from "@/lib/format-number";
import { useWindowStore } from "@/lib/stores/window-store";
import { useSearchParams } from "next/navigation";

import { AlertRibbon, type RibbonVariant } from "@/components/cockpit/alert-ribbon";
import { Link } from "@/i18n/navigation";
import { AGENT_SCOPE_PARAM, parseAgentScope } from "@/lib/agent-scope";
import { fetchSLO } from "@/lib/api/client";

/**
 * A RATE IS NOT PUBLISHED UNTIL THE SAMPLE CAN CARRY ONE.
 *
 * Below this many judged responses, one observation moves the percentage by a full point or
 * more — so "0,0 %" is a count wearing a percent sign, and its decimal is noise. The operator
 * saw the consequence on 2026-08-21: over seven days the fleet had **one** judged response, it
 * scored 0.10 against a 0.70 bar, and the band led with "0,0 % des réponses au niveau exigé" —
 * literally true (0 of 1) and read as a systemic collapse. The sample was on screen, in the
 * second line, in smaller type.
 *
 * 100 is not a taste: it is the point at which one response is worth less than one percentage
 * point. Under it the headline states the COUNTS, which cannot be misread; over it the rate is
 * meaningful and leads, with its sample still beside it in the burn line.
 */
const MIN_N_FOR_A_RATE = 100;

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
  // The dashboard below asks the SAME question under the key `["slo", asOf, scope, period]`,
  // and in live mode its `asOf` is `null` and it passes `undefined` down — byte-identical to
  // this call. The only thing that made them two HTTP requests was the private key `slo-hero`.
  // Sharing the key merges the observers: one request, one cached answer, and no way for the
  // ribbon and the gauge to end up quoting two different reads of one endpoint.
  //
  // The `null` is deliberate and is what keeps this ribbon LIVE: when the operator scrubs to a
  // past instant the dashboard's key moves to that instant while this one does not, so the two
  // separate again exactly when they are meant to mean different things.
  const { data } = useQuery({
    queryKey: ["slo", null, scope, period],
    queryFn: ({ signal }) => fetchSLO(signal, undefined, scope, period),
    staleTime: 30_000,
  });

  // Hooks before the early return: a conditional hook is a React error, and `!data` is exactly
  // the branch that would skip them.
  const percent = usePercentFormat(1);
  const decimal = useDecimalFormat(1);

  if (!data) return null;
  const pct = (n: number) => percent(n);
  // Tight (no space before %) for the gauge marker flag: a trailing " %" widens the box on the
  // right and shifts the visible digits left of the vertical marker. The space is STRIPPED from
  // the formatted result rather than never added: which whitespace to remove is a fact about
  // the locale — French and German put a narrow no-break space there, English nothing — and
  // formatting first is the only way to know what is present.
  const pctTight = (n: number) => percent(n).replace(/[\s\u202f\u00a0]/g, "");
  const metricKey = METRIC_KEY[data.metric as keyof typeof METRIC_KEY];
  const metric = metricKey ? t(metricKey) : data.metric;

  // NOTHING MEASURED is not a target met — and it is not a 0 % one either.
  //
  // `compute_slo` is honest on an empty window: every field is zero and `breaching` is false
  // ("no evidence of a breach"). The fact carrying the truth is `n`. This component read the
  // other two and printed the payload's two most misleading halves side by side: "0,0 % of
  // responses at the required level" — which reads as a catastrophe — next to "95,0 % target
  // met", which reads as all-clear. Both false, in opposite directions, from the same absence.
  //
  // It was seen in production the minute the agent was restarted: live scores are a RING
  // BUFFER, so every deployment starts with an empty window — the worst possible moment for a
  // banner to reassure. The dashboard's own tile, reading the SAME endpoint, already guarded
  // this (`n > 0 ? … : null`); the ribbon above it did not, so one screen said "—" and "target
  // met" at once. A witness that cannot see may never report "ok" (ADR 0026).
  if (data.n === 0) {
    const unmeasured = t("unmeasured", { metric, threshold: pct(data.target) });
    if (variant === "slim") {
      return <AlertRibbon variant="slim" severity="info" icon={EyeOff} title={unmeasured} />;
    }
    // No gauge: a needle at zero over nothing observed is the same fabricated number in a
    // second notation.
    return (
      <AlertRibbon
        variant="gauge"
        severity="info"
        icon={EyeOff}
        eyebrow={t("title")}
        title={unmeasured}
      />
    );
  }

  // Enough judged responses for a rate to mean something? The two branches below differ only
  // in what LEADS: a percentage, or the counts it was computed from.
  const rateIsPublishable = data.n >= MIN_N_FOR_A_RATE;

  if (!data.breaching) {
    const okTitle = rateIsPublishable
      ? t("okShort", { metric, rate: pct(data.good_rate), threshold: pct(data.target) })
      : t("okCount", {
          metric,
          good: data.n_good,
          n: data.n,
          threshold: pct(data.target),
        });
    if (variant === "slim") {
      return <AlertRibbon variant="slim" severity="ok" icon={ShieldCheck} title={okTitle} />;
    }
    return (
      <AlertRibbon
        variant="gauge"
        severity="ok"
        icon={ShieldCheck}
        eyebrow={t("title")}
        title={okTitle}
        // A needle is a percentage drawn instead of written, so it inherits the same rule: on
        // too small a sample it is the fabricated precision again, in a second notation. This
        // is the reasoning already committed for `n === 0`, applied one step further along.
        gauge={
          rateIsPublishable
            ? {
                value: data.good_rate,
                threshold: data.target,
                thresholdLabel: pctTight(data.target),
              }
            : undefined
        }
      />
    );
  }

  const title = rateIsPublishable
    ? t("breachedShort", { metric, rate: pct(data.good_rate), threshold: pct(data.target) })
    : t("breachedCount", {
        metric,
        good: data.n_good,
        n: data.n,
        threshold: pct(data.target),
      });
  const burn = t("burn", {
    x: decimal(data.burn_rate),
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
      // The ribbon falls back to `meta` when there is no gauge, so the burn line — which
      // carries the SAMPLE — survives the needle's removal instead of going with it.
      meta={
        <span className="inline-flex items-center gap-1.5 tabular-nums">
          <Flame className="h-3 w-3 shrink-0 text-[var(--tessera-fg-danger)]" aria-hidden />
          {burn}
        </span>
      }
      gauge={
        // Same rule as the green band and as `n === 0`: a needle is a percentage drawn rather
        // than written, so too small a sample forbids it in either notation. The band keeps its
        // red severity, its icon and the burn line — the alarm survives; only the false
        // precision goes.
        rateIsPublishable
          ? {
              value: data.good_rate,
              threshold: data.target,
              thresholdLabel: pctTight(data.target),
              caption: (
                <span className="inline-flex items-center gap-1.5">
                  <Flame className="h-3 w-3 shrink-0 text-[var(--tessera-fg-danger)]" aria-hidden />
                  {burn}
                </span>
              ),
            }
          : undefined
      }
      action={remediate}
    />
  );
}
