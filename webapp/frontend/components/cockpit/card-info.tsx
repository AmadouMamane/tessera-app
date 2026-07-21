"use client";

import { useTranslations } from "next-intl";

import { MetricInfo } from "./metric-info";

/**
 * CardInfo — a reusable ⓘ pastille for a card/metric/section title.
 *
 * It reads its plain-language explanation from `<ns>.explain.<k>.{what,how,source}`,
 * the same shape the per-page `SectionInfo` helpers use (overview, état-à-date).
 * Factored out here so every AGENT and cockpit surface can explain its cards from
 * one place instead of re-declaring the helper file by file.
 *
 * `what` is always rendered (the definition); `how` and `source` render only when
 * the key exists (guarded via `.has`), so a card can carry just a definition
 * without inventing a formula or a data source it does not have — the honest-empty
 * discipline the reference pages already follow.
 *
 * The namespace is passed as a string (messages are not statically typed here), so
 * a single component serves every `explain` sub-tree without a literal per call site.
 */
export function CardInfo({
  ns,
  k,
  title,
  className,
}: {
  /** i18n namespace holding an `explain` sub-tree (e.g. "agentPrompts"). */
  ns: string;
  /** Key under `<ns>.explain` (e.g. "versions"). */
  k: string;
  /** The card/metric name, shown as the popover heading. */
  title: string;
  className?: string;
}) {
  const te = useTranslations(`${ns}.explain`);
  // Honest-empty: a card whose key has no `what` gets no pastille rather than a
  // raw key path on screen. This makes the helper safe to sprinkle on payload-
  // driven metrics (KPI tiles keyed by a runtime `kpi.key`) — a metric earns its
  // ⓘ only once an explanation is authored for it.
  if (!te.has(`${k}.what`)) return null;
  return (
    <MetricInfo
      title={title}
      what={te(`${k}.what`)}
      how={te.has(`${k}.how`) ? te(`${k}.how`) : undefined}
      source={te.has(`${k}.source`) ? te(`${k}.source`) : undefined}
      className={className}
    />
  );
}
