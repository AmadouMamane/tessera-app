"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, GitBranch, ShieldCheck, Users, X } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { MetricInfo } from "@/components/cockpit/metric-info";
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

  const { data, isLoading } = useQuery({
    queryKey: ["guardrail-catalogue", locale, scope],
    queryFn: ({ signal }) => fetchGuardrailCatalogue(locale, scope, signal),
    staleTime: 60_000,
  });

  const [selectedId, setSelectedId] = useState<string | null>(null);
  // Closing must survive the rows[0] fallback below — null alone re-selects the first row.
  const [dismissed, setDismissed] = useState(false);

  const rows = useMemo<Row[]>(() => {
    const all = data?.blocks ?? [];
    if (scope === "all") return all;
    return all.filter((b) => b.consumer_ids.includes(scope));
  }, [data, scope]);

  if (isLoading) {
    return <p className="text-[0.72rem] text-[var(--tessera-text-muted)]">{t("loading")}</p>;
  }
  if (!data?.available || rows.length === 0) {
    return (
      <p className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4 text-[0.72rem] text-[var(--tessera-text-muted)]">
        {t("empty")}
      </p>
    );
  }

  const selected = dismissed ? null : (rows.find((b) => b.id === selectedId) ?? rows[0] ?? null);

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

      <div className={cn("grid gap-2.5", selected && "xl:grid-cols-[minmax(0,1fr)_360px]")}>
        <div className="overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
          <table
            className="w-full border-collapse text-left text-[0.72rem]"
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
                  onClick={() => {
                    setDismissed(false);
                    setSelectedId(b.id);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      setDismissed(false);
                      setSelectedId(b.id);
                    }
                  }}
                  // biome-ignore lint/a11y/useSemanticElements: a table row cannot be a button; keyboard + role provided.
                  role="button"
                  tabIndex={0}
                  aria-label={b.name}
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

        {selected ? (
          <GuardrailDetail t={t} row={selected} onClose={() => setDismissed(true)} />
        ) : null}
      </div>
      {data.note ? (
        <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{data.note}</p>
      ) : null}
    </div>
  );
}

function GuardrailDetail({
  t,
  row,
  onClose,
}: {
  t: ReturnType<typeof useTranslations<"guardrailCatalogue">>;
  row: Row;
  onClose: () => void;
}) {
  const d = row.detail;
  return (
    <aside
      data-testid="guardrail-detail"
      className="flex min-w-0 flex-col gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3 xl:sticky xl:top-0 xl:h-fit"
    >
      <div className="flex items-start justify-between gap-2">
        <p className="truncate font-mono text-sm font-semibold text-[var(--tessera-text-strong)]">
          {d.name}
        </p>
        <button
          type="button"
          onClick={onClose}
          aria-label={t("close")}
          className="text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
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
    </aside>
  );
}
