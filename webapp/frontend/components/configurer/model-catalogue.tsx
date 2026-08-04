"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Cpu, GitBranch, Users } from "lucide-react";
import { useSession } from "next-auth/react";
import { useLocale, useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { DetailDrawer } from "@/components/cockpit/detail-drawer";
import { MetricInfo } from "@/components/cockpit/metric-info";
import { Button } from "@/components/ui/button";
import { Truncate } from "@/components/ui/truncate";
import { Link } from "@/i18n/navigation";
import { AGENT_SCOPE_PARAM, parseAgentScope } from "@/lib/agent-scope";
import {
  fetchModelCatalogue,
  fetchSettingsOverrides,
  mutateSettingsOverride,
  mutateSettingsOverrideRevert,
} from "@/lib/api/client";
import type { ModelCatalogue as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

type Row = NonNullable<Data["models"]>[number];

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

/** ⓘ for a model-catalogue KPI, reading models.explain.<k>.{what,how,source?}.
 * Guarded: an unmapped KPI key simply renders no ⓘ. */
function KpiInfo({ k, title }: { k: string; title: string }) {
  const te = useTranslations("models.explain");
  if (!te.has(`${k}.what`)) return null;
  return (
    <MetricInfo
      title={title}
      what={te(`${k}.what`)}
      how={te(`${k}.how`)}
      source={te.has(`${k}.source`) ? te(`${k}.source`) : undefined}
    />
  );
}

export function ModelCatalogue() {
  const t = useTranslations("models");
  const locale = useLocale();
  const searchParams = useSearchParams();
  const scope = parseAgentScope(searchParams.get(AGENT_SCOPE_PARAM));

  const { data, isLoading } = useQuery({
    queryKey: ["model-catalogue", locale, scope],
    queryFn: ({ signal }) => fetchModelCatalogue(locale, scope, signal),
    staleTime: 60_000,
  });

  const [selectedId, setSelectedId] = useState<string | null>(null);

  const rows = useMemo<Row[]>(() => {
    const all = data?.models ?? [];
    if (scope === "all") return all;
    return all.filter((m) => m.consumer_ids.includes(scope));
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

  const selected = selectedId ? (rows.find((m) => m.id === selectedId) ?? null) : null;

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
              <p className="flex items-center gap-1 text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
                <Truncate full={kpi.label} className="min-w-0">
                  {kpi.label}
                </Truncate>
                <KpiInfo k={kpi.key} title={kpi.label} />
              </p>
              <p className="mt-1 truncate font-mono text-[0.82rem] font-semibold text-[var(--tessera-text-strong)]">
                {kpi.value}
              </p>
            </div>
          ))}
        </div>
      ) : null}

      <ServingModels />

      <div>
        <div className="overflow-x-auto rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
          <table
            data-premium-table="true"
            className="w-full min-w-[760px] border-collapse text-left text-xs"
            data-testid="models-table"
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
              {rows.map((m) => (
                <tr
                  key={m.id}
                  onClick={() => setSelectedId(m.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      setSelectedId(m.id);
                    }
                  }}
                  // biome-ignore lint/a11y/useSemanticElements: a table row cannot be a button; keyboard + role provided.
                  role="button"
                  tabIndex={0}
                  aria-haspopup="dialog"
                  aria-label={m.name}
                  aria-pressed={selected?.id === m.id}
                  className={cn(
                    "cursor-pointer border-b border-[var(--tessera-border)]/60 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#5b8def]",
                    selected?.id === m.id
                      ? "bg-[var(--tessera-surface-2)]"
                      : "hover:bg-[var(--tessera-muted)]/40",
                  )}
                >
                  <td className="px-2.5 py-1.5">
                    <span className="inline-flex items-center gap-1.5 font-mono text-[var(--tessera-text)]">
                      <Cpu className="h-3 w-3 text-[var(--tessera-fg-info)]" /> {m.name}
                    </span>
                  </td>
                  <td className="px-2.5 py-1.5 text-[var(--tessera-text-muted)]">
                    {m.provider_label}
                  </td>
                  <td className="px-2.5 py-1.5 text-[var(--tessera-text-muted)]">{m.role_label}</td>
                  <td className="px-2.5 py-1.5">
                    <span className="inline-flex items-center gap-1.5 text-[var(--tessera-text-muted)]">
                      <span className={cn("h-1.5 w-1.5 rounded-full", STATUS_DOT[m.status])} />
                      {m.status_label}
                    </span>
                  </td>
                  <td className="px-2.5 py-1.5 tabular-nums text-[var(--tessera-text-muted)]">
                    {m.price}
                  </td>
                  <td className="px-2.5 py-1.5 tabular-nums text-[var(--tessera-text-muted)]">
                    {m.used_by}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {selected ? <ModelDetail row={selected} onClose={() => setSelectedId(null)} /> : null}
      {data.note ? (
        <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{data.note}</p>
      ) : null}
    </div>
  );
}

/** The governed serving-model panel (ADR 0030): org + per-agent chat model.
 *  Every effective value is base-or-override with visible provenance; the set /
 *  revert mutations are superadmin-only (verified assertion, mandatory reason)
 *  and land in the governance journal. Non-superadmins see honest disabled
 *  controls, never a button that pretends. */
function ServingModels() {
  const t = useTranslations("models.serving");
  const locale = useLocale();
  const isSuper = useSession().data?.user?.role === "superadmin";
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["settings-overrides"],
    queryFn: ({ signal }) => fetchSettingsOverrides(signal),
    staleTime: 30_000,
  });
  const [editing, setEditing] = useState<{ key: string; mode: "set" | "revert" } | null>(null);
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Unreadable panel (e.g. anonymous session) → render nothing rather than a
  // fabricated empty registry; the page's model table stays fully usable.
  if (!data) return null;

  const submit = async () => {
    if (!editing) return;
    setBusy(true);
    setError(null);
    try {
      if (editing.mode === "set") {
        await mutateSettingsOverride(editing.key, { value, reason });
      } else {
        await mutateSettingsOverrideRevert(editing.key, { reason });
      }
      // Close the form as soon as the mutation lands — before any refetch.
      // Awaiting the (slow) sibling refetches here used to run these setters
      // seconds later, silently closing and blanking a form the operator had
      // already reopened for the next act.
      setEditing(null);
      setReason("");
      await qc.invalidateQueries({ queryKey: ["settings-overrides"] });
      // Mark the sibling surfaces stale without blocking on their refetch.
      void qc.invalidateQueries({ queryKey: ["model-catalogue"] });
      void qc.invalidateQueries({ queryKey: ["parameters-overview"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const startEdit = (key: string, mode: "set" | "revert", effective: string) => {
    setEditing({ key, mode });
    setValue(effective);
    setReason("");
    setError(null);
  };

  return (
    <section
      data-testid="serving-models"
      className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3"
    >
      <h3 className="text-[0.78rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
        {t("title")}
      </h3>
      <p className="mt-0.5 text-[0.6rem] leading-relaxed text-[var(--tessera-text-muted)]">
        {t("note")}
      </p>
      <ul className="mt-2 flex flex-col gap-1.5">
        {data.knobs.map((k) => {
          const effective = k.override?.value ?? k.base;
          const isEditing = editing?.key === k.key;
          // ADR 0034 — the knob family binds the row label and the control.
          const kind = k.kind ?? "model";
          const rowLabel =
            kind === "budget_eur"
              ? t("budgetDaily")
              : kind === "overrun"
                ? t("budgetOverrun")
                : (k.agent_id ?? t("org"));
          return (
            <li
              key={k.key}
              className="flex flex-col gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="min-w-[180px] text-[0.7rem] font-medium text-[var(--tessera-text)]">
                  {rowLabel}
                </span>
                <span className="font-mono text-[0.68rem] text-[var(--tessera-fg-info)]">
                  {effective}
                </span>
                <span
                  className={cn(
                    "inline-flex items-center rounded border px-1.5 py-0.5 text-[0.56rem] font-medium",
                    k.override
                      ? "border-sky-500/30 bg-sky-500/15 text-[var(--tessera-fg-info)]"
                      : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]",
                  )}
                >
                  {k.override ? t("overrideBadge") : t("baseBadge")}
                </span>
                <span className="ml-auto flex items-center gap-2">
                  {isSuper ? (
                    <>
                      {/* While a mutation is in flight (busy covers the awaited panel
                          refetch too), opening another editing session would race the
                          in-flight submit's close — so the affordances wait. */}
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          // Budget knobs with no override start from a usable
                          // value, not the "—" / "block" base token.
                          startEdit(
                            k.key,
                            "set",
                            k.override?.value ??
                              (kind === "budget_eur"
                                ? "10"
                                : kind === "overrun"
                                  ? "block"
                                  : effective),
                          )
                        }
                        className="text-[0.62rem] font-medium text-[var(--tessera-fg-info)] hover:text-[var(--tessera-fg-info)] disabled:opacity-50"
                      >
                        {t("change")}
                      </button>
                      {k.override ? (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => startEdit(k.key, "revert", effective)}
                          className="text-[0.62rem] font-medium text-[var(--tessera-fg-warning)] hover:text-[var(--tessera-fg-warning)] disabled:opacity-50"
                        >
                          {t("revert")}
                        </button>
                      ) : null}
                    </>
                  ) : (
                    <span title={t("superadminOnly")}>
                      <button
                        type="button"
                        disabled
                        className="cursor-not-allowed text-[0.62rem] font-medium text-[var(--tessera-text-muted)] opacity-60"
                      >
                        {t("change")}
                      </button>
                    </span>
                  )}
                </span>
              </div>
              {k.override ? (
                <p className="text-[0.6rem] text-[var(--tessera-text-muted)]">
                  {t("provenance", {
                    author: k.override.author,
                    date: new Date(k.override.updated_at).toLocaleString(locale, {
                      dateStyle: "short",
                      timeStyle: "short",
                    }),
                    reason: k.override.reason,
                  })}
                  {" · "}
                  {t("baseIs", { base: k.base })}
                </p>
              ) : null}
              {isEditing && editing ? (
                <div className="flex flex-wrap items-center gap-2">
                  {editing.mode === "set" ? (
                    kind === "budget_eur" ? (
                      // ADR 0034 — a numeric EUR amount, validated server-side
                      // (positive decimal, refused-not-stored).
                      <input
                        type="number"
                        min="0.5"
                        step="0.5"
                        aria-label={t("budgetDaily")}
                        value={value}
                        onChange={(e) => setValue(e.target.value)}
                        className="h-7 w-28 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-1.5 font-mono text-[0.64rem] text-[var(--tessera-text)]"
                      />
                    ) : kind === "overrun" ? (
                      // ADR 0034 — a closed behaviour list, never free text.
                      <select
                        aria-label={t("budgetOverrun")}
                        value={value}
                        onChange={(e) => setValue(e.target.value)}
                        className="h-7 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-1.5 font-mono text-[0.64rem] text-[var(--tessera-text)]"
                      >
                        {(k.options ?? []).map((o) => (
                          <option key={o} value={o}>
                            {o}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <select
                        aria-label={t("modelLabel")}
                        value={value}
                        onChange={(e) => setValue(e.target.value)}
                        className="h-7 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-1.5 font-mono text-[0.64rem] text-[var(--tessera-text)]"
                      >
                        {data.allowed_chat_models.map((m) => (
                          <option key={m} value={m}>
                            {m}
                          </option>
                        ))}
                      </select>
                    )
                  ) : (
                    <span className="text-[0.64rem] text-[var(--tessera-text)]">
                      {t("revertTo", { base: k.base })}
                    </span>
                  )}
                  <input
                    aria-label={t("reasonLabel")}
                    placeholder={t("reasonPlaceholder")}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    className="h-7 w-64 min-w-0 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-2 text-[0.64rem] text-[var(--tessera-text)] placeholder:text-[var(--tessera-text-muted)]"
                  />
                  <Button
                    size="sm"
                    disabled={busy || !reason.trim()}
                    onClick={submit}
                    className="h-7 border border-[#2e72d2] bg-[#1b4f8a] px-2.5 text-[0.64rem] text-[#d8eaff] hover:bg-[#22609f]"
                  >
                    {editing.mode === "set" ? t("apply") : t("confirmRevert")}
                  </Button>
                  <button
                    type="button"
                    onClick={() => setEditing(null)}
                    className="text-[0.62rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
                  >
                    {t("cancel")}
                  </button>
                  {error ? (
                    <p role="alert" className="text-[0.62rem] text-[var(--tessera-fg-danger)]">
                      {error}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function ModelDetail({
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
      subtitle={row.provider_label}
      icon={<Cpu className="h-4 w-4" />}
      onClose={onClose}
      testId="model-detail"
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
                <Truncate as="dd" full={r.value} className="text-right text-[var(--tessera-text)]">
                  {r.value}
                </Truncate>
              </div>
            ))}
          </dl>
        </div>
      ))}
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
    </DetailDrawer>
  );
}
