"use client";

import { useQuery } from "@tanstack/react-query";
import { Mail, MapPin, Phone, Search, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";

import { fetchClientRequests } from "@/lib/api/client";
import type { ClientRequests as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

type T = ReturnType<typeof useTranslations<"clientRequests">>;
type Req = NonNullable<Data["requests"]>[number];

const STATUS_BADGE: Record<string, string> = {
  open: "border-amber-500/30 bg-amber-500/15 text-amber-300",
  in_progress: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  resolved: "border-emerald-500/30 bg-emerald-500/15 text-emerald-300",
};
const STATUS_DOT: Record<string, string> = {
  open: "bg-amber-400",
  in_progress: "bg-sky-400",
  resolved: "bg-emerald-400",
};
const CHANNEL_ICON = { phone: Phone, email: Mail, branch: MapPin } as const;

export function ClientRequests() {
  const t = useTranslations("clientRequests");
  const { data } = useQuery({
    queryKey: ["client-requests"],
    queryFn: ({ signal }) => fetchClientRequests(signal),
    staleTime: 60_000,
  });

  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [open, setOpen] = useState<Req | null>(null);

  const requests = useMemo(() => data?.requests ?? [], [data]);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return requests.filter((r) => {
      if (status !== "all" && r.status !== status) return false;
      if (!q) return true;
      return `${r.subject} ${r.summary} ${r.reference}`.toLowerCase().includes(q);
    });
  }, [requests, query, status]);

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
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="h-9 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text)] outline-none focus:border-[var(--tessera-green)]"
        >
          <option value="all">{t("allStatuses")}</option>
          {(["open", "in_progress", "resolved"] as const).map((s) => (
            <option key={s} value={s}>
              {t(`status.${s}`)}
            </option>
          ))}
        </select>
      </div>

      {filtered.length === 0 ? (
        <Unavailable text={t("empty")} />
      ) : (
        <ul className="flex flex-col gap-2">
          {filtered.map((r) => {
            const Icon = CHANNEL_ICON[r.channel];
            return (
              <li key={r.reference}>
                <button
                  type="button"
                  onClick={() => setOpen(r)}
                  className="group flex w-full items-center gap-3 rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-3.5 text-left transition-colors hover:border-[var(--tessera-green)]/50 hover:bg-[var(--tessera-muted)]"
                >
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]">
                    <Icon className="h-4 w-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-[var(--tessera-text)]">{r.subject}</p>
                    <p className="truncate text-[0.7rem] text-[var(--tessera-text-muted)]">
                      <span className="font-mono">{r.reference}</span> · {r.opened}
                    </p>
                  </div>
                  <span className={cn("inline-flex items-center gap-1.5 text-[0.7rem]")}>
                    <span className={cn("h-1.5 w-1.5 rounded-full", STATUS_DOT[r.status])} />
                    <Badge className={STATUS_BADGE[r.status]}>{t(`status.${r.status}`)}</Badge>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {data.footer ? (
        <footer className="mt-1 flex flex-wrap items-center gap-x-5 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
          <span>{t("footer.total", { n: data.footer.total ?? filtered.length })}</span>
          <span>{t("footer.source", { src: data.footer.source })}</span>
        </footer>
      ) : null}

      {open ? <ReqDrawer t={t} req={open} onClose={() => setOpen(null)} /> : null}
    </div>
  );
}

function ReqDrawer({ t, req, onClose }: { t: T; req: Req; onClose: () => void }) {
  const Icon = CHANNEL_ICON[req.channel];
  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/40"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <dialog
        open
        aria-modal
        className="relative m-0 flex h-full w-full max-w-[460px] flex-col gap-4 overflow-y-auto border-l border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-5 text-[var(--tessera-text)] shadow-[0_12px_48px_rgba(0,0,0,0.5)]"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <Badge className={STATUS_BADGE[req.status]}>{t(`status.${req.status}`)}</Badge>
            <h2 className="mt-2 text-lg font-semibold text-white">{req.subject}</h2>
            <p className="mt-1 font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
              {req.reference}
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

        <dl className="flex flex-col gap-1.5 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-3 text-[0.72rem]">
          <KV label={t("drawer.channel")}>
            <span className="inline-flex items-center gap-1.5">
              <Icon className="h-3.5 w-3.5" /> {t(`channel.${req.channel}`)}
            </span>
          </KV>
          <KV label={t("drawer.category")}>{t(`category.${req.category}`)}</KV>
          <KV label={t("drawer.opened")}>{req.opened}</KV>
          <KV label={t("drawer.updated")}>{req.updated}</KV>
        </dl>

        <div>
          <h3 className="mb-1 text-[0.68rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
            {t("drawer.summary")}
          </h3>
          <p className="text-[0.8rem] leading-relaxed text-[var(--tessera-text)]">{req.summary}</p>
        </div>
      </dialog>
    </div>
  );
}

function KV({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="shrink-0 text-[var(--tessera-text-muted)]">{label}</dt>
      <dd className="min-w-0 truncate text-right text-[var(--tessera-text)]">{children}</dd>
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
