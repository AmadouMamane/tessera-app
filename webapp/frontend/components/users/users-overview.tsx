"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  ChevronsUpDown,
  Info,
  Search,
  ShieldCheck,
  SortAsc,
  SortDesc,
  X,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import {
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { MetricSparkline } from "@/components/overview/metric-sparkline";
import { Truncate } from "@/components/ui/truncate";
import { fetchUsers } from "@/lib/api/client";
import type { UsersOverview as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

type T = ReturnType<typeof useTranslations<"users">>;
type TT = ReturnType<typeof useTranslations<"table">>;
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

const COLS: { key: string; sort?: SortKey; w: string }[] = [
  { key: "display", sort: "display", w: "24%" },
  { key: "role", sort: "role", w: "15%" },
  { key: "team", sort: "team", w: "16%" },
  { key: "status", sort: "status", w: "14%" },
  { key: "mfa", w: "11%" },
  { key: "lastLogin", w: "13%" },
];
const ROWS_PER_PAGE_OPTS = [10, 25, 50];
const ACCENT = "#87bfff";

/** ⓘ for a users KPI, reading users.explain.<k>.{what,how,source?} (null if undocumented). */
function ExplainInfo({ k, title }: { k: string; title: string }) {
  const te = useTranslations("users.explain");
  if (!te.has(`${k}.what`)) return null;
  return (
    <MetricInfo
      title={title}
      what={te(`${k}.what`)}
      how={te.has(`${k}.how`) ? te(`${k}.how`) : undefined}
      source={te.has(`${k}.source`) ? te(`${k}.source`) : undefined}
      className="ml-auto"
    />
  );
}

export function UsersOverview() {
  const t = useTranslations("users");
  const tt = useTranslations("table");
  const locale = useLocale();
  const { data } = useQuery({
    queryKey: ["users", locale],
    queryFn: ({ signal }) => fetchUsers(locale, signal),
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
    <div className="flex flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      <p className="text-sm text-[var(--tessera-text-muted)]">{t("subtitle")}</p>

      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {(data.kpis ?? []).map((k) => (
          <div
            key={k.key}
            className="flex h-[92px] flex-col overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-2.5"
          >
            <p className="flex items-center gap-1 truncate text-[0.64rem] font-medium text-[var(--tessera-text-muted)]">
              <Truncate full={t(`kpi.${k.key}`)}>{t(`kpi.${k.key}`)}</Truncate>
              <ExplainInfo k={k.key} title={t(`kpi.${k.key}`)} />
            </p>
            <p className="mt-0.5 text-[1.3rem] font-semibold leading-none text-white">{k.value}</p>
            <Truncate
              as="p"
              full={k.sub}
              className="mt-0.5 text-[0.56rem] text-[var(--tessera-text-muted)]"
            >
              {k.sub}
            </Truncate>
            <MetricSparkline className="mt-auto h-4 w-full" values={k.series} tone="success" />
          </div>
        ))}
      </div>

      <section className="flex min-h-[54px] shrink-0 flex-wrap items-center gap-2 rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
        <div className="relative min-w-[200px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--tessera-text-muted)]" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label={t("search")}
            placeholder={t("search")}
            className="h-9 w-full rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] pl-9 pr-3 text-xs text-[var(--tessera-text)] outline-none focus:border-[#2e72d2]"
          />
        </div>
        <label className="relative shrink-0">
          <span className="sr-only">{t("allRoles")}</span>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="h-9 cursor-pointer appearance-none rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] pl-3 pr-8 text-xs text-[var(--tessera-text)] outline-none hover:border-[#2e72d2] focus:border-[#2e72d2]"
          >
            <option value="all">{t("allRoles")}</option>
            {roles.map((r) => (
              <option key={r} value={r}>
                {t(`role.${r}`)}
              </option>
            ))}
          </select>
          <ChevronsUpDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#87bfff]" />
        </label>
        <span className="shrink-0 text-[0.62rem] tabular-nums text-[var(--tessera-text-muted)]">
          {rows.length}/{users.length}
        </span>
      </section>

      <UsersTable
        t={t}
        tt={tt}
        rows={rows}
        sort={sort}
        onSort={toggleSort}
        statusLabel={statusLabel}
        selected={open}
        onSelect={setOpen}
      />

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

// ── table ────────────────────────────────────────────────────────────────────

function UsersTable({
  t,
  tt,
  rows,
  sort,
  onSort,
  statusLabel,
  selected,
  onSelect,
}: {
  t: T;
  tt: TT;
  rows: User[];
  sort: { key: SortKey; dir: 1 | -1 };
  onSort: (key: SortKey) => void;
  statusLabel: (s: string) => string;
  selected: User | null;
  onSelect: (u: User) => void;
}) {
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const total = rows.length;
  const totalPages = Math.max(1, Math.ceil(total / perPage));
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset to page 1 on filter/sort/size change
  useEffect(() => setPage(1), [total, perPage, sort.key, sort.dir]);
  const safePage = Math.min(page, totalPages);
  const start = (safePage - 1) * perPage;
  const pageRows = rows.slice(start, start + perPage);
  return (
    <div
      data-testid="users-table"
      className="flex min-w-0 flex-col rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)]"
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[820px] table-fixed border-collapse text-left text-[0.72rem]">
          <thead>
            <tr className="border-b border-[var(--tessera-border)] text-[0.56rem] uppercase tracking-wide text-[var(--tessera-text-muted)]">
              {COLS.map((c, idx) => (
                <th
                  key={c.key}
                  style={{ width: c.w }}
                  className={cn("py-1.5 font-medium", idx === 0 ? "pl-5 pr-2" : "px-2")}
                >
                  {c.sort ? (
                    <button
                      type="button"
                      onClick={() => onSort(c.sort as SortKey)}
                      aria-sort={
                        sort.key === c.sort ? (sort.dir === 1 ? "ascending" : "descending") : "none"
                      }
                      className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-[var(--tessera-text)]"
                    >
                      {t(`col.${c.key}`)}
                      {sort.key === c.sort ? (
                        sort.dir === 1 ? (
                          <SortAsc className="h-3 w-3 text-[#87bfff]" />
                        ) : (
                          <SortDesc className="h-3 w-3 text-[#87bfff]" />
                        )
                      ) : (
                        <ChevronsUpDown className="h-3 w-3 opacity-40" />
                      )}
                    </button>
                  ) : (
                    t(`col.${c.key}`)
                  )}
                </th>
              ))}
              <th className="w-28 px-2 py-1.5" aria-hidden="true" />
            </tr>
          </thead>
          <tbody>
            {pageRows.map((u) => {
              const active = selected?.username === u.username;
              return (
                <tr
                  key={u.username}
                  onClick={() => onSelect(u)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect(u);
                    }
                  }}
                  tabIndex={0}
                  // biome-ignore lint/a11y/useSemanticElements: a table row cannot be a <button>; keyboard + role provided.
                  role="button"
                  aria-label={u.display}
                  className={cn(
                    "group cursor-pointer border-b border-[var(--tessera-border)]/60 outline-none transition-colors last:border-0 hover:bg-[#0b2b49] focus-visible:bg-[#0b2b49]",
                    active && "bg-[#0b3157] shadow-[inset_3px_0_0_#2e72d2]",
                  )}
                >
                  <td className="py-1.5 pl-5 pr-2">
                    <span className="flex items-center gap-2">
                      <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-[var(--tessera-green-muted)] text-[0.62rem] font-semibold text-[#d6f0e3]">
                        {u.display.charAt(0).toUpperCase()}
                      </span>
                      <span className="min-w-0">
                        <Truncate
                          full={u.display}
                          className="font-medium text-[var(--tessera-text)]"
                        >
                          {u.display}
                        </Truncate>
                        <Truncate
                          full={u.username}
                          className="font-mono text-[0.6rem] text-[var(--tessera-text-muted)]"
                        >
                          {u.username}
                        </Truncate>
                      </span>
                    </span>
                  </td>
                  <td className="px-2 py-1.5">
                    <Badge className={BADGE[u.badge]}>{u.role_label}</Badge>
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                    <Truncate full={u.team}>{u.team}</Truncate>
                  </td>
                  <td className="px-2 py-1.5">
                    <span
                      className={cn("inline-flex items-center gap-1.5", STATUS[u.status]?.text)}
                    >
                      <span className={cn("h-1.5 w-1.5 rounded-full", STATUS[u.status]?.dot)} />
                      {statusLabel(u.status)}
                    </span>
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                    {u.mfa ? t("mfaOn") : t("mfaOff")}
                  </td>
                  <td className="px-2 py-1.5 text-[var(--tessera-text-muted)]">
                    <Truncate full={u.last_login}>{u.last_login}</Truncate>
                  </td>
                  <td className="px-2 py-1.5">
                    <span className="flex items-center justify-end gap-1 whitespace-nowrap">
                      <span className="text-[0.66rem] text-[#87bfff] opacity-0 transition-opacity group-hover:opacity-100">
                        {tt("rowOpen")}
                      </span>
                      <ChevronRight className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]/40 transition-colors group-hover:text-[#87bfff]" />
                    </span>
                  </td>
                </tr>
              );
            })}
            {total === 0 ? (
              <tr>
                <td
                  colSpan={COLS.length + 1}
                  className="px-2 py-6 text-center text-[0.7rem] text-[var(--tessera-text-muted)]"
                >
                  {tt("empty")}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <TablePagination
        tt={tt}
        page={safePage}
        totalPages={totalPages}
        start={total === 0 ? 0 : start + 1}
        end={Math.min(start + perPage, total)}
        total={total}
        perPage={perPage}
        onPage={setPage}
        onPerPage={setPerPage}
        accent={ACCENT}
      />
    </div>
  );
}

// Shared connaissances-style pagination footer (reused across cockpit tables).
function pageWindow(page: number, totalPages: number): number[] {
  const span = Math.min(5, totalPages);
  let first = Math.max(1, page - Math.floor(span / 2));
  first = Math.min(first, Math.max(1, totalPages - span + 1));
  return Array.from({ length: span }, (_, i) => first + i);
}

function TablePagination({
  tt,
  page,
  totalPages,
  start,
  end,
  total,
  perPage,
  onPage,
  onPerPage,
  accent,
}: {
  tt: TT;
  page: number;
  totalPages: number;
  start: number;
  end: number;
  total: number;
  perPage: number;
  onPage: (p: number) => void;
  onPerPage: (n: number) => void;
  accent: string;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--tessera-border)] px-3 py-2 text-[0.7rem] text-[var(--tessera-text-muted)]">
      <span className="tabular-nums" aria-live="polite">
        {tt("summary", { start, end, total })}
      </span>
      <div className="flex items-center gap-1">
        <button
          type="button"
          disabled={page <= 1}
          aria-label={tt("prev")}
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
            style={
              n === page ? { borderColor: `${accent}99`, background: `${accent}26` } : undefined
            }
            className={cn(
              "flex h-7 min-w-7 items-center justify-center rounded-md border px-1.5 text-[0.72rem] tabular-nums",
              n === page
                ? "font-medium text-white"
                : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
            )}
          >
            {n}
          </button>
        ))}
        <button
          type="button"
          disabled={page >= totalPages}
          aria-label={tt("next")}
          onClick={() => onPage(Math.min(totalPages, page + 1))}
          className="flex h-7 w-7 items-center justify-center rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)] disabled:opacity-40"
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
      <label className="flex items-center gap-2">
        <span>{tt("perPage")}</span>
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

// ── drawer ───────────────────────────────────────────────────────────────────

function UserDrawer({ t, user, onClose }: { t: T; user: User; onClose: () => void }) {
  const [rect, setRect] = useState<{
    top: number;
    left: number;
    width: number;
    height: number;
  } | null>(null);
  const [shown, setShown] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const FOCUSABLE = 'button, a[href], select, input, [tabindex]:not([tabindex="-1"])';
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    dialogRef.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus();
    return () => opener?.focus?.();
  }, []);
  const onTrapKey = (event: ReactKeyboardEvent<HTMLDialogElement>) => {
    if (event.key !== "Tab" || !dialogRef.current) return;
    const f = dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE);
    const first = f[0];
    const last = f[f.length - 1];
    if (!first || !last) return;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };
  useEffect(() => {
    const measure = () => {
      const m = document.querySelector("main");
      if (!m) return;
      const mr = m.getBoundingClientRect();
      const c = document.querySelector("[data-shell-content]") ?? m;
      const cr = c.getBoundingClientRect();
      setRect({ top: mr.top, left: cr.left, width: cr.width, height: mr.bottom - mr.top });
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);
  useEffect(() => {
    setShown(true);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div
      className="fixed z-50 flex justify-end overflow-hidden bg-[#020817]/70 py-2.5 pl-2.5 backdrop-blur-[2px]"
      style={rect ?? { inset: 0 }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <dialog
        ref={dialogRef}
        open
        aria-modal="true"
        aria-label={user.display}
        onKeyDown={onTrapKey}
        onCancel={(event) => {
          event.preventDefault();
          onClose();
        }}
        className={cn(
          "static m-0 block h-full w-full max-w-[440px] bg-transparent p-0 transition-transform duration-200 ease-out",
          shown ? "translate-x-0" : "translate-x-full",
        )}
      >
        <aside
          data-testid="user-detail"
          className="flex h-full w-full min-w-0 flex-col gap-4 overflow-y-auto rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-5 shadow-[0_12px_48px_rgba(0,0,0,0.5)]"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-[var(--tessera-green-muted)] text-base font-semibold text-[#d6f0e3]">
                {user.display.charAt(0).toUpperCase()}
              </span>
              <div className="min-w-0">
                <h2 className="truncate text-lg font-semibold text-white">{user.display}</h2>
                <Truncate
                  as="p"
                  full={user.email}
                  className="font-mono text-[0.62rem] text-[var(--tessera-text-muted)]"
                >
                  {user.email}
                </Truncate>
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
        </aside>
      </dialog>
    </div>
  );
}

function KV({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="shrink-0 text-[var(--tessera-text-muted)]">{label}</dt>
      <Truncate as="dd" className="min-w-0 text-right text-[var(--tessera-text)]">
        {children}
      </Truncate>
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
