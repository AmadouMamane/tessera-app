"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ChevronRight,
  Database,
  Download,
  FileSearch,
  KeyRound,
  PackageCheck,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";
import type { Route } from "next";
import { useLocale, useTranslations } from "next-intl";
import type { ReactNode } from "react";
import { useState } from "react";

import { downloadBlob } from "@/components/agent/agent-subtab-shared";
import { MetricInfo } from "@/components/cockpit/metric-info";
import { SyntheticNotice } from "@/components/cockpit/synthetic-notice";
import { MetricSparkline } from "@/components/overview/metric-sparkline";
import {
  TemporalRail,
  useRailTimeline,
  useTemporalState,
} from "@/components/overview/temporal-rail";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import {
  fetchEvidencePackManifest,
  fetchEvidencePackVerify,
  fetchProofsOverview,
  fetchSiem,
  mutateEvidencePackCreate,
} from "@/lib/api/client";
import type { EvidencePackVerify, ProofsOverview as ProofsData } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

const PACK_BADGE: Record<string, string> = {
  signe: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  exporte: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  attente: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  echec: "border-red-500/30 bg-red-500/15 text-red-300",
};
const EXP_BADGE: Record<string, string> = {
  ok: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  degraded: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  down: "border-red-500/30 bg-red-500/15 text-red-300",
};
const TABS = ["overview", "evidencePacks", "exporters", "chain", "destinations"] as const;
type Tab = (typeof TABS)[number];

type T = ReturnType<typeof useTranslations<"proofs">>;
type Data = ProofsData;

/** A ⓘ for a proofs metric/zone, reading proofs.explain.<k>.{what,how,source?}. */
function ExplainInfo({ k, title }: { k: string; title: string }) {
  const te = useTranslations("proofs.explain");
  return (
    <MetricInfo
      title={title}
      what={te(`${k}.what`)}
      how={te(`${k}.how`)}
      source={te.has(`${k}.source`) ? te(`${k}.source`) : undefined}
    />
  );
}

export function ProofsOverview() {
  const t = useTranslations("proofs");
  const locale = useLocale();
  const temporal = useTemporalState();
  const railTimeline = useRailTimeline();
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["proofs-overview", locale],
    queryFn: ({ signal }) => fetchProofsOverview(locale, signal),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
  // Freeze one evidence-pack manifest (governed act; fresh payload swaps in).
  const createPack = useMutation({
    mutationFn: () => mutateEvidencePackCreate(locale),
    onSuccess: (fresh) => qc.setQueryData(["proofs-overview", locale], fresh),
  });
  // Real verification verdict for the displayed pack (two facts, shown as such).
  const [verdict, setVerdict] = useState<EvidencePackVerify | null>(null);
  const verify = useMutation({
    mutationFn: (packId: string) => fetchEvidencePackVerify(packId),
    onSuccess: setVerdict,
  });
  const downloadManifest = async (packId: string) => {
    const manifest = await fetchEvidencePackManifest(packId);
    downloadBlob(`${packId}.json`, "application/json", JSON.stringify(manifest, null, 2));
  };
  // The SIEM export is REAL: the normalised ECS events the SOC would ingest.
  const exportSiem = async () => {
    const events = await fetchSiem();
    downloadBlob("tessera-siem-events.json", "application/json", JSON.stringify(events, null, 2));
  };

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        …
      </div>
    );
  }

  // Zones reused by the focused tabs (identical rendering + honesty flags).
  const pipelineZone = (
    <Zone
      label={t("zone.pipeline")}
      info={<ExplainInfo k="zone.pipeline" title={t("zone.pipeline")} />}
    >
      {/* The assembly pipeline + packs are REAL since lot 7 (durable manifests,
          governed create, re-derivable digests) — no synthetic notice here. */}
      <div className="grid gap-3 xl:grid-cols-12">
        <Pipeline t={t} data={data} className="xl:col-span-7" />
        <CurrentPack
          t={t}
          data={data}
          className="xl:col-span-5"
          onCreate={() => createPack.mutate()}
          creating={createPack.isPending}
          onVerify={(id) => verify.mutate(id)}
          verifying={verify.isPending}
          verdict={verdict}
          onDownload={downloadManifest}
        />
      </div>
    </Zone>
  );
  const packsZone = (
    <Zone
      label={t("zone.recentPacks")}
      info={<ExplainInfo k="zone.recentPacks" title={t("zone.recentPacks")} />}
    >
      <div className="grid gap-3 xl:grid-cols-12">
        <RecentPacks t={t} data={data} className="xl:col-span-8" />
        <Panel
          title={t("zone.distribution")}
          info={<ExplainInfo k="zone.distribution" title={t("zone.distribution")} />}
          className="xl:col-span-4"
        >
          <Donut
            slices={data.artifacts_distribution}
            total={data.artifacts_total}
            caption="Total"
            labelOf={(k) => t(`art.${k}`)}
            showCount
          />
        </Panel>
      </div>
    </Zone>
  );
  const exportersZone = (
    <Zone
      label={t("zone.exporters")}
      info={<ExplainInfo k="zone.exporters" title={t("zone.exporters")} />}
      action={
        <Link
          href="/configurer/integrations"
          className="inline-flex shrink-0 items-center gap-0.5 whitespace-nowrap text-[0.62rem] text-[var(--tessera-green)] hover:underline"
        >
          {t("viewAll.exporters")}
          <ChevronRight className="h-3 w-3" />
        </Link>
      }
    >
      <SyntheticNotice signalId="evidence_export" compact />
      <Exporters t={t} data={data} />
    </Zone>
  );
  const cryptoZone = (
    <Zone
      label={t("zone.crypto")}
      info={<ExplainInfo k="zone.crypto" title={t("zone.crypto")} />}
      action={
        <Link
          href="/prouver/audit-logs"
          className="inline-flex shrink-0 items-center gap-0.5 whitespace-nowrap text-[0.62rem] text-[var(--tessera-green)] hover:underline"
        >
          {t("drill.chain")}
          <ChevronRight className="h-3 w-3" />
        </Link>
      }
    >
      <Crypto t={t} data={data} />
    </Zone>
  );
  const controlCasesZone = (
    <Zone
      label={t("zone.controlCases")}
      info={<ExplainInfo k="zone.controlCases" title={t("zone.controlCases")} />}
    >
      <SyntheticNotice signalId="evidence_export" compact />
      <ControlCases t={t} data={data} />
    </Zone>
  );
  const retentionZone = (
    <Zone
      label={t("zone.retention")}
      info={<ExplainInfo k="zone.retention" title={t("zone.retention")} />}
    >
      <SyntheticNotice signalId="evidence_export" compact />
      <Retention t={t} data={data} />
    </Zone>
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pb-1 text-[var(--tessera-text)]">
      <CommandBar t={t} active={activeTab} onSelect={setActiveTab} />
      <TemporalRail
        mode={temporal.mode}
        liveStatus={t("rail.realtime")}
        timeline={railTimeline.data}
        selectedAt={temporal.selectedAt}
        onSelectedAtChange={temporal.setSelectedAt}
        periodKey={temporal.periodKey}
        onPeriodChange={temporal.setPeriodKey}
        windowEnd={temporal.windowEnd}
        onPickDate={temporal.pickDate}
        onModeChange={temporal.changeMode}
      />

      <div id="proofs-tabpanel" role="tabpanel" className="flex min-w-0 flex-col gap-3">
        {activeTab === "evidencePacks" ? (
          <>
            {packsZone}
            {pipelineZone}
          </>
        ) : null}
        {activeTab === "exporters" ? exportersZone : null}
        {activeTab === "chain" ? (
          <div className="grid gap-3 xl:grid-cols-2">
            {cryptoZone}
            <Zone
              label={t("zone.alerts")}
              info={<ExplainInfo k="zone.alerts" title={t("zone.alerts")} />}
            >
              <AlertsPanel t={t} data={data} />
            </Zone>
          </div>
        ) : null}
        {activeTab === "destinations" ? (
          <>
            {retentionZone}
            {controlCasesZone}
          </>
        ) : null}
      </div>

      {activeTab !== "overview" ? null : (
        <>
          <Zone
            label={t("zone.actual")}
            info={<ExplainInfo k="zone.actual" title={t("zone.actual")} />}
          >
            <div className="grid gap-3 xl:grid-cols-12">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:col-span-10 xl:grid-cols-6">
                {data.kpis.map((kpi) => (
                  <KpiTile
                    key={kpi.key}
                    kpi={kpi}
                    label={t(`kpi.${kpi.key}`)}
                    vs={t("delta.vs7d")}
                    info={<ExplainInfo k={`kpi.${kpi.key}`} title={t(`kpi.${kpi.key}`)} />}
                  />
                ))}
              </div>
              <AlertsPanel t={t} data={data} className="xl:col-span-2" />
            </div>
          </Zone>

          <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_320px]">
            <div className="flex min-w-0 flex-col gap-3">
              {pipelineZone}
              {packsZone}
              {exportersZone}
              <div className="grid gap-3 xl:grid-cols-2">
                {cryptoZone}
                {controlCasesZone}
              </div>
              {retentionZone}
            </div>

            <ProofsRail
              t={t}
              data={data}
              onCreatePack={() => createPack.mutate()}
              creating={createPack.isPending}
              onExportSiem={exportSiem}
              onDownloadManifest={
                data.current_pack ? () => downloadManifest(data.current_pack?.id ?? "") : null
              }
            />
          </div>
        </>
      )}

      <Footer t={t} data={data} />
    </div>
  );
}

// ── chrome ───────────────────────────────────────────────────────────────────

function CommandBar({
  t,
  active,
  onSelect,
}: {
  t: T;
  active: Tab;
  onSelect: (tab: Tab) => void;
}) {
  return (
    <section
      role="tablist"
      aria-label={t("tabs.overview")}
      className="flex min-h-[54px] shrink-0 flex-wrap items-center gap-1.5 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]"
    >
      {TABS.map((tab) => (
        <button
          key={tab}
          type="button"
          role="tab"
          aria-selected={tab === active}
          aria-controls="proofs-tabpanel"
          onClick={() => onSelect(tab)}
          className={cn(
            "h-8 shrink-0 rounded-md border px-3 text-xs font-medium transition-colors",
            tab === active
              ? "border-[#2e72d2] bg-[#0d3561] text-[#d8eaff]"
              : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-muted)] hover:text-[var(--tessera-text)]",
          )}
        >
          {t(`tabs.${tab}`)}
        </button>
      ))}
    </section>
  );
}

function AlertsPanel({ t, data, className }: { t: T; data: Data; className?: string }) {
  return (
    <Panel
      title={t("zone.alerts")}
      info={<ExplainInfo k="zone.alerts" title={t("zone.alerts")} />}
      className={className}
      action={
        <ViewAll label={t("viewAll.alerts", { n: data.alert_count })} href="/prouver/audit-logs" />
      }
    >
      <ul className="flex flex-col gap-1.5">
        {data.alerts.map((a) => (
          <li key={a.label} className="flex items-center gap-2 text-[0.7rem]">
            <span
              className={cn(
                "h-1.5 w-1.5 shrink-0 rounded-full",
                a.level === "warn"
                  ? "bg-amber-400"
                  : a.level === "bad"
                    ? "bg-red-400"
                    : "bg-emerald-400",
              )}
            />
            <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">{a.label}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// ── pipeline + current pack ──────────────────────────────────────────────────

function Pipeline({ t, data, className }: { t: T; data: Data; className?: string }) {
  return (
    <Panel title="" className={className}>
      <div className="flex flex-col gap-2">
        <ol className="flex items-stretch gap-1">
          {data.pipeline.map((step, i) => (
            <li key={step.key} className="flex min-w-0 flex-1 items-center gap-1">
              <div className="flex min-w-0 flex-1 flex-col items-center gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-2 text-center">
                <PackageCheck className="h-3.5 w-3.5 text-[#87bfff]" />
                <span className="truncate text-[0.62rem] text-[var(--tessera-text-muted)]">
                  {t(`pipeline.${step.key}`)}
                </span>
                <span className="text-[0.9rem] font-semibold tabular-nums text-white">
                  {step.count}
                </span>
                <span
                  className={cn(
                    "inline-flex items-center gap-0.5 text-[0.58rem]",
                    step.status === "ok" ? "text-emerald-300" : "text-red-300",
                  )}
                >
                  <ShieldCheck className="h-2.5 w-2.5" /> {step.status === "ok" ? "OK" : "KO"}
                </span>
              </div>
              {i < data.pipeline.length - 1 ? (
                <ChevronRight className="h-4 w-4 shrink-0 text-[var(--tessera-text-muted)]" />
              ) : null}
            </li>
          ))}
        </ol>
        <p
          className={cn(
            "inline-flex items-center gap-1.5 text-[0.7rem]",
            data.chain_verified ? "text-[var(--tessera-green)]" : "text-red-300",
          )}
        >
          <ShieldCheck className="h-3.5 w-3.5" />{" "}
          {data.chain_verified ? t("pipeline.chainOk") : t("pipeline.chainBroken")}
        </p>
      </div>
    </Panel>
  );
}

function CurrentPack({
  t,
  data,
  className,
  onCreate,
  creating,
  onVerify,
  verifying,
  verdict,
  onDownload,
}: {
  t: T;
  data: Data;
  className?: string;
  onCreate: () => void;
  creating: boolean;
  onVerify: (id: string) => void;
  verifying: boolean;
  verdict: EvidencePackVerify | null;
  onDownload: (id: string) => void;
}) {
  const p = data.current_pack;
  if (p === null) {
    // Honest empty: nobody froze a pack yet — the create act is right here.
    return (
      <Panel
        title={t("zone.currentPack")}
        info={<ExplainInfo k="zone.currentPack" title={t("zone.currentPack")} />}
        className={className}
      >
        <div className="flex flex-col items-start gap-2 py-3">
          <p className="text-[0.7rem] text-[var(--tessera-text-muted)]">{t("pack.none")}</p>
          <Button
            size="sm"
            disabled={creating}
            onClick={onCreate}
            className="h-8 gap-1.5 border border-[#2e72d2] bg-[#1b4f8a] px-3 text-[0.7rem] text-[#d8eaff] hover:bg-[#22609f]"
          >
            <PackageCheck className="h-3.5 w-3.5" /> {t("pack.create")}
          </Button>
        </div>
      </Panel>
    );
  }
  return (
    <Panel
      title={t("zone.currentPack")}
      info={<ExplainInfo k="zone.currentPack" title={t("zone.currentPack")} />}
      className={className}
    >
      <div className="flex flex-col gap-2 text-[0.72rem]">
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-[#87bfff]">{p.id}</span>
          <span className="text-[var(--tessera-text-muted)]">{p.period}</span>
        </div>
        <KV label={t("packCol.scope")} value={p.scope} />
        <KV label={t("pack.hash")} value={p.hash} mono />
        <KV label={t("pack.signer")} value={p.signer} />
        <div>
          <p className="mb-1 text-[0.62rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            {t("pack.contents")}
          </p>
          <p className="text-[0.68rem] leading-relaxed text-[var(--tessera-text)]">
            {p.contents.map((c) => `${c.n} ${t(`content.${c.key}`)}`).join(", ")}
          </p>
        </div>
        <div className="mt-1 flex gap-2">
          <Button
            size="sm"
            onClick={() => onDownload(p.id)}
            className="h-8 flex-1 justify-center gap-1.5 border border-[#2e72d2] bg-[#1b4f8a] text-[0.7rem] text-[#d8eaff] hover:bg-[#22609f]"
          >
            <Download className="h-3.5 w-3.5" /> {t("pack.download")}
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={verifying}
            onClick={() => onVerify(p.id)}
            className="h-8 flex-1 justify-center gap-1.5 border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[0.7rem]"
          >
            <ShieldCheck className="h-3.5 w-3.5" /> {t("pack.verify")}
          </Button>
        </div>
        {verdict && verdict.pack_id === p.id ? (
          <output className="flex flex-col gap-0.5 text-[0.64rem]">
            <span className={verdict.manifest_ok ? "text-emerald-300" : "text-red-300"}>
              {verdict.manifest_ok ? t("pack.manifestOk") : t("pack.manifestBad")}
            </span>
            <span className={verdict.chain_verified_now ? "text-emerald-300" : "text-red-300"}>
              {verdict.chain_verified_now ? t("pack.chainOkNow") : t("pack.chainBadNow")} (
              {verdict.chain_length_now})
            </span>
          </output>
        ) : null}
      </div>
    </Panel>
  );
}

function RecentPacks({ t, data, className }: { t: T; data: Data; className?: string }) {
  return (
    <Panel
      title=""
      className={className}
      action={<ViewAll label={t("viewAll.packs")} href="/prouver/etat-a-date" />}
    >
      {/* Real durable packs since lot 7 — no synthetic notice. */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-[0.7rem]">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {(
                [
                  "id",
                  "scope",
                  "artifacts",
                  "signature",
                  "destinations",
                  "by",
                  "time",
                  "status",
                ] as const
              ).map((c) => (
                <th key={c} className="whitespace-nowrap px-1.5 py-1 font-medium">
                  {t(`packCol.${c}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.recent_packs.map((p) => (
              <tr key={p.id} className="border-b border-[var(--tessera-border)]/60 last:border-0">
                <td className="px-1.5 py-1 font-mono text-[0.62rem] text-[#87bfff]">{p.id}</td>
                <td className="max-w-[150px] truncate px-1.5 py-1 text-[var(--tessera-text-muted)]">
                  {p.scope}
                </td>
                <td className="px-1.5 py-1 tabular-nums text-[var(--tessera-text)]">
                  {p.artifacts}
                </td>
                <td className="px-1.5 py-1 text-emerald-300">
                  <ShieldCheck className="h-3.5 w-3.5" />
                </td>
                <td className="px-1.5 py-1 tabular-nums text-[var(--tessera-text-muted)]">
                  {p.destinations}
                </td>
                <td className="px-1.5 py-1 text-[var(--tessera-text-muted)]">{p.by}</td>
                <td className="px-1.5 py-1 tabular-nums text-[var(--tessera-text-muted)]">
                  {p.time}
                </td>
                <td className="px-1.5 py-1">
                  <Badge className={PACK_BADGE[p.status]}>{t(`packStatus.${p.status}`)}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function Exporters({ t, data }: { t: T; data: Data }) {
  return (
    <Panel
      title=""
      action={<ViewAll label={t("viewAll.exporters")} href="/configurer/integrations" />}
    >
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-[0.72rem]">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {(["destination", "format", "status", "lastPush", "queue", "retention"] as const).map(
                (c) => (
                  <th key={c} className="whitespace-nowrap px-2 py-1.5 font-medium">
                    {t(`expCol.${c}`)}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {data.exporters.map((e) => (
              <tr
                key={e.destination}
                className="border-b border-[var(--tessera-border)]/60 last:border-0"
              >
                <td className="px-2 py-1.5 font-medium text-[var(--tessera-text)]">
                  {e.destination}
                </td>
                <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">{e.format}</td>
                <td className="px-2 py-1.5">
                  <Badge className={EXP_BADGE[e.status]}>{t(`expStatus.${e.status}`)}</Badge>
                </td>
                <td className="px-2 py-1.5 tabular-nums text-[var(--tessera-text-muted)]">
                  {e.last_push}
                </td>
                <td className="px-2 py-1.5 tabular-nums text-[var(--tessera-text-muted)]">
                  {e.queue}
                </td>
                <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">{e.retention}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function Crypto({ t, data }: { t: T; data: Data }) {
  const c = data.crypto;
  return (
    <Panel title="">
      <div className="flex items-center gap-4">
        <div className="flex flex-col items-center">
          <KeyRound className="h-7 w-7 text-emerald-400" />
          <span className="mt-1 text-lg font-semibold text-white">{c.valid_signatures}</span>
          <span className="text-[0.58rem] text-[var(--tessera-text-muted)]">
            {t("crypto.validSignatures")}
          </span>
        </div>
        <dl className="flex min-w-0 flex-1 flex-col gap-1.5 text-[0.7rem]">
          <KV label={t("crypto.algorithm")} value={c.algorithm} mono />
          <KV label={t("crypto.chainLength")} value={c.chain_length} />
          <KV
            label={t("crypto.anomalies")}
            value={String(c.anomalies)}
            tone={c.anomalies === 0 ? "text-emerald-300" : "text-red-300"}
          />
        </dl>
      </div>
    </Panel>
  );
}

function ControlCases({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title="">
      <table className="w-full border-collapse text-left text-[0.7rem]">
        <thead>
          <tr className="border-b border-[var(--tessera-border)] text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
            {(["caseId", "subject", "linked", "owner", "status"] as const).map((c) => (
              <th key={c} className="px-1.5 py-1 font-medium">
                {t(`ccCol.${c}`)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.control_case_proofs.map((c) => (
            <tr
              key={c.case_id}
              className="border-b border-[var(--tessera-border)]/60 last:border-0"
            >
              <td className="px-1.5 py-1 font-mono text-[0.64rem] text-[var(--tessera-green)]">
                {c.case_id}
              </td>
              <td className="max-w-[150px] truncate px-1.5 py-1 text-[var(--tessera-text)]">
                {c.subject}
              </td>
              <td className="px-1.5 py-1 text-center tabular-nums text-[var(--tessera-text-muted)]">
                {c.linked}
              </td>
              <td className="px-1.5 py-1 text-[var(--tessera-text-muted)]">{c.owner}</td>
              <td className="px-1.5 py-1">
                <span className={c.status === "ok" ? "text-emerald-300" : "text-amber-300"}>
                  {t(`ccStatus.${c.status}`)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

function Retention({ t, data }: { t: T; data: Data }) {
  return (
    <Panel title="">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-[0.72rem]">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {(
                [
                  "destination",
                  "proofType",
                  "retention",
                  "obligation",
                  "coverage",
                  "expiry",
                ] as const
              ).map((c) => (
                <th key={c} className="whitespace-nowrap px-2 py-1.5 font-medium">
                  {t(`retCol.${c}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.retention.map((r) => (
              <tr
                key={`${r.destination}-${r.proof_type}`}
                className="border-b border-[var(--tessera-border)]/60 last:border-0"
              >
                <td className="px-2 py-1.5 font-medium text-[var(--tessera-text)]">
                  {r.destination}
                </td>
                <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">{r.proof_type}</td>
                <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">{r.retention}</td>
                <td className="px-2 py-1.5">
                  <Badge className="border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]">
                    {r.obligation}
                  </Badge>
                </td>
                <td className="px-2 py-1.5 tabular-nums text-emerald-300">{r.coverage}%</td>
                <td className="px-2 py-1.5 tabular-nums text-[var(--tessera-text-muted)]">
                  {r.expiry}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

// ── right rail ───────────────────────────────────────────────────────────────

function ProofsRail({
  t,
  data,
  onCreatePack,
  creating,
  onExportSiem,
  onDownloadManifest,
}: {
  t: T;
  data: Data;
  onCreatePack: () => void;
  creating: boolean;
  onExportSiem: () => void;
  onDownloadManifest: (() => void) | null;
}) {
  return (
    <aside className="flex min-w-0 flex-col gap-3">
      <Panel
        title={t("zone.integrity")}
        info={<ExplainInfo k="zone.integrity" title={t("zone.integrity")} />}
      >
        <div className="flex items-center gap-3">
          <ShieldCheck
            className={cn(
              "h-9 w-9 shrink-0",
              data.chain_verified ? "text-emerald-400" : "text-red-400",
            )}
          />
          <div>
            <p
              className={cn(
                "text-sm font-semibold",
                data.chain_verified ? "text-emerald-300" : "text-red-300",
              )}
            >
              {data.chain_verified ? t("integrity.intact") : t("integrity.broken")}
            </p>
            <p className="text-[0.66rem] text-[var(--tessera-text-muted)]">
              {data.chain_verified ? t("integrity.noAnomaly") : t("integrity.hasAnomaly")}
            </p>
          </div>
        </div>
      </Panel>

      <Panel title={t("zone.quickActions")}>
        {/* All four are REAL: governed pack freeze, the ECS events a SOC would
            ingest, the latest manifest verbatim, and the exporters catalogue. */}
        <ul className="flex flex-col gap-1">
          {(
            [
              {
                key: "createPack",
                icon: PackageCheck,
                onClick: onCreatePack,
                disabled: creating,
              },
              { key: "exportSiem", icon: UploadCloud, onClick: onExportSiem },
              {
                key: "downloadManifest",
                icon: Download,
                onClick: onDownloadManifest ?? undefined,
                disabled: onDownloadManifest === null,
              },
              { key: "manageExporters", icon: FileSearch, href: "/configurer/integrations" },
            ] as {
              key: string;
              icon: typeof PackageCheck;
              onClick?: () => void;
              disabled?: boolean;
              href?: Route;
            }[]
          ).map((q) => {
            const cls =
              "flex w-full items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1.5 text-left text-[0.68rem] transition-colors hover:bg-[var(--tessera-muted)] disabled:opacity-60";
            const body = (
              <>
                <q.icon className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-green)]" />
                <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">
                  {t(`quick.${q.key}`)}
                </span>
              </>
            );
            return (
              <li key={q.key}>
                {q.href ? (
                  <Link href={q.href} className={cls}>
                    {body}
                  </Link>
                ) : (
                  <button
                    type="button"
                    onClick={q.onClick}
                    disabled={q.disabled === true}
                    className={cls}
                  >
                    {body}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      </Panel>

      {/* The journal / queue below stay demonstration (no external export). */}
      <SyntheticNotice signalId="evidence_export" compact />

      <Panel
        title={t("zone.journal")}
        info={<ExplainInfo k="zone.journal" title={t("zone.journal")} />}
        action={<ViewAll label={t("viewAll.all")} href="/prouver/audit-logs" />}
      >
        <ul className="flex flex-col gap-1.5">
          {data.export_journal.map((j, i) => (
            <li key={`${j.time}-${j.label}-${i}`} className="flex items-center gap-2 text-[0.7rem]">
              <span
                className={cn(
                  "h-1.5 w-1.5 shrink-0 rounded-full",
                  j.status === "ok"
                    ? "bg-emerald-400"
                    : j.status === "degraded"
                      ? "bg-amber-400"
                      : "bg-red-400",
                )}
              />
              <span className="min-w-0 flex-1 truncate text-[var(--tessera-text)]">{j.label}</span>
              <span className="shrink-0 tabular-nums text-[var(--tessera-text-muted)]">
                {j.time}
              </span>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel
        title={t("zone.queue")}
        info={<ExplainInfo k="zone.queue" title={t("zone.queue")} />}
        action={<ViewAll label={t("queue.viewQueue")} href="/configurer/integrations" />}
      >
        <dl className="flex flex-col gap-1.5 text-[0.7rem]">
          <KV label={t("queue.pendingSignature")} value={String(data.queue.pending_signature)} />
          <KV label={t("queue.pendingExport")} value={String(data.queue.pending_export)} />
          <KV label={t("queue.verifications")} value={String(data.queue.verifications)} />
        </dl>
      </Panel>
    </aside>
  );
}

function Footer({ t, data }: { t: T; data: Data }) {
  const f = data.footer;
  return (
    <footer className="mt-1 flex shrink-0 flex-wrap items-center gap-x-5 gap-y-1 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
      <Chip
        icon={ShieldCheck}
        tone="text-[var(--tessera-green)]"
        label={t("footer.chain", { txt: f.chain })}
      />
      <Chip icon={Database} label={t("footer.source", { src: f.source })} />
      <Chip icon={Activity} label={`${t("integrity.lastCheck")} ${data.updated_at}`} />
    </footer>
  );
}

// ── atoms ────────────────────────────────────────────────────────────────────

function Zone({
  label,
  info,
  action,
  children,
}: {
  label: string;
  info?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="shrink-0 rounded-xl border border-[var(--tessera-border)]/60 bg-[var(--tessera-surface)]/20 p-2.5">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-1 text-[0.7rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
          {label}
          {info}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function Panel({
  title,
  info,
  action,
  children,
  className,
}: {
  title: string;
  info?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3",
        className,
      )}
    >
      {title || action ? (
        <div className="mb-2 flex items-center justify-between gap-2">
          <h3 className="flex min-w-0 items-center gap-1 text-[0.8rem] font-semibold text-[var(--tessera-text)]">
            <span className="min-w-0 truncate">{title}</span>
            {info}
          </h3>
          {action}
        </div>
      ) : null}
      <div className="min-h-0 flex-1">{children}</div>
    </div>
  );
}

function KpiTile({
  kpi,
  label,
  vs,
  info,
}: { kpi: Data["kpis"][number]; label: string; vs: string; info?: ReactNode }) {
  const up = kpi.delta_label.trim().startsWith("+");
  const neutral = !/[+-]/.test(kpi.delta_label.trim().charAt(0));
  const good = up === kpi.good_is_up;
  const magnitude = kpi.delta_label.replace(/^[+-]\s*/, "");
  return (
    <div className="flex h-[104px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <p className="flex items-center gap-1 text-[0.7rem] font-medium text-[var(--tessera-text-muted)]">
        <span className="min-w-0 truncate">{label}</span>
        {info}
      </p>
      <div className="mt-1 flex items-center gap-2">
        <span className="whitespace-nowrap text-[1.4rem] font-semibold leading-none text-white">
          {kpi.value}
        </span>
        <MetricSparkline
          className="h-6 min-w-0 flex-1"
          values={kpi.series}
          tone={kpi.good_is_up ? "success" : "danger"}
        />
      </div>
      <div className="mt-auto flex items-center gap-1 whitespace-nowrap text-[0.62rem] font-medium">
        <span
          className={
            neutral
              ? "text-[var(--tessera-text-muted)]"
              : good
                ? "text-[var(--tessera-green)]"
                : "text-red-300"
          }
        >
          {neutral ? "" : up ? "▲ " : "▼ "}
          {magnitude}
        </span>
        <span className="text-[var(--tessera-text-muted)]">{vs}</span>
      </div>
    </div>
  );
}

function Donut({
  slices,
  total,
  caption,
  labelOf,
  showCount,
}: {
  slices: Data["artifacts_distribution"];
  total: number;
  caption: string;
  labelOf: (key: string) => string;
  showCount?: boolean;
}) {
  const sum = slices.reduce((s, x) => s + x.count, 0) || 1;
  const R = 40;
  const C = 2 * Math.PI * R;
  let off = 0;
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-[108px] w-[108px] shrink-0">
        <svg viewBox="0 0 108 108" className="h-full w-full -rotate-90" aria-hidden="true">
          <circle
            cx="54"
            cy="54"
            r={R}
            fill="none"
            stroke="var(--tessera-border)"
            strokeWidth="9"
          />
          {slices.map((s) => {
            const frac = s.count / sum;
            const seg = { dash: frac * C, gap: C - frac * C, o: -off * C };
            off += frac;
            return (
              <circle
                key={s.key}
                cx="54"
                cy="54"
                r={R}
                fill="none"
                stroke={s.color}
                strokeWidth="9"
                strokeDasharray={`${seg.dash} ${seg.gap}`}
                strokeDashoffset={seg.o}
              />
            );
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center overflow-hidden">
          <span className="max-w-[52px] truncate text-base font-semibold leading-none tabular-nums text-white">
            {total}
          </span>
          <span className="line-clamp-2 max-w-[52px] break-words text-center text-[0.46rem] uppercase leading-tight text-[var(--tessera-text-muted)]">
            {caption}
          </span>
        </div>
      </div>
      <ul className="flex min-w-0 flex-1 flex-col gap-0.5 text-[0.64rem]">
        {slices.map((s) => (
          <li key={s.key} className="flex flex-col gap-0.5">
            <span className="flex min-w-0 items-center gap-1">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: s.color }} />
              <span className="min-w-0 truncate text-[var(--tessera-text)]">{labelOf(s.key)}</span>
            </span>
            <span className="pl-2.5 tabular-nums text-[var(--tessera-text-muted)]">
              {showCount ? `${s.count} · ` : ""}
              {s.pct}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Badge({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded border px-1.5 py-0.5 text-[0.58rem] font-medium",
        className,
      )}
    >
      {children}
    </span>
  );
}

function KV({
  label,
  value,
  mono,
  tone,
}: { label: string; value: string; mono?: boolean; tone?: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="shrink-0 text-[var(--tessera-text-muted)]">{label}</span>
      <span
        className={cn(
          "min-w-0 truncate text-right text-[var(--tessera-text)]",
          mono && "font-mono text-[0.64rem]",
          tone,
        )}
      >
        {value}
      </span>
    </div>
  );
}

function ViewAll({ label, href }: { label: string; href: Route }) {
  return (
    <Link
      href={href}
      className="flex shrink-0 items-center gap-0.5 text-[0.66rem] font-medium text-[#87bfff] hover:text-[#a9d2ff]"
    >
      {label} <ChevronRight className="h-3 w-3" />
    </Link>
  );
}

function Chip({
  icon: Icon,
  label,
  tone,
}: { icon: typeof Activity; label: string; tone?: string }) {
  return (
    <span className="flex min-w-0 items-center gap-1.5 whitespace-nowrap">
      <Icon className={cn("h-3.5 w-3.5 shrink-0", tone)} />
      <span className="truncate">{label}</span>
    </span>
  );
}
