"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, GitBranch, ShieldCheck, Users } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { DetailDrawer } from "@/components/cockpit/detail-drawer";
import { MetricInfo } from "@/components/cockpit/metric-info";
import { QueryErrorState } from "@/components/cockpit/query-error-state";
import { Link } from "@/i18n/navigation";
import { AGENT_SCOPE_PARAM, parseAgentScope } from "@/lib/agent-scope";
import { fetchGuardrailCatalogue } from "@/lib/api/client";
import type { GuardrailCatalogue as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

type Row = NonNullable<Data["blocks"]>[number];

const REVALIDATE_HREF = "/agir/release-control";
const VERDICT_DOT: Record<string, string> = {
  good: "bg-emerald-400",
  crit: "bg-red-400",
  bad: "bg-amber-400",
  muted: "bg-[var(--tessera-text-muted)]",
};
const STATUS_DOT: Record<string, string> = {
  active: "bg-emerald-400",
  available: "bg-[var(--tessera-text-muted)]",
};

/** ⓘ for a guardrail KPI, reading guardrailCatalogue.explain.<k>.{what,how,source?}. */
function KpiInfo({ k, title }: { k: string; title: string }) {
  const te = useTranslations("guardrailCatalogue.explain");
  return te.has(`${k}.what`) ? (
    <MetricInfo
      title={title}
      what={te(`${k}.what`)}
      how={te(`${k}.how`)}
      source={te.has(`${k}.source`) ? te(`${k}.source`) : undefined}
    />
  ) : null;
}

export function GuardrailCatalogue() {
  const t = useTranslations("guardrailCatalogue");
  const locale = useLocale();
  const searchParams = useSearchParams();
  const scope = parseAgentScope(searchParams.get(AGENT_SCOPE_PARAM));

  const { data, isLoading, isError, isFetching, refetch } = useQuery({
    queryKey: ["guardrail-catalogue", locale, scope],
    queryFn: ({ signal }) => fetchGuardrailCatalogue(locale, scope, signal),
    staleTime: 60_000,
  });

  const [selectedId, setSelectedId] = useState<string | null>(null);

  const rows = useMemo<Row[]>(() => {
    const all = data?.blocks ?? [];
    if (scope === "all") return all;
    return all.filter((b) => b.consumer_ids.includes(scope));
  }, [data, scope]);

  if (isLoading) {
    return <p className="text-[0.72rem] text-[var(--tessera-text-muted)]">{t("loading")}</p>;
  }
  // Three states, not one. `!data?.available || rows.length === 0` collapsed "the request
  // failed", "the backend says it cannot serve this" and "there are genuinely no guardrails"
  // into a single sentence — and the third is the reassuring one. A platform that reports "no
  // guardrails configured" because its catalogue endpoint is down is telling the operator the
  // opposite of what happened.
  if (isError || !data) {
    return <QueryErrorState onRetry={() => void refetch()} retrying={isFetching} compact />;
  }
  if (!data.available) {
    return (
      <p className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4 text-[0.72rem] text-[var(--tessera-text-muted)]">
        {t("unavailable")}
      </p>
    );
  }
  if (rows.length === 0) {
    return (
      <p className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4 text-[0.72rem] text-[var(--tessera-text-muted)]">
        {t("empty")}
      </p>
    );
  }

  const selected = selectedId ? (rows.find((b) => b.id === selectedId) ?? null) : null;

  return (
    <div className="flex flex-col gap-2.5">
      {data.kpis ? (
        <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
          {data.kpis.map((kpi) => (
            <div
              key={kpi.key}
              data-slot="card"
              className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5"
            >
              <div className="flex items-center gap-1">
                <p className="min-w-0 truncate text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
                  {kpi.label}
                </p>
                <KpiInfo k={kpi.key} title={kpi.label} />
              </div>
              <p className="mt-1 truncate font-mono text-[0.82rem] font-semibold text-[var(--tessera-text-strong)]">
                {kpi.value}
              </p>
            </div>
          ))}
        </div>
      ) : null}

      <div>
        <div className="overflow-x-auto rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
          <table
            data-premium-table="true"
            className="w-full min-w-[760px] border-collapse text-left text-xs"
            data-testid="guardrails-table"
          >
            <thead>
              <tr className="border-b border-[var(--tessera-border)] text-[0.56rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
                {(data.columns ?? []).map((c) => (
                  <th key={c} className="px-2.5 py-2 font-medium">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((b) => (
                <tr
                  key={b.id}
                  onClick={() => setSelectedId(b.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      setSelectedId(b.id);
                    }
                  }}
                  // biome-ignore lint/a11y/useSemanticElements: a table row cannot be a button; keyboard + role provided.
                  role="button"
                  tabIndex={0}
                  aria-haspopup="dialog"
                  aria-label={b.name}
                  aria-pressed={selected?.id === b.id}
                  className={cn(
                    "cursor-pointer border-b border-[var(--tessera-border)]/60 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#5b8def]",
                    selected?.id === b.id
                      ? "bg-[var(--tessera-surface-2)]"
                      : "hover:bg-[var(--tessera-muted)]/40",
                  )}
                >
                  <td className="px-2.5 py-1.5">
                    <span className="inline-flex items-center gap-1.5 font-mono text-[var(--tessera-text)]">
                      <ShieldCheck className="h-3 w-3 text-[var(--tessera-fg-info)]" /> {b.name}
                    </span>
                  </td>
                  <td className="px-2.5 py-1.5 text-[var(--tessera-text-muted)]">{b.scope}</td>
                  <td className="px-2.5 py-1.5 text-[var(--tessera-text-muted)]">
                    {b.composition}
                  </td>
                  <td className="px-2.5 py-1.5">
                    <span className="inline-flex items-center gap-1.5 text-[var(--tessera-text-muted)]">
                      <span
                        className={cn(
                          "h-1.5 w-1.5 rounded-full",
                          STATUS_DOT[b.status] ?? VERDICT_DOT.muted,
                        )}
                      />
                      {b.status_label}
                    </span>
                  </td>
                  <td className="px-2.5 py-1.5 tabular-nums text-[var(--tessera-text-muted)]">
                    {b.used_by}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {selected ? <GuardrailDetail row={selected} onClose={() => setSelectedId(null)} /> : null}
      {data.note ? (
        <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{data.note}</p>
      ) : null}
    </div>
  );
}

function GuardrailDetail({
  row,
  onClose,
}: {
  row: Row;
  onClose: () => void;
}) {
  const d = row.detail;
  return (
    <DetailDrawer
      title={d.name}
      subtitle={row.scope}
      icon={<ShieldCheck className="h-4 w-4" />}
      onClose={onClose}
      testId="guardrail-detail"
      width="max-w-[440px]"
    >
      {d.sections.map((s) => (
        <div key={s.key}>
          <p className="mb-1 text-[0.56rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            {s.title}
          </p>
          <dl className="flex flex-col gap-1 text-[0.66rem]">
            {s.rows.map((r) => (
              <div key={r.label} className="flex items-center justify-between gap-3">
                <dt className="text-[var(--tessera-text-muted)]">{r.label}</dt>
                <dd className="truncate text-right text-[var(--tessera-text)]">{r.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
      {d.consumers ? (
        <div className="border-t border-[var(--tessera-border)] pt-2">
          <div className="mb-1.5 flex items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1.5 text-[0.66rem] font-semibold text-[var(--tessera-text)]">
              <Users className="h-3.5 w-3.5 text-[var(--tessera-fg-info)]" /> {d.consumers.title}
            </span>
            {d.consumers.regate_count > 0 ? (
              <span className="inline-flex items-center gap-1 text-[0.6rem] text-[var(--tessera-fg-warning)]">
                <AlertTriangle className="h-3 w-3" /> {d.consumers.regate_label}
              </span>
            ) : null}
          </div>
          {d.consumers.items.length > 0 ? (
            <ul className="flex flex-wrap gap-1.5">
              {d.consumers.items.map((c) => (
                <li
                  key={c.agent_id}
                  title={c.label}
                  className="inline-flex items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1 text-[0.62rem]"
                >
                  <span
                    className={cn(
                      "h-1.5 w-1.5 rounded-full",
                      VERDICT_DOT[c.tone] ?? VERDICT_DOT.muted,
                    )}
                  />
                  {c.name}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{d.consumers.empty}</p>
          )}
          <p className="mt-1.5 text-[0.56rem] leading-relaxed text-[var(--tessera-text-muted)]">
            {d.consumers.note}
          </p>
          {d.consumers.count > 0 ? (
            <Link
              href={REVALIDATE_HREF}
              className={cn(
                "mt-1.5 inline-flex items-center gap-1 text-[0.6rem] font-medium hover:underline",
                d.consumers.regate_count > 0
                  ? "text-[var(--tessera-fg-warning)]"
                  : "text-[var(--tessera-fg-info)]",
              )}
            >
              <GitBranch className="h-3 w-3" /> {d.consumers.revalidate_label}
            </Link>
          ) : null}
        </div>
      ) : null}
    </DetailDrawer>
  );
}
