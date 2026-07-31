"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Bookmark,
  CalendarDays,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  Clock,
  Download,
  FileText,
  Filter,
  GitBranch,
  History,
  Info,
  Lock,
  MessageSquare,
  Package,
  RotateCcw,
  Search,
  ShieldCheck,
  ShieldX,
  Terminal,
  X,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { CalendarPopover } from "@/components/cockpit/calendar-popover";
import { LiveBeacon } from "@/components/cockpit/live-beacon";
import { MetricInfo } from "@/components/cockpit/metric-info";
import { Skeleton } from "@/components/ui/skeleton";
import { Truncate } from "@/components/ui/truncate";
import { Link } from "@/i18n/navigation";
import { fetchEtatADate, saveEtatSnapshot } from "@/lib/api/client";
import type { EtatADate as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

type Row = NonNullable<Data["table"]>["rows"][number];
type GovCard = NonNullable<Data["guardrails"]>;
type SortDir = "asc" | "desc";

const TYPE_TONE: Record<string, string> = {
  violet: "border-[#8b7cf0]/30 bg-[#8b7cf0]/15 text-[var(--tessera-fg-accent)]",
  blue: "border-[#4c8bf5]/30 bg-[#4c8bf5]/15 text-[var(--tessera-fg-info)]",
};
const KIND_DOT: Record<string, string> = {
  info: "bg-sky-400",
  ok: "bg-emerald-400",
  warn: "bg-amber-400",
};
// Diff colour code (matches the normative): added/removed/changed/unchanged.
const DIFF_GLYPH: Record<string, string> = {
  added: "+",
  removed: "-",
  changed: "~",
  unchanged: "=",
};
const DIFF_TONE: Record<string, string> = {
  added: "text-[var(--tessera-fg-success)]",
  removed: "text-[var(--tessera-fg-danger)]",
  changed: "text-[var(--tessera-fg-warning)]",
  unchanged: "text-[var(--tessera-text-muted)]",
};
const ROWS_PER_PAGE_OPTS = [10, 25, 50];

function useDismiss(open: boolean, onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);
  return ref;
}

/** datetime-local value (browser-local) -> ISO instant, or null when empty. */
function toIso(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

/** ISO instant -> datetime-local value in browser-local time (for the input). */
function toLocalInput(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const off = d.getTimezoneOffset() * 60_000;
  return new Date(d.getTime() - off).toISOString().slice(0, 16);
}

/** A reference code "RES-2026-06-10-1620" -> the ISO instant it encodes. */
function refToIso(ref: string): string | null {
  const m = ref.trim().match(/RES-(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})/i);
  if (!m) return null;
  const [, y, mo, d, h, mi] = m;
  const local = new Date(Number(y), Number(mo) - 1, Number(d), Number(h), Number(mi));
  return Number.isNaN(local.getTime()) ? null : local.toISOString();
}

function esc(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/** Build a clean, printable opposable-evidence report (browser "Save as PDF"). */
function buildReportHtml(data: Data): string {
  const m = data.meta;
  const integ = data.integrity;
  const orig = data.original;
  const opp = data.opposability;
  const rows = data.table?.rows ?? [];
  const metaRows = [
    ["Reference", m?.ref_code],
    ["Etat a la date", m?.as_of_label],
    ["Tenant", m?.tenant],
    ["Agent", m?.agent],
    ["Source du contexte", m?.context_source],
    ["Fuseau horaire", m?.timezone],
  ]
    .filter(([, v]) => v)
    .map(([k, v]) => `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`)
    .join("");
  const integRows = integ
    ? [
        [integ.verified_label, integ.verified ? "OUI" : "NON"],
        ["Chaine d'audit", integ.chain_label],
        ["Couverture de l'index", integ.coverage],
        ["Sondage de test", integ.test_query],
        ["Dernier sync", integ.last_sync],
      ]
        .filter(([, v]) => v)
        .map(([k, v]) => `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`)
        .join("")
    : "";
  const sourceRows = rows
    .map(
      (r) =>
        `<tr><td>${esc(r.source)}</td><td>${esc(r.type)}</td><td>${esc(r.version)}</td>` +
        `<td>${esc(r.accessible_until)}</td><td>${esc(r.status_label)}</td></tr>`,
    )
    .join("");
  // The report's seal is honest: only a verified QUALIFIED seal earns "Etat opposable" (register §9).
  const sealText =
    opp?.badge === "scelle_opposable"
      ? "SCELLE - Etat opposable"
      : opp?.badge === "scelle_non_qualifie"
        ? "SCELLE (non qualifie)"
        : opp?.badge === "non_scelle"
          ? "NON SCELLE"
          : opp?.badge === "integrite_partielle"
            ? "Integrite partielle"
            : "";
  const sealCls =
    opp?.badge === "scelle_opposable" || opp?.badge === "scelle_non_qualifie"
      ? "seal"
      : "seal partial";
  const sealed = sealText ? `<span class="${sealCls}">${esc(sealText)}</span>` : "";
  return `<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>Rapport d'etat opposable - ${esc(m?.ref_code ?? "")}</title>
<style>
  body{font:13px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;color:#111;margin:32px;}
  h1{font-size:20px;margin:0 0 2px;} h2{font-size:14px;margin:24px 0 8px;border-bottom:1px solid #ddd;padding-bottom:4px;}
  .sub{color:#555;margin:0 0 12px;}
  .seal{display:inline-block;margin-left:10px;padding:2px 8px;border:1px solid #1a7f4b;color:#1a7f4b;border-radius:999px;font-size:11px;font-weight:600;vertical-align:middle;}
  .seal.partial{border-color:#b45309;color:#b45309;}
  table{border-collapse:collapse;width:100%;margin:6px 0;} th,td{border:1px solid #e2e2e2;padding:6px 8px;text-align:left;vertical-align:top;}
  th{background:#f6f6f6;white-space:nowrap;width:200px;} .src th{width:auto;}
  .qa{border:1px solid #e2e2e2;border-radius:6px;padding:10px;background:#fafafa;}
  .qa .q{font-weight:600;} .qa .a{margin-top:6px;white-space:pre-wrap;}
  footer{margin-top:28px;color:#888;font-size:11px;}
</style></head><body>
<h1>Rapport d'etat opposable ${sealed}</h1>
<p class="sub">Reconstitution de l'etat accessible et applicable par l'agent a la date et heure donnees.</p>
<p class="sub" style="font-size:11px;">Statut attribue uniquement apres verification reussie.${opp?.provider_label ? ` ${esc(opp.provider_label)}.` : ""}</p>
<h2>Contexte de la reconstitution</h2>
<table>${metaRows}</table>
${integRows ? `<h2>Integrite & preuve</h2><table>${integRows}</table>` : ""}
${
  orig?.available
    ? `<h2>${esc(orig.title)} (${esc(orig.ref_code ?? "")})</h2><div class="qa"><div class="q">Q : ${esc(orig.question)}</div><div class="a">R : ${esc(orig.answer)}</div></div>`
    : ""
}
${
  sourceRows
    ? `<h2>${esc(data.table?.title ?? "Sources accessibles a T")}</h2><table class="src"><tr><th>Source</th><th>Type</th><th>Version</th><th>Accessible jusqu'a</th><th>Statut</th></tr>${sourceRows}</table>`
    : ""
}
<footer>Genere le ${esc(new Date().toLocaleString("fr-FR"))} - Tessera - document probatoire reproductible (meme T => meme etat).</footer>
</body></html>`;
}

export function EtatADate() {
  const t = useTranslations("etatADate");
  const locale = useLocale();
  const qc = useQueryClient();
  // Per-source scope carried in the URL (`?sources=`), set from the Sources
  // drawer's "Voir à date" link. Empty = no scope (all sources).
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const sources = searchParams.get("sources") || null;
  // Per-agent scope (TE-01 owed param, closed): URL-derived like ?sources=,
  // so a per-agent reconstruction is deep-linkable and shareable.
  const agentScope = searchParams.get("agent") || null;
  const setAgentScope = (value: string | null) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set("agent", value);
    } else {
      params.delete("agent");
    }
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname);
  };
  // The instant T is URL-derived (`?asof=`), like `?sources=` and `?agent=`:
  // a reconstruction at T is deep-linkable and shareable, and the rail never
  // holds it in local state (registre §5 — the TE-01 owed param, closed).
  const asOf = searchParams.get("asof") || null;
  const setAsOf = (value: string | null) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set("asof", value);
    } else {
      params.delete("asof");
    }
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname);
  };
  // Draft instant (date + time) from the premium picker; empty = none picked.
  // Seeded from a deep-linked `?asof=` so the picker shows the instant it serves.
  const [draft, setDraft] = useState(() => (asOf ? toLocalInput(asOf) : ""));
  const [refInput, setRefInput] = useState("");
  const [search, setSearch] = useState("");
  const [typeF, setTypeF] = useState("all");
  const [statusF, setStatusF] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);

  const { data } = useQuery({
    queryKey: ["etat-a-date", asOf, sources, agentScope, locale],
    queryFn: ({ signal }) => fetchEtatADate(asOf, sources, agentScope, locale, signal),
    staleTime: 30_000,
  });

  const saveSnapshot = useMutation({
    mutationFn: () => saveEtatSnapshot(asOf, sources, agentScope, locale),
    onSuccess: (fresh) =>
      qc.setQueryData(["etat-a-date", asOf, sources, agentScope, locale], fresh),
  });

  function reconstruct() {
    setAsOf(refToIso(refInput) ?? toIso(draft));
  }

  function goLive() {
    setDraft("");
    setRefInput("");
    setAsOf(null);
  }

  function reloadAt(snapAsOf: string | null) {
    setAsOf(snapAsOf);
    setDraft(snapAsOf ? toLocalInput(snapAsOf) : "");
    setRefInput("");
  }

  function downloadReport() {
    if (!data) return;
    const html = buildReportHtml(data);
    const win = window.open("", "_blank");
    if (!win) return;
    win.document.open();
    win.document.write(html);
    win.document.close();
    // Let the new document lay out before invoking the print -> "Save as PDF" dialog.
    win.addEventListener("load", () => win.print());
  }

  const allRows = data?.table?.rows ?? [];
  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return allRows.filter(
      (r) =>
        (typeF === "all" || r.type_key === typeF) &&
        (statusF === "all" || r.status === statusF) &&
        (q === "" || r.source.toLowerCase().includes(q)),
    );
  }, [allRows, search, typeF, statusF]);

  const detail = selected ? (allRows.find((r) => r.key === selected) ?? null) : null;

  return (
    <div className="relative flex flex-col gap-2.5 pb-2 text-[var(--tessera-text)]">
      {/* Banner + page actions share one row (no wasted line). */}
      <div className="flex flex-wrap items-stretch gap-3">
        {data?.meta?.banner ? (
          <Banner text={data.meta.banner} className="min-w-0 flex-1" />
        ) : (
          <div className="flex-1" />
        )}
        <div className="flex shrink-0 items-center gap-2">
          {/* The active time-mode, always visible (registre §5): Live or the
              reconstruction instant, worded by the backend (`meta.as_of_label`). */}
          {data?.meta?.as_of_label ? (
            // Rail grammar (registre §5): a chosen instant wears champagne —
            // never violet — and Live carries the heartbeat, not a static dot.
            <span
              className={cn(
                "inline-flex h-9 items-center gap-1.5 rounded-md border px-3 text-xs",
                asOf === null
                  ? "border-[var(--tessera-border)] bg-[var(--tessera-surface)] text-[var(--tessera-text-muted)]"
                  : "border-gold-500/45 bg-gold-500/[0.12] text-gold-700 dark:text-gold-200",
              )}
            >
              {asOf === null ? (
                <LiveBeacon />
              ) : (
                <span className="h-1.5 w-1.5 rounded-full bg-gold-400" />
              )}
              {data.meta.as_of_label}
            </span>
          ) : null}
          <OpposabilityBadge opp={data?.opposability} t={t} />
          <button
            type="button"
            onClick={() => saveSnapshot.mutate()}
            disabled={!data?.available || saveSnapshot.isPending}
            className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 text-xs text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)] disabled:opacity-50"
          >
            <Bookmark className="h-4 w-4" />
            {saveSnapshot.isPending
              ? t("saving")
              : saveSnapshot.isSuccess
                ? t("saved")
                : t("saveSnapshot")}
          </button>
          <button
            type="button"
            onClick={downloadReport}
            disabled={!data?.available}
            className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 text-xs text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)] disabled:opacity-50"
          >
            <Download className="h-4 w-4" /> {t("downloadReport")}
          </button>
        </div>
      </div>

      <ControlBar
        t={t}
        draft={draft}
        onDraft={setDraft}
        onLive={goLive}
        isLive={asOf === null}
        refInput={refInput}
        onRefInput={setRefInput}
        agentScope={agentScope}
        onAgentScope={setAgentScope}
        onReconstruct={reconstruct}
        meta={data?.meta}
      />

      {data?.meta?.scope ? <ScopeBar t={t} scope={data.meta.scope} /> : null}

      {data === undefined ? (
        <EtatSkeleton />
      ) : !data.available ? (
        <div className="flex min-h-[50vh] items-center justify-center text-sm text-[var(--tessera-text-muted)]">
          {t("unavailable")}
        </div>
      ) : (
        <div className="grid gap-2.5 xl:grid-cols-12">
          {/* Left content column: reconstruction + governance cards + sources */}
          <div className="flex flex-col gap-2.5 xl:col-span-8">
            <div className="grid gap-2.5 md:grid-cols-3">
              <Reconstructed data={data} className="md:col-span-1" />
              <Original data={data} className="md:col-span-2" />
            </div>
            <div className="grid gap-2.5 md:grid-cols-3">
              <GovCardView
                t={t}
                card={data.guardrails}
                icon={ShieldCheck}
                iconClass="text-[var(--tessera-fg-success)]"
              />
              <GovCardView
                t={t}
                card={data.prompt_model}
                icon={Terminal}
                iconClass="text-[var(--tessera-fg-warning)]"
              />
              <GovCardView
                t={t}
                card={data.release}
                icon={Package}
                iconClass="text-[var(--tessera-fg-teal)]"
              />
            </div>
            <SourcesTable
              t={t}
              title={data.table?.title ?? ""}
              allRows={allRows}
              rows={rows}
              search={search}
              onSearch={setSearch}
              typeF={typeF}
              onTypeF={setTypeF}
              statusF={statusF}
              onStatusF={setStatusF}
              selected={selected}
              onSelect={setSelected}
            />
          </div>

          {/* Right rail: chronology, integrity, audit pieces, snapshots */}
          <div className="flex flex-col gap-2.5 xl:col-span-4">
            <Chronology data={data} />
            <Integrity data={data} />
            <Handoffs data={data} />
            <AuditPieces data={data} />
            <Snapshots data={data} onReload={reloadAt} />
          </div>
        </div>
      )}

      {detail ? <SourceDrawer t={t} row={detail} onClose={() => setSelected(null)} /> : null}
    </div>
  );
}

type T = ReturnType<typeof useTranslations<"etatADate">>;

// ── banner + control bar ──────────────────────────────────────────────────────

function Banner({ text, className }: { text: string; className?: string }) {
  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-lg border border-[#9a5f18]/50 bg-[#3e260c]/30 p-2.5 text-[0.72rem] text-[var(--tessera-fg-warning)]",
        className,
      )}
    >
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-[var(--tessera-fg-warning)]" />
      <span>{text}</span>
    </div>
  );
}

type Scope = NonNullable<NonNullable<Data["meta"]>["scope"]>;

/** Per-source scope chip: shows the active source filter + a reset to all. */
function ScopeBar({ t, scope }: { t: T; scope: Scope }) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-[#7c5cf5]/40 bg-[#6d4aed]/10 px-3 py-2 text-[0.72rem]">
      <Filter className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-fg-accent)]" />
      <span className="text-[var(--tessera-text-muted)]">{t("scopeLabel")}</span>
      <span className="font-medium text-[var(--tessera-text)]">{scope.labels.join(" · ")}</span>
      <Link
        href="/prouver/etat-a-date"
        className="ml-auto flex items-center gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-2 py-1 text-[0.68rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
      >
        <X className="h-3 w-3" /> {t("scopeClear")}
      </Link>
    </div>
  );
}

// The selector folds to a real fleet id; this sentinel keeps the historical default.
const DEFAULT_AGENT_OPTION = "— défaut —";

const pad2 = (n: number) => String(n).padStart(2, "0");
/** Date -> "YYYY-MM-DDTHH:MM" (local), the datetime-local contract. */
function fmtLocal(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

/**
 * Premium date+time picker — the SHARED CalendarPopover in an `sr01-menu` shell
 * (the rail grammar): never a second homemade month grid, never a native
 * datetime panel, and champagne — not violet — for a chosen instant. Draft
 * semantics are the caller's: `value` is a local "YYYY-MM-DDTHH:MM" string that
 * the page applies with "Reconstituer", so the popover stays open after a day
 * pick (day + time are tuned together, then reconstructed).
 */
function DateTimePicker({
  t,
  value,
  onChange,
  onLive,
  isLive,
}: {
  t: T;
  value: string;
  onChange: (v: string) => void;
  onLive: () => void;
  isLive: boolean;
}) {
  const locale = useLocale();
  const [open, setOpen] = useState(false);
  const ref = useDismiss(open, () => setOpen(false));
  const selected = value ? new Date(value) : null;
  const time = value ? value.slice(11, 16) : "12:00";

  function pickDay(day: string) {
    const [y = 1970, m = 1, d = 1] = day.split("-").map(Number);
    const [hh = "12", mm = "00"] = time.split(":");
    onChange(fmtLocal(new Date(y, m - 1, d, +hh, +mm)));
  }
  function pickTime(value_: string) {
    const base = selected ?? new Date();
    const [hh = "12", mm = "00"] = value_.split(":");
    onChange(fmtLocal(new Date(base.getFullYear(), base.getMonth(), base.getDate(), +hh, +mm)));
  }

  const live = isLive && !selected;
  const trigger =
    selected != null
      ? new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(
          selected,
        )
      : t("now");

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "flex h-9 w-[15rem] items-center gap-2 rounded-md border bg-[var(--tessera-bg)] px-2.5 text-left text-sm shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] transition-colors hover:border-gold-500/60",
          selected ? "border-gold-500/45 bg-gold-500/[0.08]" : "border-[var(--tessera-border)]",
        )}
      >
        <CalendarDays className="h-4 w-4 shrink-0 text-gold-600 dark:text-gold-400" />
        <span className="truncate text-[var(--tessera-text)]">{trigger}</span>
        {/* Static dot: the page's ONE heartbeat lives on the mode badge above —
            a second beating dot on the same surface would just compete with it. */}
        {live ? (
          <span className="ml-auto h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />
        ) : (
          <ChevronDown className="ml-auto h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)]" />
        )}
      </button>
      {open ? (
        <div className="sr01-menu absolute left-0 z-50 mt-1 w-[292px] rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] shadow-[0_20px_60px_rgba(0,0,0,0.42)]">
          <CalendarPopover
            selectedDate={selected ?? new Date()}
            onPick={pickDay}
            labels={{ prevMonth: t("prevMonth"), nextMonth: t("nextMonth") }}
            className="w-full border-0 bg-transparent shadow-none"
          />
          <div className="flex items-center justify-between gap-2 border-t border-[var(--tessera-border)] px-3 pb-3 pt-2.5">
            <label className="flex items-center gap-2 text-[0.72rem] text-[var(--tessera-text-muted)]">
              <Clock className="h-3.5 w-3.5" />
              <input
                type="time"
                value={time}
                onChange={(e) => pickTime(e.target.value)}
                aria-label={t("dateTime")}
                className="h-8 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-2 text-xs text-[var(--tessera-text)] outline-none [color-scheme:dark]"
              />
            </label>
            <button
              type="button"
              onClick={() => {
                onLive();
                setOpen(false);
              }}
              className="flex items-center gap-1 rounded-md border border-[var(--tessera-border)] px-2.5 py-1 text-[0.7rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
            >
              <Clock className="h-3 w-3" /> {t("now")}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ControlBar({
  t,
  draft,
  onDraft,
  onLive,
  isLive,
  refInput,
  onRefInput,
  agentScope,
  onAgentScope,
  onReconstruct,
  meta,
}: {
  t: T;
  draft: string;
  onDraft: (v: string) => void;
  onLive: () => void;
  isLive: boolean;
  refInput: string;
  onRefInput: (v: string) => void;
  agentScope: string | null;
  onAgentScope: (v: string | null) => void;
  onReconstruct: () => void;
  meta: Data["meta"];
}) {
  return (
    <div className="flex flex-wrap items-end gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      {/* Single-tenant build: the tenant is a fact to read, never a fake select. */}
      <Field label={t("tenant")}>
        <span className="flex h-9 items-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-sm text-[var(--tessera-text)]">
          {meta?.tenant ?? "-"}
        </span>
      </Field>
      <SelectField
        label={t("agent")}
        value={agentScope ?? DEFAULT_AGENT_OPTION}
        options={[DEFAULT_AGENT_OPTION, ...(meta?.agents ?? [])]}
        onChange={(v) => onAgentScope(v === DEFAULT_AGENT_OPTION ? null : v)}
      />
      <Field label={t("dateTime")}>
        <DateTimePicker t={t} value={draft} onChange={onDraft} onLive={onLive} isLive={isLive} />
      </Field>
      <Field label={t("reference")}>
        <input
          value={refInput}
          onChange={(e) => onRefInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") onReconstruct();
          }}
          placeholder={t("refPlaceholder")}
          aria-label={t("reference")}
          className="h-9 w-56 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-sm text-[var(--tessera-text)] outline-none focus:border-[#7c5cf5]"
        />
      </Field>
      <Field label={t("contextSource")}>
        <span className="flex h-9 items-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-sm text-[var(--tessera-text)]">
          {meta?.context_source ?? "-"}
        </span>
      </Field>
      <button
        type="button"
        onClick={onReconstruct}
        className="ml-auto flex h-9 items-center gap-2 rounded-md border border-[#7c5cf5] bg-[#6d4aed] px-4 text-xs font-medium text-white hover:bg-[#7c5cf5]"
      >
        <History className="h-4 w-4" /> {t("reconstruct")}
      </button>
    </div>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <Field label={label}>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-label={label}
          className="h-9 w-44 appearance-none rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] pr-8 pl-3 text-sm text-[var(--tessera-text)] outline-none focus:border-[#7c5cf5]"
        >
          {options.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
        <ChevronDown className="-translate-y-1/2 pointer-events-none absolute top-1/2 right-2.5 h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
      </div>
    </Field>
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

// ── panels ───────────────────────────────────────────────────────────────────

function Panel({
  title,
  icon: Icon,
  iconClass = "text-[var(--tessera-fg-accent)]",
  info,
  right,
  children,
  className,
}: {
  title: string;
  icon?: typeof ShieldCheck;
  iconClass?: string;
  /** Optional ⓘ explainer rendered next to the panel title. */
  info?: React.ReactNode;
  right?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      data-slot="card"
      className={cn(
        "flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3",
        className,
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="flex min-w-0 items-center gap-1.5 text-[0.78rem] font-semibold text-[var(--tessera-text)]">
          {Icon ? <Icon className={cn("h-4 w-4 shrink-0", iconClass)} /> : null}
          <span className="min-w-0 truncate">{title}</span>
          {info}
        </h2>
        {right}
      </div>
      {children}
    </section>
  );
}

/** A ⓘ for an état-à-date panel, reading etatADate.explain.<k>.{what,how,source?}. */
function SectionInfo({ title, explainKey }: { title: string; explainKey: string }) {
  const te = useTranslations("etatADate.explain");
  return (
    <MetricInfo
      title={title}
      what={te(`${explainKey}.what`)}
      how={te(`${explainKey}.how`)}
      source={te.has(`${explainKey}.source`) ? te(`${explainKey}.source`) : undefined}
    />
  );
}

/**
 * Register §9 opposability badge (TE-01) — computed live from the backend's tree + Hica-seal
 * verdict, never cosmetic (TESS-0015). "Scellé · opposable" is reserved for a verified QUALIFIED
 * (eIDAS) seal; a verified non-qualified seal is "Scellé (non qualifié)"; absent / stale /
 * unverifiable ⇒ "Intégrité partielle"; broken content ⇒ "Non scellé". The mandatory mention
 * renders beneath the badge; provider + qualification are in the tooltip. This replaces the
 * pre-existing over-claim that showed "Scellé" on chain integrity alone (Q6).
 */
function OpposabilityBadge({
  opp,
  t,
}: {
  opp: Data["opposability"];
  t: ReturnType<typeof useTranslations>;
}) {
  const badge = opp?.badge ?? "verification_en_cours";
  const tone =
    badge === "scelle_opposable"
      ? "border-emerald-500/40 bg-emerald-500/10 text-[var(--tessera-fg-success)]"
      : badge === "scelle_non_qualifie"
        ? "border-emerald-500/30 bg-emerald-500/5 text-[var(--tessera-fg-success)]/80"
        : badge === "non_scelle"
          ? "border-red-500/40 bg-red-500/10 text-[var(--tessera-fg-danger)]"
          : badge === "integrite_partielle"
            ? "border-amber-500/40 bg-amber-500/10 text-[var(--tessera-fg-warning)]"
            : "border-[var(--tessera-border)] text-[var(--tessera-text-muted)]";
  const Icon =
    badge === "non_scelle" ? ShieldX : badge === "integrite_partielle" ? GitBranch : Lock;
  const label = opp?.badge_label ?? t("sealVerifying");
  const mention = opp?.mention ?? "";
  const provider = opp?.provider_label ?? "";
  return (
    <div className="flex flex-col items-end gap-0.5">
      <span
        title={provider ? `${provider} — ${mention}` : mention}
        className={`flex h-9 items-center gap-1.5 rounded-md border px-2.5 text-[0.72rem] font-medium ${tone}`}
      >
        <Icon className="h-3.5 w-3.5" /> {label}
      </span>
      {mention ? (
        <span className="max-w-[15rem] text-right text-[0.56rem] leading-tight text-[var(--tessera-text-muted)]">
          {mention}
        </span>
      ) : null}
    </div>
  );
}

function VerifiedBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={cn(
        "inline-flex w-fit items-center gap-1 rounded-full border px-2 py-0.5 text-[0.6rem] font-medium",
        ok
          ? "border-emerald-500/30 bg-emerald-500/15 text-[var(--tessera-fg-success)]"
          : "border-red-500/30 bg-red-500/15 text-[var(--tessera-fg-danger)]",
      )}
    >
      {ok ? <ShieldCheck className="h-3.5 w-3.5" /> : null}
      {label}
    </span>
  );
}

function Reconstructed({ data, className }: { data: Data; className?: string }) {
  const t = useTranslations("etatADate");
  const r = data.reconstructed;
  if (!r) return null;
  return (
    <Panel
      title={r.title}
      icon={FileText}
      iconClass="text-[var(--tessera-fg-accent)]"
      info={<SectionInfo title={r.title} explainKey="reconstructed" />}
      right={<VerifiedBadge ok={r.verified} label={r.verified_label} />}
      className={className}
    >
      <p className="text-[0.72rem] text-[var(--tessera-text-muted)]">
        {t("snapshotLabel")} ·{" "}
        <span className="font-mono text-[var(--tessera-text)]">{r.snapshot_id}</span>
      </p>
      <p className="mt-3 text-[0.68rem] text-[var(--tessera-text-muted)]">{r.built_label}</p>
    </Panel>
  );
}

function Original({ data, className }: { data: Data; className?: string }) {
  const t = useTranslations("etatADate");
  const o = data.original;
  if (!o) return null;
  return (
    <Panel
      title={o.title}
      icon={MessageSquare}
      iconClass="text-[var(--tessera-fg-info)]"
      info={<SectionInfo title={o.title} explainKey="original" />}
      className={className}
    >
      <p className="text-[0.62rem] text-[var(--tessera-text-muted)]">
        {t("referenceLabel")} · <span className="font-mono">{o.ref_code}</span>
      </p>
      {o.available ? (
        <div className="mt-2 flex flex-col gap-2 text-[0.74rem]">
          <div>
            <p className="mb-0.5 text-[0.74rem] font-semibold text-[var(--tessera-text)]">
              {t("question")}
            </p>
            <Truncate full={o.question} className="text-[var(--tessera-text-muted)]">
              {o.question}
            </Truncate>
          </div>
          <div>
            <p className="mb-0.5 text-[0.74rem] font-semibold text-[var(--tessera-text)]">
              {t("answer")}
            </p>
            <p className="text-[var(--tessera-text-muted)]">{o.answer}</p>
          </div>
          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 border-t border-[var(--tessera-border)]/50 pt-2 text-[0.62rem] text-[var(--tessera-text-muted)]">
            <span>
              {t("timestampLabel")}{" "}
              <span className="text-[var(--tessera-text)]">{o.timestamp}</span>
            </span>
            <span>
              {t("sessionLabel")}{" "}
              <span className="font-mono text-[var(--tessera-text)]">{o.session}</span>
            </span>
          </div>
          <CtaLink label={o.cta} href={o.cta_href} />
        </div>
      ) : (
        <p className="mt-2 text-[0.74rem] text-[var(--tessera-text-muted)]">{t("noOriginal")}</p>
      )}
    </Panel>
  );
}

function GovCardView({
  t,
  card,
  icon,
  iconClass,
  className,
}: {
  t: T;
  card?: GovCard;
  icon: typeof ShieldCheck;
  iconClass?: string;
  className?: string;
}) {
  if (!card) return null;
  return (
    <Panel
      title={card.title}
      icon={icon}
      iconClass={iconClass}
      info={<SectionInfo title={card.title} explainKey="govCard" />}
      className={className}
    >
      <dl className="flex flex-col gap-1.5 text-[0.72rem]">
        {card.rows.map((r) => (
          <div key={r.label} className="flex h-[1.15rem] items-center justify-between gap-2">
            <dt className="shrink-0 whitespace-nowrap text-[var(--tessera-text-muted)]">
              {r.label}
            </dt>
            <Truncate
              as="dd"
              full={r.value}
              className="text-right font-medium text-[var(--tessera-text)]"
            >
              {r.value}
            </Truncate>
          </div>
        ))}
      </dl>
      <div className="mt-2.5 border-t border-[var(--tessera-border)]/60 pt-2">
        <p className="text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
          {t("diffVsNow")}
        </p>
        <ul className="mt-1 flex flex-col gap-1">
          {card.diff.map((d) => (
            <li
              key={d.text}
              className="flex items-start gap-1.5 text-[0.68rem] text-[var(--tessera-text)]"
            >
              <span
                className={cn(
                  "w-2.5 shrink-0 text-center font-semibold tabular-nums",
                  DIFF_TONE[d.kind] ?? "text-[var(--tessera-text-muted)]",
                )}
                aria-hidden
              >
                {DIFF_GLYPH[d.kind] ?? "="}
              </span>
              {d.text}
            </li>
          ))}
        </ul>
      </div>
      <Link
        href={card.cta_href as never}
        className="mt-auto flex items-center gap-1 self-start pt-2.5 text-[0.68rem] text-[var(--tessera-fg-accent)] hover:text-[var(--tessera-text-strong)]"
      >
        {card.cta} <ChevronRight className="h-3.5 w-3.5" />
      </Link>
    </Panel>
  );
}

function Chronology({ data, className }: { data: Data; className?: string }) {
  const t = useTranslations("etatADate");
  const tl = data.timeline;
  if (!tl) return null;
  return (
    <Panel
      title={tl.title}
      icon={History}
      iconClass="text-[var(--tessera-fg-accent)]"
      info={<SectionInfo title={tl.title} explainKey="chronology" />}
      className={className}
    >
      {tl.rows.length === 0 ? (
        <p className="py-1 text-[0.72rem] text-[var(--tessera-text-muted)]">{t("noTimeline")}</p>
      ) : (
        <ul className="flex flex-col gap-2.5">
          {tl.rows.map((r, i) => (
            <li key={`${r.time}-${i}`} className="relative flex gap-2.5 text-[0.72rem]">
              {/* connecting thread, centered on the header icon column (w-4 -> 8px) */}
              {i < tl.rows.length - 1 ? (
                <span
                  aria-hidden
                  className="-translate-x-1/2 absolute top-[7px] left-2 h-[calc(100%+0.625rem)] w-px bg-[var(--tessera-border)]"
                />
              ) : null}
              <span className="flex w-4 shrink-0 justify-center">
                <span
                  className={cn(
                    "z-10 mt-1 h-1.5 w-1.5 rounded-full ring-2 ring-[var(--tessera-surface)]",
                    KIND_DOT[r.kind] ?? "bg-slate-400",
                  )}
                />
              </span>
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
      {tl.cta && tl.cta_href ? <CtaLink label={tl.cta} href={tl.cta_href} /> : null}
    </Panel>
  );
}

function CtaLink({ label, href }: { label: string; href: string }) {
  return (
    <Link
      href={href as never}
      className="mt-2.5 flex items-center gap-1 self-start text-[0.68rem] text-[var(--tessera-fg-accent)] hover:text-[var(--tessera-text-strong)]"
    >
      {label} <ChevronRight className="h-3.5 w-3.5" />
    </Link>
  );
}

function Integrity({ data }: { data: Data }) {
  const it = data.integrity;
  if (!it) return null;
  const rows: [string, string][] = [
    ["Indice snapshot", it.snapshot_id],
    ["Couverture des sources", it.coverage],
    ["Requête de test", it.test_query],
    ["Dernière synchro avant T", it.last_sync],
    ["Journalisation", it.chain_label],
  ];
  return (
    <Panel
      title={it.title}
      icon={ShieldCheck}
      iconClass="text-[var(--tessera-fg-success)]"
      info={<SectionInfo title={it.title} explainKey="integrity" />}
    >
      <dl className="flex flex-col gap-1.5 text-[0.72rem]">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between gap-2">
            <dt className="text-[var(--tessera-text-muted)]">{label}</dt>
            <dd className="truncate text-right font-medium tabular-nums text-[var(--tessera-text)]">
              {value}
            </dd>
          </div>
        ))}
      </dl>
      <div className="mt-2.5">
        <VerifiedBadge ok={it.verified} label={it.verified_label} />
      </div>
    </Panel>
  );
}

function AuditPieces({ data, className }: { data: Data; className?: string }) {
  const a = data.audit_pieces;
  if (!a) return null;
  return (
    <Panel
      title={a.title}
      icon={FileText}
      iconClass="text-[var(--tessera-fg-info)]"
      info={<SectionInfo title={a.title} explainKey="auditPieces" />}
      className={className}
    >
      <ul className="flex flex-col gap-2">
        {a.rows.map((r) => (
          <li key={r.href}>
            <Link
              href={r.href as never}
              className="flex items-center justify-between gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2 text-[0.72rem] text-[var(--tessera-text)] hover:border-[#7c5cf5]/50"
            >
              {r.label}
              <ChevronRight className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
            </Link>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Handoffs({ data, className }: { data: Data; className?: string }) {
  const h = data.handoffs;
  if (!h) return null;
  return (
    <Panel
      title={h.title}
      icon={ArrowRight}
      iconClass="text-[var(--tessera-fg-success)]"
      info={<SectionInfo title={h.title} explainKey="handoffs" />}
      className={className}
    >
      {h.subtitle ? (
        <p className="mb-2 text-[0.62rem] text-[var(--tessera-text-muted)]">{h.subtitle}</p>
      ) : null}
      {h.rows.length === 0 ? (
        <p className="text-[0.72rem] text-[var(--tessera-text-muted)]">
          Aucune passation jusqu'à T.
        </p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {h.rows.map((r, i) => (
            <li
              key={`${r.from}-${r.to}-${r.at}-${i}`}
              className="rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2 text-[0.72rem]"
            >
              <span className="flex items-center gap-1.5 font-medium text-[var(--tessera-text)]">
                {r.from} <ArrowRight className="h-3.5 w-3.5 text-[var(--tessera-fg-success)]" />{" "}
                {r.to}
              </span>
              <span className="text-[0.62rem] text-[var(--tessera-text-muted)]">
                {r.at} · {r.reason}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

// ── sources table (filters + sort + pagination + row-click drawer) ────────────

const COLS: { key: keyof Row; labelKey: string; width: string; align?: "right" }[] = [
  { key: "source", labelKey: "source", width: "30%" },
  { key: "type", labelKey: "type", width: "16%" },
  { key: "version", labelKey: "colVersion", width: "18%" },
  { key: "chunks", labelKey: "colDocuments", width: "12%", align: "right" },
  { key: "accessible_until", labelKey: "colAccessibleUntil", width: "12%" },
  { key: "status", labelKey: "status", width: "12%" },
];

function sortValue(row: Row, key: keyof Row): string | number {
  const v = row[key];
  return typeof v === "number" ? v : String(v ?? "").toLowerCase();
}

function SourcesTable({
  t,
  title,
  allRows,
  rows,
  search,
  onSearch,
  typeF,
  onTypeF,
  statusF,
  onStatusF,
  selected,
  onSelect,
  className,
}: {
  t: T;
  title: string;
  allRows: Row[];
  rows: Row[];
  search: string;
  onSearch: (v: string) => void;
  typeF: string;
  onTypeF: (v: string) => void;
  statusF: string;
  onStatusF: (v: string) => void;
  selected: string | null;
  onSelect: (key: string | null) => void;
  className?: string;
}) {
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const [sortCol, setSortCol] = useState<number | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const sorted = useMemo(() => {
    if (sortCol === null) return rows;
    const key = COLS[sortCol]?.key ?? "source";
    return [...rows].sort((a, b) => {
      const va = sortValue(a, key);
      const vb = sortValue(b, key);
      const cmp =
        typeof va === "number" && typeof vb === "number"
          ? va - vb
          : String(va).localeCompare(String(vb));
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [rows, sortCol, sortDir]);

  const total = sorted.length;
  const totalPages = Math.max(1, Math.ceil(total / perPage));
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset on filter/sort/size change
  useEffect(() => setPage(1), [total, perPage, sortCol, sortDir]);
  const safePage = Math.min(page, totalPages);
  const start = (safePage - 1) * perPage;
  const pageRows = sorted.slice(start, start + perPage);

  const typeOpts = useMemo(() => {
    const m = new Map<string, string>();
    for (const r of allRows) m.set(r.type_key, r.type);
    return [...m.entries()];
  }, [allRows]);
  const statusOpts = useMemo(() => {
    const m = new Map<string, string>();
    for (const r of allRows) m.set(r.status, r.status_label);
    return [...m.entries()];
  }, [allRows]);

  function toggleSort(i: number) {
    if (i === sortCol) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortCol(i);
      setSortDir("asc");
    }
  }

  return (
    <section
      className={cn(
        "flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]",
        className,
      )}
    >
      <div className="flex flex-wrap items-center gap-2 border-b border-[var(--tessera-border)] p-3">
        <h2 className="mr-auto text-[0.78rem] font-semibold text-[var(--tessera-text)]">{title}</h2>
        <div className="relative">
          <Search className="-translate-y-1/2 pointer-events-none absolute top-1/2 left-2.5 h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
          <input
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            placeholder={t("searchPlaceholder")}
            aria-label={t("searchPlaceholder")}
            className="h-8 w-52 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] pr-2 pl-8 text-[0.72rem] text-[var(--tessera-text)] outline-none focus:border-[#7c5cf5]"
          />
        </div>
        <FilterDropdown
          label={t("filterType")}
          value={typeF}
          allLabel={t("all")}
          options={typeOpts}
          onSelect={onTypeF}
        />
        <FilterDropdown
          label={t("filterStatus")}
          value={statusF}
          allLabel={t("all")}
          options={statusOpts}
          onSelect={onStatusF}
        />
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[680px] table-fixed border-collapse text-left">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.6rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {COLS.map((c, i) => (
                <th
                  key={c.labelKey}
                  style={{ width: c.width }}
                  aria-sort={
                    sortCol === i ? (sortDir === "asc" ? "ascending" : "descending") : "none"
                  }
                  className={cn("px-3 py-2", c.align === "right" && "text-right")}
                >
                  <button
                    type="button"
                    onClick={() => toggleSort(i)}
                    className={cn(
                      "inline-flex items-center gap-1 hover:text-[var(--tessera-text)]",
                      sortCol === i && "text-[var(--tessera-text)]",
                      c.align === "right" && "flex-row-reverse",
                    )}
                  >
                    {t(c.labelKey)}
                    {sortCol === i ? (
                      <span className="text-[0.7rem]">{sortDir === "asc" ? "▲" : "▼"}</span>
                    ) : (
                      <ChevronsUpDown className="h-3 w-3 opacity-40" />
                    )}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.length === 0 ? (
              <tr>
                <td
                  colSpan={COLS.length}
                  className="px-3 py-6 text-center text-[0.72rem] text-[var(--tessera-text-muted)]"
                >
                  {t("tableEmpty")}
                </td>
              </tr>
            ) : (
              pageRows.map((r) => (
                <tr
                  key={r.key}
                  // biome-ignore lint/a11y/useSemanticElements: a table row cannot be a <button>; it opens the detail drawer
                  role="button"
                  tabIndex={0}
                  aria-label={r.source}
                  onClick={() => onSelect(r.key)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect(r.key);
                    }
                  }}
                  className={cn(
                    "cursor-pointer border-b border-[var(--tessera-border)]/50 text-[0.72rem] outline-none last:border-0 hover:bg-[var(--tessera-bg)]/50 focus-visible:bg-[var(--tessera-bg)]/60 focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-[#5fd0c6]",
                    selected === r.key && "bg-[var(--tessera-bg)]/60",
                  )}
                >
                  <td className="truncate px-3 py-2 font-medium text-[var(--tessera-text)]">
                    {r.source}
                    <span className="block text-[0.58rem] font-normal uppercase text-[var(--tessera-text-muted)]">
                      {r.langs}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={cn(
                        "rounded-full border px-2 py-0.5 text-[0.58rem]",
                        TYPE_TONE[r.type_tone] ??
                          "border-slate-500/30 bg-slate-500/15 text-[var(--tessera-text-muted)]",
                      )}
                    >
                      {r.type}
                    </span>
                  </td>
                  <td className="px-3 py-2 tabular-nums text-[var(--tessera-text-muted)]">
                    {r.version}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-[var(--tessera-text)]">
                    {r.chunks}
                  </td>
                  <td className="px-3 py-2 tabular-nums text-[var(--tessera-text-muted)]">
                    {r.accessible_until}
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={cn(
                        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[0.58rem] font-medium",
                        r.status === "accessible"
                          ? "border-emerald-500/30 bg-emerald-500/15 text-[var(--tessera-fg-success)]"
                          : "border-red-500/30 bg-red-500/15 text-[var(--tessera-fg-danger)]",
                      )}
                    >
                      {r.status_label}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <Pagination
        t={t}
        page={safePage}
        totalPages={totalPages}
        start={total === 0 ? 0 : start + 1}
        end={Math.min(start + perPage, total)}
        total={total}
        perPage={perPage}
        onPage={setPage}
        onPerPage={setPerPage}
      />
    </section>
  );
}

function FilterDropdown({
  label,
  value,
  allLabel,
  options,
  onSelect,
}: {
  label: string;
  value: string;
  allLabel: string;
  options: [string, string][];
  onSelect: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useDismiss(open, () => setOpen(false));
  const current =
    value === "all" ? allLabel : (options.find(([k]) => k === value)?.[1] ?? allLabel);
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex h-8 items-center gap-1.5 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 text-[0.72rem] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
      >
        <span className="text-[var(--tessera-text)]">{label}</span>
        <span>{current}</span>
        <ChevronDown className="h-3 w-3" />
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 min-w-[10rem] rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-1 shadow-lg"
        >
          {[["all", allLabel] as [string, string], ...options].map(([k, lbl]) => (
            <button
              key={k}
              type="button"
              role="menuitem"
              onClick={() => {
                onSelect(k);
                setOpen(false);
              }}
              className={cn(
                "flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-[0.72rem] hover:bg-[var(--tessera-bg)]",
                value === k ? "text-[var(--tessera-text)]" : "text-[var(--tessera-text-muted)]",
              )}
            >
              {lbl}
              {value === k ? (
                <ShieldCheck className="h-3.5 w-3.5 text-[var(--tessera-fg-success)]" />
              ) : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function pageWindow(page: number, totalPages: number): number[] {
  const span = Math.min(5, totalPages);
  let first = Math.max(1, page - Math.floor(span / 2));
  first = Math.min(first, Math.max(1, totalPages - span + 1));
  return Array.from({ length: span }, (_, i) => first + i);
}

function Pagination({
  t,
  page,
  totalPages,
  start,
  end,
  total,
  perPage,
  onPage,
  onPerPage,
}: {
  t: T;
  page: number;
  totalPages: number;
  start: number;
  end: number;
  total: number;
  perPage: number;
  onPage: (p: number) => void;
  onPerPage: (n: number) => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--tessera-border)] px-3 py-2 text-[0.7rem] text-[var(--tessera-text-muted)]">
      <span className="tabular-nums" aria-live="polite">
        {t("paginationSummary", { start, end, total })}
      </span>
      <div className="flex items-center gap-1">
        <button
          type="button"
          disabled={page <= 1}
          aria-label={t("prevPage")}
          onClick={() => onPage(Math.max(1, page - 1))}
          className="flex h-7 w-7 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)] disabled:opacity-40"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </button>
        {pageWindow(page, totalPages).map((n) => (
          <button
            key={n}
            type="button"
            aria-current={n === page ? "page" : undefined}
            onClick={() => onPage(n)}
            className={cn(
              "flex h-7 min-w-7 items-center justify-center rounded-md border px-1.5 text-[0.72rem] tabular-nums",
              n === page
                ? "border-[#b9a6ff]/60 bg-[#b9a6ff]/15 font-medium text-[var(--tessera-text-strong)]"
                : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
            )}
          >
            {n}
          </button>
        ))}
        <button
          type="button"
          disabled={page >= totalPages}
          aria-label={t("nextPage")}
          onClick={() => onPage(Math.min(totalPages, page + 1))}
          className="flex h-7 w-7 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)] disabled:opacity-40"
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
      <label className="flex items-center gap-2">
        <span>{t("rowsPerPage")}</span>
        <select
          value={perPage}
          onChange={(e) => onPerPage(Number(e.target.value))}
          className="h-7 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-1.5 text-[0.72rem] text-[var(--tessera-text)] focus:outline-none"
        >
          {ROWS_PER_PAGE_OPTS.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

// ── row-click drawer (anchored to <main>, like Connaissances) ─────────────────

function SourceDrawer({ t, row, onClose }: { t: T; row: Row; onClose: () => void }) {
  const [rect, setRect] = useState<{
    top: number;
    left: number;
    width: number;
    height: number;
  } | null>(null);
  useEffect(() => {
    const measure = () => {
      const m = document.querySelector("main");
      if (!m) return;
      const r = m.getBoundingClientRect();
      setRect({ top: r.top, left: r.left, width: r.width, height: r.bottom - r.top });
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const fields: [string, string][] = [
    [t("type"), row.type],
    [t("status"), row.status_label],
    [t("langs"), row.langs.toUpperCase()],
    [t("accessibleChunks"), `${row.chunks} / ${row.total_chunks}`],
    [t("firstSeen"), row.first_seen],
    [t("lastSeen"), row.updated],
  ];

  return (
    <div
      className="fixed z-50 flex justify-end overflow-hidden bg-[#020817]/70 p-2.5 backdrop-blur-[2px]"
      style={rect ?? { inset: 0 }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <dialog
        open
        aria-modal
        aria-label={row.source}
        className="relative flex h-full w-full max-w-[440px] flex-col rounded-lg border border-[var(--tessera-border)] border-l bg-[var(--tessera-surface)] p-4 text-[var(--tessera-text)] shadow-2xl"
      >
        <button
          type="button"
          onClick={onClose}
          aria-label={t("close")}
          className="absolute top-3 right-3 rounded-md border border-[var(--tessera-border)] p-1 text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
        >
          <X className="h-4 w-4" />
        </button>
        <p className="text-[0.62rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
          {t("detailEyebrow")}
        </p>
        <h3 className="mt-1 pr-8 text-[0.95rem] font-semibold">{row.source}</h3>
        <span
          className={cn(
            "mt-2 inline-flex w-fit items-center gap-1 rounded-full border px-2 py-0.5 text-[0.6rem] font-medium",
            row.status === "accessible"
              ? "border-emerald-500/30 bg-emerald-500/15 text-[var(--tessera-fg-success)]"
              : "border-red-500/30 bg-red-500/15 text-[var(--tessera-fg-danger)]",
          )}
        >
          {row.status_label}
        </span>
        <dl className="mt-4 flex flex-col gap-2.5 text-[0.78rem]">
          {fields.map(([label, value]) => (
            <div
              key={label}
              className="flex items-center justify-between gap-2 border-b border-[var(--tessera-border)]/40 pb-2 last:border-0"
            >
              <dt className="text-[var(--tessera-text-muted)]">{label}</dt>
              <dd className="font-medium tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
      </dialog>
    </div>
  );
}

function Snapshots({ data, onReload }: { data: Data; onReload: (asOf: string | null) => void }) {
  const t = useTranslations("etatADate");
  const s = data.snapshots;
  if (!s) return null;
  return (
    <Panel
      title={s.title}
      icon={Bookmark}
      iconClass="text-[var(--tessera-fg-danger)]"
      info={<SectionInfo title={s.title} explainKey="snapshots" />}
    >
      {s.rows.length === 0 ? (
        <p className="py-1 text-[0.72rem] text-[var(--tessera-text-muted)]">{t("noSnapshots")}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {s.rows.map((r) => (
            <li
              key={r.id}
              className="flex items-center justify-between gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-2"
            >
              <span className="min-w-0">
                <span className="flex items-center gap-2 text-[0.74rem] font-medium text-[var(--tessera-text)]">
                  {r.as_of_label}
                  <span className="rounded bg-[var(--tessera-surface)] px-1.5 py-0.5 font-mono text-[0.58rem] text-[var(--tessera-text-muted)]">
                    {r.ref_code}
                  </span>
                </span>
                <Truncate
                  full={`${r.summary} - ${t("savedAt")} ${r.saved_label}`}
                  className="text-[0.62rem] text-[var(--tessera-text-muted)]"
                >
                  {r.summary} - {t("savedAt")} {r.saved_label}
                </Truncate>
              </span>
              <button
                type="button"
                onClick={() => onReload(r.as_of)}
                className="flex shrink-0 items-center gap-1 rounded-md border border-[var(--tessera-border)] px-2 py-1 text-[0.62rem] text-[var(--tessera-fg-accent)] hover:text-[var(--tessera-text-strong)]"
              >
                <RotateCcw className="h-3 w-3" /> {t("reload")}
              </button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

// ── skeleton ───────────────────────────────────────────────────────────────

const SKELETON_CARDS = ["a", "b", "c"];

function EtatSkeleton() {
  return (
    <div className="flex flex-col gap-2.5">
      <div className="grid gap-2.5 xl:grid-cols-12">
        <Skeleton className="h-40 rounded-lg xl:col-span-3" />
        <Skeleton className="h-40 rounded-lg xl:col-span-5" />
        <Skeleton className="h-40 rounded-lg xl:col-span-4" />
      </div>
      <div className="grid gap-2.5 xl:grid-cols-12">
        {SKELETON_CARDS.map((k) => (
          <Skeleton key={k} className="h-44 rounded-lg xl:col-span-4" />
        ))}
      </div>
      <Skeleton className="h-80 rounded-lg" />
    </div>
  );
}
