"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bookmark,
  Boxes,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  Download,
  FileText,
  History,
  Info,
  RotateCcw,
  Search,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/i18n/navigation";
import { fetchEtatADate, saveEtatSnapshot } from "@/lib/api/client";
import type { EtatADate as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

type Row = NonNullable<Data["table"]>["rows"][number];
type GovCard = NonNullable<Data["guardrails"]>;
type SortDir = "asc" | "desc";

const TYPE_TONE: Record<string, string> = {
  violet: "border-[#8b7cf0]/30 bg-[#8b7cf0]/15 text-[#c4b5fd]",
  blue: "border-[#4c8bf5]/30 bg-[#4c8bf5]/15 text-[#93c5fd]",
};
const KIND_DOT: Record<string, string> = {
  info: "bg-sky-400",
  ok: "bg-emerald-400",
  warn: "bg-amber-400",
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

function toIso(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

function toLocalInput(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const off = d.getTimezoneOffset() * 60_000;
  return new Date(d.getTime() - off).toISOString().slice(0, 16);
}

export function EtatADate() {
  const t = useTranslations("etatADate");
  const qc = useQueryClient();
  const [draft, setDraft] = useState("");
  const [asOf, setAsOf] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [typeF, setTypeF] = useState("all");
  const [statusF, setStatusF] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);

  const { data } = useQuery({
    queryKey: ["etat-a-date", asOf],
    queryFn: ({ signal }) => fetchEtatADate(asOf, signal),
    staleTime: 30_000,
  });

  const saveSnapshot = useMutation({
    mutationFn: () => saveEtatSnapshot(asOf),
    onSuccess: (fresh) => qc.setQueryData(["etat-a-date", asOf], fresh),
  });

  function reloadAt(snapAsOf: string | null) {
    setAsOf(snapAsOf);
    setDraft(snapAsOf ? toLocalInput(snapAsOf) : "");
  }

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
    <div className="relative flex flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      {data?.meta?.banner ? <Banner text={data.meta.banner} /> : null}

      <ControlBar
        t={t}
        draft={draft}
        onDraft={setDraft}
        onReconstruct={() => setAsOf(toIso(draft))}
        meta={data?.meta}
        onDownload={downloadReport}
        canDownload={Boolean(data?.available)}
        onSave={() => saveSnapshot.mutate()}
        saving={saveSnapshot.isPending}
        saved={saveSnapshot.isSuccess}
      />

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
              <GovCardView t={t} card={data.guardrails} icon={ShieldCheck} />
              <GovCardView t={t} card={data.prompt_model} icon={FileText} />
              <GovCardView t={t} card={data.release} icon={Boxes} />
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

function Banner({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-[#9a5f18]/50 bg-[#3e260c]/30 p-2.5 text-[0.72rem] text-[#f0c89a]">
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-[#f0a23a]" />
      <span>{text}</span>
    </div>
  );
}

function ControlBar({
  t,
  draft,
  onDraft,
  onReconstruct,
  meta,
  onDownload,
  canDownload,
  onSave,
  saving,
  saved,
}: {
  t: T;
  draft: string;
  onDraft: (v: string) => void;
  onReconstruct: () => void;
  meta: Data["meta"];
  onDownload: () => void;
  canDownload: boolean;
  onSave: () => void;
  saving: boolean;
  saved: boolean;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3">
      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={onSave}
          disabled={!canDownload || saving}
          className="flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)] disabled:opacity-50"
        >
          <Bookmark className="h-4 w-4" />
          {saving ? t("saving") : saved ? t("saved") : t("saveSnapshot")}
        </button>
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
        <Field label={t("tenant")}>
          <Static>{meta?.tenant ?? "-"}</Static>
        </Field>
        <Field label={t("agent")}>
          <Static>{meta?.agent ?? "-"}</Static>
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
            {meta?.context_source ?? "-"}
            <span className="rounded bg-[var(--tessera-surface)] px-1.5 py-0.5 font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
              {meta?.ref_code ?? "-"}
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

function Static({ children }: { children: React.ReactNode }) {
  return (
    <span className="flex h-9 items-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-sm">
      {children}
    </span>
  );
}

// ── panels ───────────────────────────────────────────────────────────────────

function Panel({
  title,
  icon: Icon,
  children,
  className,
}: { title: string; icon?: typeof ShieldCheck; children: React.ReactNode; className?: string }) {
  return (
    <section
      className={cn(
        "flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3",
        className,
      )}
    >
      <h2 className="mb-2 flex items-center gap-1.5 text-[0.78rem] font-semibold text-[var(--tessera-text)]">
        {Icon ? <Icon className="h-4 w-4 text-[#b9a6ff]" /> : null}
        {title}
      </h2>
      {children}
    </section>
  );
}

function VerifiedBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={cn(
        "inline-flex w-fit items-center gap-1 rounded-full border px-2 py-0.5 text-[0.6rem] font-medium",
        ok
          ? "border-emerald-500/30 bg-emerald-500/15 text-emerald-300"
          : "border-red-500/30 bg-red-500/15 text-red-300",
      )}
    >
      {ok ? <ShieldCheck className="h-3.5 w-3.5" /> : null}
      {label}
    </span>
  );
}

function Reconstructed({ data, className }: { data: Data; className?: string }) {
  const r = data.reconstructed;
  if (!r) return null;
  return (
    <Panel title={r.title} icon={Sparkles} className={className}>
      <p className="font-mono text-[0.72rem] text-[var(--tessera-text)]">{r.snapshot_id}</p>
      <VerifiedBadge ok={r.verified} label={r.verified_label} />
      <p className="mt-3 text-[0.68rem] text-[var(--tessera-text-muted)]">{r.built_label}</p>
    </Panel>
  );
}

function Original({ data, className }: { data: Data; className?: string }) {
  const t = useTranslations("etatADate");
  const o = data.original;
  if (!o) return null;
  return (
    <Panel title={o.title} icon={FileText} className={className}>
      <p className="font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">{o.ref_code}</p>
      {o.available ? (
        <div className="mt-2 flex flex-col gap-2 text-[0.74rem]">
          <div>
            <p className="text-[0.62rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {t("question")}
            </p>
            <p className="text-[var(--tessera-text)]">{o.question}</p>
          </div>
          <div>
            <p className="text-[0.62rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
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
  className,
}: { t: T; card?: GovCard; icon: typeof ShieldCheck; className?: string }) {
  if (!card) return null;
  return (
    <Panel title={card.title} icon={icon} className={className}>
      <dl className="flex flex-col gap-1.5 text-[0.72rem]">
        {card.rows.map((r) => (
          <div key={r.label} className="flex items-center justify-between gap-2">
            <dt className="text-[var(--tessera-text-muted)]">{r.label}</dt>
            <dd className="truncate text-right font-medium text-[var(--tessera-text)]">
              {r.value}
            </dd>
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
              key={d}
              className="flex items-start gap-1.5 text-[0.68rem] text-[var(--tessera-text)]"
            >
              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-[#b9a6ff]" />
              {d}
            </li>
          ))}
        </ul>
      </div>
      <Link
        href={card.cta_href as never}
        className="mt-2.5 flex items-center gap-1 self-start text-[0.68rem] text-[#b9a6ff] hover:text-white"
      >
        {card.cta} <ChevronRight className="h-3.5 w-3.5" />
      </Link>
    </Panel>
  );
}

function Chronology({ data, className }: { data: Data; className?: string }) {
  const tl = data.timeline;
  if (!tl) return null;
  return (
    <Panel title={tl.title} icon={History} className={className}>
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
      {tl.cta && tl.cta_href ? <CtaLink label={tl.cta} href={tl.cta_href} /> : null}
    </Panel>
  );
}

function CtaLink({ label, href }: { label: string; href: string }) {
  return (
    <Link
      href={href as never}
      className="mt-2.5 flex items-center gap-1 self-start text-[0.68rem] text-[#b9a6ff] hover:text-white"
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
    ["Requete de test", it.test_query],
    ["Derniere synchro avant T", it.last_sync],
    ["Journalisation", it.chain_label],
  ];
  return (
    <Panel title={it.title} icon={ShieldCheck}>
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
    <Panel title={a.title} icon={FileText} className={className}>
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
                          "border-slate-500/30 bg-slate-500/15 text-slate-300",
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
                          ? "border-emerald-500/30 bg-emerald-500/15 text-emerald-300"
                          : "border-red-500/30 bg-red-500/15 text-red-300",
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
              {value === k ? <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" /> : null}
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
                ? "border-[#b9a6ff]/60 bg-[#b9a6ff]/15 font-medium text-white"
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
              ? "border-emerald-500/30 bg-emerald-500/15 text-emerald-300"
              : "border-red-500/30 bg-red-500/15 text-red-300",
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
    <Panel title={s.title} icon={Bookmark}>
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
                <span className="block truncate text-[0.62rem] text-[var(--tessera-text-muted)]">
                  {r.summary} - {t("savedAt")} {r.saved_label}
                </span>
              </span>
              <button
                type="button"
                onClick={() => onReload(r.as_of)}
                className="flex shrink-0 items-center gap-1 rounded-md border border-[var(--tessera-border)] px-2 py-1 text-[0.62rem] text-[#b9a6ff] hover:text-white"
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
    <div className="flex flex-col gap-3">
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
