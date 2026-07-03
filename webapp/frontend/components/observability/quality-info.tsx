"use client";

import { useTranslations } from "next-intl";

import { MetricInfo } from "@/components/cockpit/metric-info";

/**
 * QInfo — the Qualité-IA per-metric ⓘ affordance.
 *
 * A thin wrapper over {@link MetricInfo} that reads a metric's explainer from
 * `quality.explain.<k>.{what,how,source}` so every KPI tile and panel title on
 * the Qualité-IA sub-tabs (Signaux, Runs, Cas échoués, Modèles, Calibration)
 * can carry a grounded "what does this number mean?" popover with the SAME
 * source of truth the overview already uses. `source` is optional and guarded
 * with `te.has` so a metric without a distinct source line renders cleanly.
 *
 * Shared (rather than re-declared per sub-component) to avoid a circular import:
 * the sub-tab components are imported BY the dashboard, so they cannot import a
 * helper defined there.
 */
export function QInfo({
  title,
  k,
  className,
}: {
  /** The metric/panel name, shown as the popover heading. */
  title: string;
  /** The `quality.explain` key holding `.what` / `.how` / optional `.source`. */
  k: string;
  className?: string;
}) {
  const te = useTranslations("quality.explain");
  return (
    <MetricInfo
      title={title}
      what={te(`${k}.what`)}
      how={te(`${k}.how`)}
      source={te.has(`${k}.source`) ? te(`${k}.source`) : undefined}
      className={className}
    />
  );
}
