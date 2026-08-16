"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Boxes, Home, SearchCheck, ShieldAlert } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { DetailDrawer } from "@/components/cockpit/detail-drawer";
import { ComponentTimeline } from "@/components/health/component-timeline";
import {
  humanSeconds,
  observedAt,
  relativeNow,
  resolveLink,
  stateTone,
  verdictTone,
} from "@/components/health/observability-shared";
import { Badge } from "@/components/ui/badge";
import { fetchComponentHistory } from "@/lib/api/client";
import type { ComponentCheck, ComponentsResponse } from "@/lib/api/schemas";
import { usePercentFormat } from "@/lib/format-number";

/**
 * One component, interrogated in full — the drawer behind every table row.
 *
 * The table's cells are the translated summary; this is the evidence view, so the machine's
 * words appear VERBATIM (an errno paraphrased is an errno lost), the chain edges show their
 * `declared_in` citations in the open rather than behind a hover, and the component's own
 * slice of the history is drawn with the same timeline the page uses. Nothing here is a second
 * derivation: capabilities come from the payload's `consequences`, edges from its `chain`, the
 * timeline from the same `component-history` read the time zone polls.
 */
export function ComponentDrawer({
  component,
  data,
  onClose,
}: {
  component: ComponentCheck;
  data: ComponentsResponse;
  onClose: () => void;
}) {
  const pctFmt = usePercentFormat(1);
  const t = useTranslations("health.drawer");
  const tc = useTranslations("health.components");
  const tq = useTranslations("health.consequences");
  const format = useFormatter();

  // The same query key as the time zone: the drawer rides the cached answer and never adds a
  // second polling loop for the same file.
  const history = useQuery({
    queryKey: ["component-history", 1],
    queryFn: ({ signal }) => fetchComponentHistory(1, signal),
    staleTime: 30_000,
  });

  const tone = verdictTone(component.verdict);
  const dependents = data.consequences.filter((row) => row.needs.includes(component.name));
  const edges = data.chain.edges.filter(
    (edge) => edge.source === component.name || edge.target === component.name,
  );
  const link = resolveLink(data.links, component.name);
  const availability = history.data?.availability.find((row) => row.component === component.name);
  const role = tc.has(`role.${component.name}`) ? tc(`role.${component.name}`) : component.role;

  return (
    <DetailDrawer
      title={component.name}
      subtitle={role || t(`group.${component.group}`)}
      icon={<Boxes className="h-4 w-4" />}
      onClose={onClose}
      testId="component-drawer"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={tone === "neutral" ? "neutral" : tone}>
          {tc(`state.${component.verdict}`)}
        </Badge>
        <span className="text-[0.66rem] text-[var(--muted-foreground)]">
          {t(`group.${component.group}`)}
        </span>
        <span className="ml-auto text-[0.66rem] text-[var(--muted-foreground)]">
          {tc("checked", {
            when: format.relativeTime(observedAt(data.observed_at), relativeNow()),
          })}
        </span>
      </div>

      <DrawerSection label={t("asked")}>
        <p className="text-xs text-[var(--foreground)]">{component.asked || "—"}</p>
      </DrawerSection>

      <DrawerSection label={t("answered")}>
        {/* Verbatim, monospace, wrapped — the evidence, never paraphrased here. */}
        <p className="whitespace-pre-wrap break-words font-mono text-[0.7rem] leading-relaxed text-[var(--foreground)]">
          {component.detail || "—"}
        </p>
        {component.address ? (
          <p className="mt-1.5 flex flex-wrap items-baseline gap-x-2 text-[0.66rem] text-[var(--muted-foreground)]">
            <span className="font-mono">{component.address}</span>
            {component.outcome && tc.has(`outcome.${component.outcome}`) ? (
              <span>{tc(`outcome.${component.outcome}`)}</span>
            ) : null}
            {component.raw && component.raw !== component.detail ? (
              <span className="font-mono">{component.raw}</span>
            ) : null}
          </p>
        ) : null}
      </DrawerSection>

      {/* The second question asked of this component, always shown when it was asked at all.
          The row above answers "does it answer"; this answers "can the adapter that uses it
          actually read". They can differ, and when they do, this drawer is where an operator
          finds out WHY the consequences block blames a component the table shows as green. */}
      {component.read ? (
        <DrawerSection label={t("read")}>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={verdictTone(component.read.verdict)}>
              {tc(`state.${component.read.verdict}`)}
            </Badge>
            {component.read.verdict !== component.verdict ? (
              <span className="text-[0.66rem] text-[var(--tessera-fg-warning)]">
                {t("readDiverges")}
              </span>
            ) : null}
          </div>
          <p className="mt-1.5 whitespace-pre-wrap break-words font-mono text-[0.7rem] leading-relaxed text-[var(--muted-foreground)]">
            {component.read.detail || "—"}
          </p>
        </DrawerSection>
      ) : null}

      {dependents.length > 0 ? (
        <DrawerSection label={t("dependents")}>
          <ul className="flex flex-col gap-1">
            {dependents.map((row) => (
              <li key={row.key} className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                <span className="flex items-center gap-1 text-[0.72rem] font-medium text-[var(--foreground)]">
                  {row.gates_agents ? (
                    <ShieldAlert
                      className="h-3 w-3 shrink-0 text-[var(--tessera-fg-warning)]"
                      aria-label={tq("gatesAgents")}
                    />
                  ) : null}
                  {tq(`capability.${row.key}`)}
                </span>
                <Badge tone={stateTone(row.state)}>{tq(`state.${row.state}`)}</Badge>
                {row.checked_by_read.includes(component.name) ? (
                  <span
                    className="flex items-center gap-0.5 text-[0.62rem] text-[var(--muted-foreground)]"
                    title={t("readBackedTitle")}
                  >
                    <SearchCheck className="h-3 w-3" />
                    {t("readBacked")}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </DrawerSection>
      ) : null}

      {edges.length > 0 ? (
        <DrawerSection label={t("edges")}>
          <ul className="flex flex-col gap-1.5">
            {edges.map((edge) => (
              <li key={`${edge.source}-${edge.target}-${edge.signal}`} className="text-[0.7rem]">
                <span className="text-[var(--foreground)]">
                  {edge.source} → {edge.target}
                </span>
                <span className="text-[var(--muted-foreground)]">
                  {" · "}
                  {t(`signal.${edge.signal}`)}
                  {edge.profile ? ` (${t("remoteProfile")})` : ""}
                </span>
                {/* The citation, in the open: the drawing is checkable from here. */}
                <span
                  className="block truncate font-mono text-[0.62rem] text-[var(--muted-foreground)]"
                  title={edge.declared_in}
                >
                  {edge.declared_in}
                </span>
              </li>
            ))}
          </ul>
        </DrawerSection>
      ) : null}

      {component.group === "stack" ? (
        <DrawerSection label={t("lastDay")}>
          {history.isPending ? (
            <p className="text-[0.66rem] text-[var(--muted-foreground)]">{t("historyLoading")}</p>
          ) : history.data ? (
            <>
              <ComponentTimeline
                phases={history.data.phases}
                component={component.name}
                since={history.data.window.since}
                until={history.data.window.until}
                days={1}
              />
              <p className="mt-1.5 text-[0.66rem] text-[var(--muted-foreground)]">
                {availability
                  ? t("availabilityLine", {
                      ok:
                        availability.ok_ratio === null
                          ? t("cannotSay")
                          : pctFmt(availability.ok_ratio),
                      observed: humanSeconds(availability.observed_seconds),
                    })
                  : t("neverObserved")}
              </p>
            </>
          ) : (
            <p className="text-[0.66rem] text-[var(--muted-foreground)]">
              {t("historyUnreadable")}
            </p>
          )}
        </DrawerSection>
      ) : null}

      {link ? (
        <DrawerSection label={t("door")}>
          <a
            href={link.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md border border-[var(--tessera-border)] px-2 py-1 text-[0.7rem] text-[var(--foreground)] transition-colors hover:border-[var(--tessera-green)]/50 hover:text-[var(--tessera-green)]"
          >
            <span className="font-mono text-[0.66rem]">{link.url}</span>
            {link.hostLocal ? (
              <Home className="h-2.5 w-2.5 shrink-0 text-[var(--muted-foreground)]" />
            ) : null}
            <ArrowUpRight className="h-3 w-3 shrink-0" />
          </a>
          {link.hostLocal ? (
            <p className="mt-1 text-[0.62rem] text-[var(--muted-foreground)]">
              {t("hostLocalNote")}
            </p>
          ) : null}
        </DrawerSection>
      ) : null}
    </DetailDrawer>
  );
}

function DrawerSection({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section>
      <p className="mb-1 text-[0.6rem] font-medium uppercase tracking-wide text-[var(--muted-foreground)]">
        {label}
      </p>
      {children}
    </section>
  );
}
