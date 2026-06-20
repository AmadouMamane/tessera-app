"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronsUpDown, Info, Search, ShieldCheck, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { type ReactNode, useMemo, useState } from "react";

import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { fetchUsers } from "@/lib/api/client";
import type { UsersOverview as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

type T = ReturnType<typeof useTranslations<"users">>;
type User = NonNullable<Data["users"]>[number];

const BADGE: Record<string, string> = {
  purple: "border-violet-500/30 bg-violet-500/15 text-violet-300",
  blue: "border-sky-500/30 bg-sky-500/15 text-sky-300",
  slate: "border-slate-500/30 bg-slate-500/15 text-slate-300",
};
const STATUS: Record<string, { dot: string; text: string }> = {
  active: { dot: "bg-emerald-400", text: "text-emerald-300" },
  provisioned_on_demand: { dot: "bg-slate-400", text: "text-slate-300" },
  disabled: { dot: "bg-red-400", text: "text-red-300" },
};
type SortKey = "display" | "role" | "team" | "status";

export function UsersOverview() {
  const t = useTranslations("users");
  const { data } = useQuery({
    queryKey: ["users"],
    queryFn: ({ signal }) => fetchUsers(signal),
    staleTime: 60_000,
  });

  const [query, setQuery] = useState("");
  const [role, setRole] = useState("all");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "display", dir: 1 });
  const [open, setOpen] = useState<User | null>(null);

  const users = useMemo(() => data?.users ?? [], [data]);
  const roles = useMemo(() => Array.from(new Set(users.map((u) => u.role))), [users]);
  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = users.filter((u) => {
      if (role !== "all" && u.role !== role) return false;
      if (!q) return true;
      return `${u.display} ${u.username} ${u.email} ${u.team}`.toLowerCase().includes(q);
    });
    return [...filtered].sort((a, b) => a[sort.key].localeCompare(b[sort.key]) * sort.dir);
  }, [users, query, role, sort]);

  if (!data) return <Loading />;
  if (!data.available) return <Unavailable text={t("unavailable")} />;

  const toggleSort = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: 1 }));
  const statusLabel = (s: string) =>
    s === "provisioned_on_demand" ? t("status.provisioned") : t(`status.${s}`);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      <p className="text-sm text-[var(--tessera-text-muted)]">{t("subtitle")}</p>

      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {(data.kpis ?? []).map((k) => (
          <div
            key={k.key}
            className="flex h-[92px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5"
          >
            <p className="truncate text-[0.64rem] font-medium text-[var(--tessera-text-muted)]">
              {t(`kpi.${k.key}`)}
            </p>
            <p className="mt-0.5 text-[1.3rem] font-semibold leading-none text-white">{k.value}</p>
            <p className="mt-0.5 truncate text-[0.56rem] text-[var(--tessera-text-muted)]">
              {k.sub}
            </p>
            <MetricSparkline className="mt-auto h-4 w-full" values={k.series} tone="success" />
          </div>
        ))}
      </div>

      <section className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2">
        <div className="relative min-w-[200px] flex-1">
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
          value={role}
          onChange={(e) => setRole(e.target.value)}
          className="h-9 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 text-xs text-[var(--tessera-text)] outline-none focus:border-[var(--tessera-green)]"
        >
          <option value="all">{t("allRoles")}</option>
          {roles.map((r) => (
            <option key={r} value={r}>
              {t(`role.${r}`)}
            </option>
          ))}
        </select>
      </section>

      <div className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-[0.74rem]">
            <thead>
              <tr className="border-b border-[var(--tessera-border)] text-[0.58rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
                {(["display", "role", "team", "status"] as SortKey[]).map((k) => (
                  <th key={k} className="px-3 py-2 font-medium">
                    <button
                      type="button"
                      onClick={() => toggleSort(k)}
                      aria-sort={
                        sort.key === k ? (sort.dir === 1 ? "ascending" : "descending") : "none"
                      }
                      className="inline-flex items-center gap-1 hover:text-[var(--tessera-text)]"
                    >
                      {t(`col.${k}`)}
                      <ChevronsUpDown
                        className={cn(
                          "h-3 w-3",
                          sort.key === k ? "text-[var(--tessera-green)]" : "opacity-40",
                        )}
                      />
                    </button>
                  </th>
                ))}
                <th className="px-3 py-2 font-medium">{t("col.mfa")}</th>
                <th className="px-3 py-2 font-medium">{t("col.lastLogin")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((u) => (
                <tr
                  key={u.username}
                  onClick={() => setOpen(u)}
                  className="cursor-pointer border-b border-[var(--tessera-border)]/60 transition-colors hover:bg-[var(--tessera-muted)]"
                >
                  <td className="px-3 py-2">
                    <span className="flex items-center gap-2">
                      <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-[var(--tessera-green-muted)] text-[0.62rem] font-semibold text-[#d6f0e3]">
                        {u.display.charAt(0).toUpperCase()}
                      </span>
                      <span className="min-w-0">
                        <span className="block font-medium text-[var(--tessera-text)]">
                          {u.display}
                        </span>
                        <span className="block font-mono text-[0.6rem] text-[var(--tessera-text-muted)]">
                          {u.username}
                        </span>
                      </span>
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <Badge className={BADGE[u.badge]}>{u.role_label}</Badge>
                  </td>
                  <td className="px-3 py-2 text-[var(--tessera-text-muted)]">{u.team}</td>
                  <td className="px-3 py-2">
                    <span
                      className={cn("inline-flex items-center gap-1.5", STATUS[u.status]?.text)}
                    >
                      <span className={cn("h-1.5 w-1.5 rounded-full", STATUS[u.status]?.dot)} />
                      {statusLabel(u.status)}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-[var(--tessera-text-muted)]">
                    {u.mfa ? t("mfaOn") : t("mfaOff")}
                  </td>
                  <td className="px-3 py-2 text-[var(--tessera-text-muted)]">{u.last_login}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="flex items-start gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 py-2 text-[0.7rem] text-[var(--tessera-text-muted)]">
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <span>{t("phaseNote")}</span>
      </div>

      {data.footer ? (
        <footer className="mt-1 flex flex-wrap items-center gap-x-5 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
          <span>{t("footer.total", { n: data.footer.total ?? rows.length })}</span>
          <span>{t("footer.source", { src: data.footer.source })}</span>
        </footer>
      ) : null}

      {open ? <UserDrawer t={t} user={open} onClose={() => setOpen(null)} /> : null}
    </div>
  );
}

function UserDrawer({ t, user, onClose }: { t: T; user: User; onClose: () => void }) {
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
          <div className="flex min-w-0 items-center gap-3">
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-[var(--tessera-green-muted)] text-base font-semibold text-[#d6f0e3]">
              {user.display.charAt(0).toUpperCase()}
            </span>
            <div className="min-w-0">
              <h2 className="text-lg font-semibold text-white">{user.display}</h2>
              <p className="font-mono text-[0.62rem] text-[var(--tessera-text-muted)]">
                {user.email}
              </p>
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

        <dl className="flex flex-col gap-1.5 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-bg)] p-3 text-[0.72rem]">
          <KV label={t("drawer.role")}>
            <Badge className={BADGE[user.badge]}>{user.role_label}</Badge>
          </KV>
          <KV label={t("drawer.team")}>{user.team}</KV>
          <KV label={t("drawer.scope")}>{t(`scope.${user.scope}`)}</KV>
          <KV label={t("drawer.mfa")}>{user.mfa ? t("mfaOn") : t("mfaOff")}</KV>
          <KV label={t("drawer.lastLogin")}>{user.last_login}</KV>
        </dl>

        <div>
          <h3 className="mb-2 flex items-center gap-1.5 text-[0.7rem] font-semibold uppercase tracking-wider text-[var(--tessera-text-muted)]">
            <ShieldCheck className="h-3.5 w-3.5" /> {t("drawer.caps")}
          </h3>
          <ul className="flex flex-wrap gap-1.5">
            {user.caps.map((c) => (
              <li
                key={c}
                className="rounded border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-2 py-1 text-[0.66rem] text-[var(--tessera-text)]"
              >
                {t(`cap.${c}`)}
              </li>
            ))}
          </ul>
        </div>
      </dialog>
    </div>
  );
}

function KV({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="shrink-0 text-[var(--tessera-text-muted)]">{label}</dt>
      <dd className="min-w-0 truncate text-right text-[var(--tessera-text)]">{children}</dd>
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
