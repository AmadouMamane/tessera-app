"use client";

import { useQuery } from "@tanstack/react-query";
import { Download, FileText, Search, X } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import { fetchClientDocuments } from "@/lib/api/client";
import type { ClientDocuments as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

type T = ReturnType<typeof useTranslations<"clientDocuments">>;
type Doc = NonNullable<Data["documents"]>[number];

const CAT_BADGE: Record<string, string> = {
  products: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  terms: "border-violet-500/30 bg-violet-500/15 text-violet-300",
  procedures: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
  services: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  other: "border-pink-500/30 bg-pink-500/15 text-pink-300",
};

export function ClientDocuments() {
  const t = useTranslations("clientDocuments");
  const locale = useLocale();
  const { data } = useQuery({
    queryKey: ["client-documents", locale],
    queryFn: ({ signal }) => fetchClientDocuments(locale, signal),
    staleTime: 60_000,
  });

  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [openDoc, setOpenDoc] = useState<Doc | null>(null);

  const docs = useMemo(() => data?.documents ?? [], [data]);
  const categories = useMemo(() => Array.from(new Set(docs.map((d) => d.category))), [docs]);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return docs.filter((d) => {
      if (category !== "all" && d.category !== category) return false;
      if (!q) return true;
      return `${d.title} ${d.excerpt} ${d.source}`.toLowerCase().includes(q);
    });
  }, [docs, query, category]);

  if (!data) return <Loading />;
  if (!data.available) return <Unavailable text={t("unavailable")} />;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 pb-2 text-[var(--tessera-text)]">
      <p className="text-sm text-[var(--tessera-text-muted)]">{t("subtitle")}</p>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {(data.kpis ?? []).map((k) => (
          <Kpi key={k.key} label={t(`kpi.${k.key}`)} value={k.value} sub={k.sub} />
        ))}
      </div>

      {(data.distribution ?? []).length > 0 ? (
        <section className="rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4">
          <h2 className="mb-3 text-[0.7rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
            {t("distribution")}
          </h2>
          <div className="flex flex-col gap-2">
            {(data.distribution ?? []).map((s) => (
              <div key={s.key} className="flex items-center gap-3 text-[0.74rem]">
                <span className="w-28 shrink-0 truncate">{t(`category.${s.key}`)}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--tessera-bg)]">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${s.pct}%`, background: s.color }}
                  />
                </div>
                <span className="w-16 shrink-0 text-right tabular-nums text-[var(--tessera-text-muted)]">
                  {s.count} · {s.pct}%
                </span>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[220px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--tessera-text-muted)]" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("search")}
            className="h-9 w-full rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] pl-9 pr-3 text-xs text-[var(--tessera-text)] outline-none focus:border-[var(--tessera-green)]"
          />
        </div>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="h-9 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text)] outline-none focus:border-[var(--tessera-green)]"
        >
          <option value="all">{t("allCategories")}</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {t(`category.${c}`)}
            </option>
          ))}
        </select>
      </div>

      {filtered.length === 0 ? (
        <Unavailable text={t("empty")} />
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((d) => (
            <button
              key={d.id}
              type="button"
              onClick={() => setOpenDoc(d)}
              className="group flex flex-col gap-2 rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4 text-left transition-colors hover:border-[var(--tessera-green)]/50 hover:bg-[var(--tessera-muted)]"
            >
              <div className="flex items-start justify-between gap-2">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-green)]">
                  <FileText className="h-4 w-4" />
                </span>
                <Badge className={CAT_BADGE[d.category] ?? CAT_BADGE.other}>
                  {t(`category.${d.category}`)}
                </Badge>
              </div>
              <p className="font-semibold text-[var(--tessera-text)]">{d.title}</p>
              <p className="line-clamp-3 text-[0.72rem] leading-relaxed text-[var(--tessera-text-muted)]">
                {d.excerpt}
              </p>
              <div className="mt-auto flex items-center gap-3 pt-1 text-[0.62rem] text-[var(--tessera-text-muted)]">
                <span>{d.language}</span>
                <span>{t("meta.pages", { n: d.pages })}</span>
                <span>{d.size_kb} Ko</span>
                <span className="ml-auto">{d.updated}</span>
              </div>
            </button>
          ))}
        </div>
      )}

      {data.footer ? (
        <footer className="mt-1 flex flex-wrap items-center gap-x-5 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
          <span>{t("footer.total", { n: data.footer.total ?? filtered.length })}</span>
          <span>{t("footer.source", { src: data.footer.source })}</span>
        </footer>
      ) : null}

      {openDoc ? <DocDrawer t={t} doc={openDoc} onClose={() => setOpenDoc(null)} /> : null}
    </div>
  );
}

function DocDrawer({ t, doc, onClose }: { t: T; doc: Doc; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/40"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <dialog
        open
        aria-modal
        className="relative m-0 flex h-full w-full max-w-[480px] flex-col overflow-y-auto border-l border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-5 text-[var(--tessera-text)] shadow-[0_12px_48px_rgba(0,0,0,0.5)]"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <Badge className={CAT_BADGE[doc.category] ?? CAT_BADGE.other}>
              {t(`category.${doc.category}`)}
            </Badge>
            <h2 className="mt-2 text-lg font-semibold text-white">{doc.title}</h2>
            <p className="mt-1 font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
              {doc.source}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("drawer.close")}
            className="shrink-0 text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-3 border-y border-[var(--tessera-border)] py-2 text-[0.66rem] text-[var(--tessera-text-muted)]">
          <span>{doc.language}</span>
          <span>{t("meta.pages", { n: doc.pages })}</span>
          <span>{doc.size_kb} Ko</span>
          <span>
            {t("meta.updated")}: {doc.updated}
          </span>
        </div>

        <article className="mt-3 whitespace-pre-wrap text-[0.8rem] leading-relaxed text-[var(--tessera-text)]">
          {doc.body}
        </article>

        <div className="mt-4 flex">
          <span className="inline-flex cursor-not-allowed items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 py-2 text-xs text-[var(--tessera-text-muted)]">
            <Download className="h-4 w-4" /> {t("drawer.download")}
          </span>
        </div>
      </dialog>
    </div>
  );
}

function Kpi({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="flex flex-col rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3.5">
      <p className="truncate text-[0.66rem] font-medium text-[var(--tessera-text-muted)]">
        {label}
      </p>
      <p className="mt-1 text-2xl font-semibold leading-none text-white">{value}</p>
      <p className="mt-1 truncate text-[0.6rem] text-[var(--tessera-text-muted)]">{sub}</p>
    </div>
  );
}

function Badge({ children, className }: { children: React.ReactNode; className?: string }) {
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

function Loading() {
  return (
    <div className="flex h-full items-center justify-center text-sm text-[var(--tessera-text-muted)]">
      …
    </div>
  );
}

function Unavailable({ text }: { text: string }) {
  return (
    <div className="flex min-h-[200px] flex-1 items-center justify-center rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-8 text-center text-sm text-[var(--tessera-text-muted)]">
      {text}
    </div>
  );
}
