"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Download, History, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { fetchEtatADate } from "@/lib/api/client";
import type { EtatADate as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

const TYPE_TONE: Record<string, string> = {
  violet: "border-[#8b7cf0]/30 bg-[#8b7cf0]/15 text-[#c4b5fd]",
  blue: "border-[#4c8bf5]/30 bg-[#4c8bf5]/15 text-[#93c5fd]",
};
const KIND_DOT: Record<string, string> = {
  info: "bg-sky-400",
  ok: "bg-emerald-400",
  warn: "bg-amber-400",
};

/** datetime-local value (browser-local) -> ISO instant, or null when empty. */
function toIso(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

export function EtatADate() {
  const t = useTranslations("etatADate");
  // null = live; a committed ISO instant once the operator reconstructs at T.
  const [draft, setDraft] = useState("");
  const [asOf, setAsOf] = useState<string | null>(null);

  const { data } = useQuery({
    queryKey: ["etat-a-date", asOf],
    queryFn: ({ signal }) => fetchEtatADate(asOf, signal),
    staleTime: 30_000,
  });

  function downloadReport() {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${data.meta?.ref_code ?? "etat-a-date"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      <ControlBar
        t={t}
        draft={draft}
        onDraft={setDraft}
        onReconstruct={() => setAsOf(toIso(draft))}
        refCode={data?.meta?.ref_code ?? "-"}
        agent={data?.meta?.agent ?? "-"}
        contextSource={data?.meta?.context_source ?? "-"}
        onDownload={downloadReport}
        canDownload={Boolean(data?.available)}
      />

      {data === undefined ? (
        <EtatSkeleton />
      ) : !data.available ? (
        <div className="flex min-h-[50vh] items-center justify-center text-sm text-[var(--tessera-text-muted)]">
          {t("unavailable")}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-5">
            {(data.kpis ?? []).map((k) => (
              <KpiTile key={k.key} kpi={k} />
            ))}
          </div>

          <div className="grid gap-2.5 xl:grid-cols-12">
            <SourcesTable data={data} className="xl:col-span-8" />
            <div className="flex flex-col gap-2.5 xl:col-span-4">
              <Integrity data={data} />
              <Timeline data={data} />
              <Policies data={data} />
            </div>
          </div>

          <SummaryCards data={data} />
        </>
      )}
    </div>
  );
}

// ── control bar ──────────────────────────────────────────────────────────────

type T = ReturnType<typeof useTranslations<"etatADate">>;

function ControlBar({
  t,
  draft,
  onDraft,
  onReconstruct,
  refCode,
  agent,
  contextSource,
  onDownload,
  canDownload,
}: {
  t: T;
  draft: string;
  onDraft: (v: string) => void;
  onReconstruct: () => void;
  refCode: string;
  agent: string;
  contextSource: string;
  onDownload: () => void;
  canDownload: boolean;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={onDownload}
          disabled={!canDownload}
          className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)] disabled:opacity-50"
        >
          <Download className="h-4 w-4" /> {t("downloadReport")}
        </button>
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <Field label={t("agent")}>
          <span className="flex h-9 items-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-sm">
            {agent}
          </span>
        </Field>
        <Field label={t("dateTime")}>
          <input
            type="datetime-local"
            value={draft}
            onChange={(e) => onDraft(e.target.value)}
            aria-label={t("dateTime")}
            className="h-9 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-sm text-[var(--tessera-text)] outline-none focus:border-[#7c5cf5]"
          />
        </Field>
        <Field label={t("contextSource")}>
          <span className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-sm">
            {contextSource}
            <span className="rounded bg-[var(--tessera-surface)] px-1.5 py-0.5 font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
              {refCode}
            </span>
          </span>
        </Field>
        <button
          type="button"
          onClick={onReconstruct}
          className="flex h-9 items-center gap-2 rounded-md border border-[#7c5cf5] bg-[#6d4aed] px-4 text-xs font-medium text-white hover:bg-[#7c5cf5]"
        >
          <History className="h-4 w-4" /> {t("reconstruct")}
        </button>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[0.62rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
        {label}
      </span>
      {children}
    </div>
  );
}

// ── KPI ────────────────────────────────────────────────────────────────────

function KpiTile({ kpi }: { kpi: NonNullable<Data["kpis"]>[number] }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <p className="truncate text-[0.66rem] text-[var(--tessera-text-muted)]">{kpi.label}</p>
      <p className="text-[1.4rem] font-semibold tabular-nums text-[var(--tessera-text)]">
        {kpi.value}
      </p>
      <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">{kpi.hint}</p>
    </div>
  );
}

// ── panels ───────────────────────────────────────────────────────────────────

function Panel({
  title,
  children,
  className,
}: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section
      className={cn(
        "flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3",
        className,
      )}
    >
      <h2 className="mb-2 text-[0.78rem] font-semibold text-[var(--tessera-text)]">{title}</h2>
      {children}
    </section>
  );
}

function SourcesTable({ data, className }: { data: Data; className?: string }) {
  const tbl = data.table;
  if (!tbl) return null;
  return (
    <Panel title={tbl.title} className={className}>
      <div className="overflow-x-auto">
        <table className="w-full table-fixed border-collapse text-[0.72rem]">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-left text-[0.62rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              <th className="py-2" style={{ width: "34%" }}>
                Source
              </th>
              <th style={{ width: "18%" }}>Type</th>
              <th style={{ width: "12%" }}>Langues</th>
              <th className="text-right" style={{ width: "12%" }}>
                Fragments
              </th>
              <th style={{ width: "12%" }}>Statut</th>
            </tr>
          </thead>
          <tbody>
            {tbl.rows.map((r) => (
              <tr key={r.key} className="border-b border-[var(--tessera-border)]/40">
                <td className="truncate py-2 pr-2 font-medium text-[var(--tessera-text)]">
                  {r.source}
                  <span className="block text-[0.58rem] font-normal text-[var(--tessera-text-muted)]">
                    {r.updated}
                  </span>
                </td>
                <td>
                  <span
                    className={cn(
                      "rounded-full border px-2 py-0.5 text-[0.58rem]",
                      TYPE_TONE[r.type_tone] ??
                        "border-slate-500/30 bg-slate-500/15 text-slate-300",
                    )}
                  >
                    {r.type}
                  </span>
                </td>
                <td className="uppercase tabular-nums text-[var(--tessera-text-muted)]">
                  {r.langs}
                </td>
                <td className="text-right tabular-nums text-[var(--tessera-text)]">{r.chunks}</td>
                <td>
                  <span
                    className={cn(
                      "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[0.58rem] font-medium",
                      r.status === "accessible"
                        ? "border-emerald-500/30 bg-emerald-500/15 text-emerald-300"
                        : "border-red-500/30 bg-red-500/15 text-red-300",
                    )}
                  >
                    {r.status_label}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function Integrity({ data }: { data: Data }) {
  const it = data.integrity;
  if (!it) return null;
  return (
    <section className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="flex flex-col">
          <span className="text-[0.62rem] text-[var(--tessera-text-muted)]">
            Couverture de l'index
          </span>
          <span className="text-[1.3rem] font-semibold tabular-nums">{it.coverage}</span>
        </span>
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[0.6rem] font-medium",
            it.verified
              ? "border-emerald-500/30 bg-emerald-500/15 text-emerald-300"
              : "border-red-500/30 bg-red-500/15 text-red-300",
          )}
        >
          {it.verified ? <ShieldCheck className="h-3.5 w-3.5" /> : null}
          {it.verified_label}
        </span>
      </div>
      <dl className="mt-2 flex flex-col gap-1.5 text-[0.72rem]">
        <div className="flex items-center justify-between gap-2">
          <dt className="text-[var(--tessera-text-muted)]">Derniere synchro avant T</dt>
          <dd className="font-medium">{it.last_sync}</dd>
        </div>
        <div className="flex items-center justify-between gap-2">
          <dt className="text-[var(--tessera-text-muted)]">Journalisation</dt>
          <dd className="font-medium">{it.chain_label}</dd>
        </div>
      </dl>
    </section>
  );
}

function Timeline({ data }: { data: Data }) {
  const tl = data.timeline;
  if (!tl) return null;
  return (
    <Panel title={tl.title}>
      {tl.rows.length === 0 ? (
        <p className="py-1 text-[0.72rem] text-[var(--tessera-text-muted)]">Aucun evenement a T.</p>
      ) : (
        <ul className="flex flex-col gap-2.5">
          {tl.rows.map((r, i) => (
            <li key={`${r.time}-${i}`} className="flex gap-2.5 text-[0.72rem]">
              <span
                className={cn(
                  "mt-1 h-1.5 w-1.5 shrink-0 rounded-full",
                  KIND_DOT[r.kind] ?? "bg-slate-400",
                )}
              />
              <span className="min-w-0">
                <span className="block tabular-nums text-[var(--tessera-text-muted)]">
                  {r.time}
                </span>
                <span className="text-[var(--tessera-text)]">{r.label}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function Policies({ data }: { data: Data }) {
  const p = data.policies;
  if (!p) return null;
  return (
    <Panel title={p.title}>
      <dl className="flex flex-col gap-1.5 text-[0.72rem]">
        {p.rows.map((r) => (
          <div key={r.label} className="flex items-center justify-between gap-2">
            <dt className="text-[var(--tessera-text-muted)]">{r.label}</dt>
            <dd className="font-medium tabular-nums text-[var(--tessera-text)]">{r.value}</dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}

function SummaryCards({ data }: { data: Data }) {
  const s = data.summary;
  if (!s) return null;
  return (
    <Panel title={s.title}>
      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-4">
        {s.cards.map((c) => (
          <div
            key={c.label}
            className="flex flex-col gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-2.5"
          >
            <span className="flex items-center gap-1.5 text-[0.62rem] text-[var(--tessera-text-muted)]">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> {c.label}
            </span>
            <span className="text-[1.1rem] font-semibold tabular-nums text-[var(--tessera-text)]">
              {c.value}
            </span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

// ── skeleton ───────────────────────────────────────────────────────────────

const SKELETON_KPIS = ["a", "b", "c", "d", "e"];

function EtatSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-5">
        {SKELETON_KPIS.map((k) => (
          <Skeleton key={k} className="h-[88px] w-full rounded-lg" />
        ))}
      </div>
      <div className="grid gap-2.5 xl:grid-cols-12">
        <Skeleton className="h-80 rounded-lg xl:col-span-8" />
        <Skeleton className="h-80 rounded-lg xl:col-span-4" />
      </div>
    </div>
  );
}
