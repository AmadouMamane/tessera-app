"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, ShieldCheck, TriangleAlert } from "lucide-react";
import { useTranslations } from "next-intl";
import type { Route } from "next";

import { Link } from "@/i18n/navigation";
import { fetchSLO } from "@/lib/api/client";

const METRIC_LABEL: Record<string, string> = {
  faithfulness: "Fidélité",
  relevance: "Pertinence",
  availability: "Disponibilité",
  latency: "Latence",
};

/**
 * P2 — Surveiller signal hero. Leads the page with the **named breached signal**
 * (the real SLO from `/observability/slo`: metric, observed rate vs threshold,
 * burn rate) + a direct remediation link → AGIR Incidents. Honest: when no SLO is
 * breaching it shows a green "respecté" state; nothing is fabricated.
 */
export function SignalBreachHero() {
  const t = useTranslations("signalHero");
  const { data } = useQuery({
    queryKey: ["slo-hero"],
    queryFn: ({ signal }) => fetchSLO(signal),
    staleTime: 30_000,
  });

  if (!data) return null;
  const pct = (n: number) => `${(n * 100).toFixed(1).replace(".", ",")} %`;
  const metric = METRIC_LABEL[data.metric] ?? data.metric;

  if (!data.breaching) {
    return (
      <section className="flex items-center gap-3 rounded-lg border border-[#3fb37f]/40 bg-[#10231b] px-3.5 py-2.5">
        <ShieldCheck className="h-5 w-5 shrink-0 text-[#7fe3b3]" />
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            {t("title")}
          </p>
          <p className="text-[0.92rem] font-semibold text-[#7fe3b3]">
            {t("ok", { metric, rate: pct(data.good_rate), threshold: pct(data.threshold) })}
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[#e0566f]/50 bg-[#2a1320] px-3.5 py-2.5">
      <div className="flex min-w-0 items-center gap-3">
        <TriangleAlert className="h-5 w-5 shrink-0 text-[#ff9bb0]" />
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            {t("title")}
          </p>
          <p className="text-[0.95rem] font-semibold text-[#ff9bb0]">
            {t("breached", { metric, rate: pct(data.good_rate), threshold: pct(data.threshold) })}
          </p>
          <p className="mt-0.5 inline-flex items-center gap-1.5 text-[11px] text-[var(--tessera-text-muted)]">
            <Activity className="h-3 w-3" />
            {t("burn", { x: data.burn_rate.toFixed(1).replace(".", ","), bad: data.n_bad, n: data.n })}
          </p>
        </div>
      </div>
      <Link
        href={"/agir/incidents-playbooks" as Route}
        className="shrink-0 rounded-md border border-[#e0566f]/60 bg-[#e0566f]/15 px-2.5 py-1.5 text-[11px] font-medium text-[#ff9bb0] transition-colors hover:bg-[#e0566f]/25 hover:text-white"
      >
        {t("remediate")} →
      </Link>
    </section>
  );
}
