"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Bell, CheckCircle2, Info, ShieldCheck, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";

import { fetchClientAlerts, mutateClientAlert } from "@/lib/api/client";
import type { ClientAlerts as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

type T = ReturnType<typeof useTranslations<"clientAlerts">>;
type Alert = NonNullable<Data["alerts"]>[number];

const SEV = {
  info: { icon: Info, ring: "text-sky-300", dot: "bg-sky-400" },
  warning: { icon: AlertTriangle, ring: "text-amber-300", dot: "bg-amber-400" },
  success: { icon: CheckCircle2, ring: "text-emerald-300", dot: "bg-emerald-400" },
} as const;
const CAT_ICON = { security: ShieldCheck, statement: Info, payment: AlertTriangle, card: Bell };

export function ClientAlerts() {
  const t = useTranslations("clientAlerts");
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["client-alerts"],
    queryFn: ({ signal }) => fetchClientAlerts(signal),
    staleTime: 30_000,
  });

  const mark = useMutation({
    mutationFn: mutateClientAlert,
    onSuccess: (fresh) => qc.setQueryData(["client-alerts"], fresh),
  });

  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [open, setOpen] = useState<Alert | null>(null);

  const alerts = useMemo(() => data?.alerts ?? [], [data]);
  const filtered = useMemo(
    () => (filter === "unread" ? alerts.filter((a) => !a.read) : alerts),
    [alerts, filter],
  );

  if (!data) return <Loading />;
  if (!data.available) return <Unavailable text={t("unavailable")} />;

  const toggleRead = (a: Alert, read: boolean) => mark.mutate({ alert_id: a.id, read });
  const markAllRead = () => {
    for (const a of alerts) if (!a.read) mark.mutate({ alert_id: a.id, read: true });
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 pb-2 text-[var(--tessera-text)]">
      <p className="text-sm text-[var(--tessera-text-muted)]">{t("subtitle")}</p>

      <div className="grid grid-cols-3 gap-3">
        {(data.kpis ?? []).map((k) => (
          <Kpi key={k.key} label={t(`kpi.${k.key}`)} value={k.value} sub={k.sub} />
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="flex rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-0.5">
          {(["all", "unread"] as const).map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={cn(
                "rounded px-3 py-1.5 text-xs font-medium transition-colors",
                filter === f
                  ? "bg-[var(--tessera-surface-elevated)] text-white"
                  : "text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
              )}
            >
              {t(`filter.${f}`)}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={markAllRead}
          disabled={alerts.every((a) => a.read) || mark.isPending}
          className="ml-auto rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 py-1.5 text-xs text-[var(--tessera-text-muted)] transition-colors hover:text-[var(--tessera-text)] disabled:opacity-40"
        >
          {t("markAllRead")}
        </button>
      </div>

      {filtered.length === 0 ? (
        <Unavailable text={t("empty")} />
      ) : (
        <ul className="flex flex-col gap-2">
          {filtered.map((a) => {
            const sev = SEV[a.severity];
            const Icon = sev.icon;
            return (
              <li
                key={a.id}
                className={cn(
                  "flex items-start gap-3 rounded-xl border bg-[var(--tessera-surface)] p-3.5 transition-colors",
                  a.read
                    ? "border-[var(--tessera-border)] opacity-70"
                    : "border-[var(--tessera-green)]/30",
                )}
              >
                <span
                  className={cn(
                    "mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)]",
                    sev.ring,
                  )}
                >
                  <Icon className="h-4 w-4" />
                </span>
                <button
                  type="button"
                  onClick={() => setOpen(a)}
                  className="min-w-0 flex-1 text-left"
                >
                  <p className="flex items-center gap-2 font-medium text-[var(--tessera-text)]">
                    {!a.read ? <span className={cn("h-1.5 w-1.5 rounded-full", sev.dot)} /> : null}
                    {a.title}
                  </p>
                  <p className="mt-0.5 line-clamp-2 text-[0.72rem] leading-relaxed text-[var(--tessera-text-muted)]">
                    {a.body}
                  </p>
                  <p className="mt-1 text-[0.62rem] text-[var(--tessera-text-muted)]">{a.date}</p>
                </button>
                <button
                  type="button"
                  onClick={() => toggleRead(a, !a.read)}
                  disabled={mark.isPending}
                  className="shrink-0 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2.5 py-1 text-[0.62rem] text-[var(--tessera-text-muted)] transition-colors hover:text-[var(--tessera-text)] disabled:opacity-40"
                >
                  {a.read ? t("markUnread") : t("markRead")}
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

      {open ? (
        <AlertDrawer
          t={t}
          alert={open}
          onClose={() => setOpen(null)}
          onToggleRead={(read) => toggleRead(open, read)}
        />
      ) : null}
    </div>
  );
}

function AlertDrawer({
  t,
  alert,
  onClose,
  onToggleRead,
}: {
  t: T;
  alert: Alert;
  onClose: () => void;
  onToggleRead: (read: boolean) => void;
}) {
  const Icon = CAT_ICON[alert.category as keyof typeof CAT_ICON] ?? Bell;
  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/40"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <dialog
        open
        aria-modal
        className="relative m-0 flex h-full w-full max-w-[440px] flex-col gap-4 overflow-y-auto border-l border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-5 text-[var(--tessera-text)] shadow-[0_12px_48px_rgba(0,0,0,0.5)]"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-3">
            <span
              className={cn(
                "grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)]",
                SEV[alert.severity].ring,
              )}
            >
              <Icon className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <h2 className="text-lg font-semibold text-white">{alert.title}</h2>
              <p className="mt-0.5 text-[0.62rem] text-[var(--tessera-text-muted)]">{alert.date}</p>
            </div>
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
        <p className="text-[0.82rem] leading-relaxed text-[var(--tessera-text)]">{alert.body}</p>
        <button
          type="button"
          onClick={() => onToggleRead(!alert.read)}
          className="self-start rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 py-2 text-xs text-[var(--tessera-text-muted)] transition-colors hover:text-[var(--tessera-text)]"
        >
          {alert.read ? t("markUnread") : t("markRead")}
        </button>
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
