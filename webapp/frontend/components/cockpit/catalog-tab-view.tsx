"use client";

import { type ReactNode, useState } from "react";

import { MetricInfo } from "@/components/cockpit/metric-info";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type {
  CatalogTab,
  SectionItem,
  TabColumn,
  TabDetail,
  TabExplain,
  TabKpi,
  TabRow,
  TabSection,
} from "@/lib/api/schemas";

const GOOD = "text-emerald-600 dark:text-emerald-400";
const WARN = "text-amber-600 dark:text-amber-400";
const BAD = "text-red-600 dark:text-red-400";

type BadgeTone = "neutral" | "navy" | "gold" | "success" | "warning" | "danger" | "info";

function tone(v: string | null | undefined): BadgeTone {
  switch (v) {
    case "success":
    case "warning":
    case "danger":
    case "info":
    case "navy":
    case "gold":
      return v;
    default:
      return "neutral";
  }
}

function kpiTone(v: string | null | undefined): string {
  switch (v) {
    case "good":
      return GOOD;
    case "warn":
      return WARN;
    case "bad":
      return BAD;
    default:
      return "text-[var(--foreground)]";
  }
}

/** ⓘ MetricInfo bound to a tab payload's optional `explain` block (grounded,
 * localized server-side). Renders nothing when the backend omits `explain`. */
function ExplainInfo({
  title,
  explain,
  className,
}: {
  title: string;
  explain?: TabExplain | null;
  className?: string;
}) {
  if (!explain) return null;
  return (
    <MetricInfo
      title={title}
      what={explain.what}
      how={explain.how ?? undefined}
      source={explain.source ?? undefined}
      className={className}
    />
  );
}

function Initials({ name }: { name: string }) {
  const ini = name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return (
    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--tessera-muted)] text-[0.55rem] font-semibold text-[var(--muted-foreground)]">
      {ini}
    </span>
  );
}

/* ---------------------------------------------------------------- KPI strip */

function KpiTile({ k }: { k: TabKpi }) {
  const up = k.delta?.startsWith("+");
  const good = k.delta_good ?? true;
  return (
    <Card className="flex h-[92px] flex-col gap-0.5 p-3">
      <div className="flex items-center gap-1 text-[0.7rem] text-[var(--muted-foreground)]">
        <span className="truncate">{k.label}</span>
        <ExplainInfo title={k.label} explain={k.explain} className="ml-auto" />
      </div>
      <div className={`text-2xl font-semibold tabular-nums ${kpiTone(k.tone)}`}>
        {k.value}
        {k.unit ? (
          <span className="text-base font-medium text-[var(--muted-foreground)]">{k.unit}</span>
        ) : null}
      </div>
      {k.delta ? (
        <div
          className={`mt-auto flex items-center gap-1 text-[0.65rem] tabular-nums ${good ? GOOD : BAD}`}
        >
          <span>{up ? "▲" : "▼"}</span>
          <span className="whitespace-nowrap">{k.delta.replace(/^[+-]/, "")}</span>
        </div>
      ) : k.sub ? (
        <div className="mt-auto truncate text-[0.65rem] text-[var(--muted-foreground)]">
          {k.sub}
        </div>
      ) : null}
    </Card>
  );
}

/* ------------------------------------------------------------------- table */

function Cell({ col, cells }: { col: TabColumn; cells: Record<string, unknown> }) {
  const v = cells[col.key];
  if (v == null) return <span className="text-[var(--muted-foreground)]">—</span>;
  switch (col.kind) {
    case "badge": {
      const c = v as { label: string; tone?: string };
      return <Badge tone={tone(c.tone)}>{c.label}</Badge>;
    }
    case "owner": {
      const c = v as { name: string; role?: string };
      return (
        <span className="flex items-center gap-1.5">
          <Initials name={c.name} />
          <span className="min-w-0">
            <span className="block truncate text-[0.72rem]">{c.name}</span>
            {c.role ? (
              <span className="block truncate text-[0.58rem] text-[var(--muted-foreground)]">
                {c.role}
              </span>
            ) : null}
          </span>
        </span>
      );
    }
    case "delta": {
      const c = v as { value: string; delta: string; good: boolean };
      const up = c.delta.startsWith("+");
      return (
        <span className="flex items-center justify-end gap-1.5">
          <span className="tabular-nums">{c.value}</span>
          <span className={`text-[0.6rem] tabular-nums ${c.good ? GOOD : BAD}`}>
            {up ? "▲" : "▼"} {c.delta.replace(/^[+-]/, "")}
          </span>
        </span>
      );
    }
    case "bar": {
      const c = v as { have: number; total: number; pct: number };
      return (
        <span className="flex flex-col items-end gap-0.5">
          <span className="tabular-nums">
            {c.have} / {c.total}
          </span>
          <span className="flex items-center gap-1">
            <span className="h-[4px] w-12 overflow-hidden rounded-full bg-[var(--tessera-border)]">
              <span
                className="block h-full rounded-full bg-emerald-500"
                style={{ width: `${c.pct}%` }}
              />
            </span>
            <span className="w-7 text-right text-[0.6rem] text-[var(--muted-foreground)]">
              {c.pct}%
            </span>
          </span>
        </span>
      );
    }
    case "pct": {
      const c = v as { pct: number };
      const t = c.pct >= 90 ? "bg-emerald-500" : c.pct >= 70 ? "bg-amber-500" : "bg-red-500";
      return (
        <span className="flex items-center justify-end gap-1.5">
          <span className="h-[4px] w-10 overflow-hidden rounded-full bg-[var(--tessera-border)]">
            <span className={`block h-full rounded-full ${t}`} style={{ width: `${c.pct}%` }} />
          </span>
          <span className="w-8 text-right tabular-nums">{c.pct}%</span>
        </span>
      );
    }
    case "mono":
      return (
        <span className="font-mono text-[0.65rem] text-[var(--tessera-green)]">{String(v)}</span>
      );
    case "num":
      return <span className="tabular-nums">{String(v)}</span>;
    default:
      return <span className="truncate">{String(v)}</span>;
  }
}

function TablePanel({
  title,
  explain,
  columns,
  rows,
  selected,
  onSelect,
}: {
  title: string;
  explain?: TabExplain | null;
  columns: TabColumn[];
  rows: TabRow[];
  selected: string;
  onSelect: (id: string) => void;
}) {
  return (
    <Card className="flex min-w-0 flex-col">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-1.5 text-[0.82rem] font-medium">
          {title}
          <ExplainInfo title={title} explain={explain} />
        </CardTitle>
      </CardHeader>
      <CardContent className="min-w-0 overflow-x-auto">
        <table className="w-full text-[0.72rem]">
          <thead>
            <tr className="border-b border-[var(--border)] text-left text-[var(--muted-foreground)]">
              {columns.map((c) => (
                <th
                  key={c.key}
                  className={`whitespace-nowrap py-1.5 pr-3 font-medium ${
                    c.align === "right" ? "text-right" : ""
                  }`}
                >
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.id}
                onClick={() => onSelect(r.id)}
                className={`cursor-pointer border-b border-[var(--border)]/50 transition-colors hover:bg-[var(--tessera-muted)]/40 ${
                  selected === r.id ? "bg-[var(--tessera-muted)]/60" : ""
                }`}
              >
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className={`py-1.5 pr-3 align-middle ${c.align === "right" ? "text-right" : ""}`}
                  >
                    <Cell col={c} cells={r.cells} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------ detail panel */

function DetailPanel({ detail, cta }: { detail: TabDetail; cta: string }) {
  return (
    <Card className="flex flex-col xl:sticky xl:top-4">
      <CardHeader className="gap-1 pb-2">
        <div className="text-[0.6rem] font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">
          {detail.eyebrow}
        </div>
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-1.5 text-sm">
            {detail.title}
            <ExplainInfo title={detail.title} explain={detail.explain} />
          </CardTitle>
          {detail.status_label ? (
            <Badge tone={tone(detail.status_tone)}>{detail.status_label}</Badge>
          ) : null}
        </div>
        {detail.summary ? (
          <p className="text-[0.68rem] leading-snug text-[var(--muted-foreground)]">
            {detail.summary}
          </p>
        ) : null}
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <dl className="flex flex-col gap-1 text-[0.7rem]">
          {detail.fields.map((f) => (
            <div key={f.label} className="flex items-center justify-between gap-2">
              <dt className="shrink-0 text-[var(--muted-foreground)]">{f.label}</dt>
              <dd className={`min-w-0 truncate text-right ${f.tone ? `text-${f.tone}` : ""}`}>
                {f.tone ? (
                  <Badge tone={tone(f.tone)}>{f.value}</Badge>
                ) : (
                  <span className="tabular-nums">{f.value}</span>
                )}
              </dd>
            </div>
          ))}
        </dl>

        {detail.lists.map((l) => (
          <div key={l.title} className="flex flex-col gap-1">
            <div className="text-[0.6rem] font-semibold uppercase tracking-wider text-[var(--muted-foreground)]">
              {l.title}
            </div>
            <ul className="flex flex-col gap-1 text-[0.7rem]">
              {l.items.map((it, i) => {
                const item = it as { label: string; sub?: string; badge?: string; tone?: string };
                return (
                  <li key={`${l.title}-${i}`} className="flex items-center justify-between gap-2">
                    <span className="min-w-0 truncate">
                      {item.label}
                      {item.sub ? (
                        <span className="ml-1 text-[0.58rem] text-[var(--muted-foreground)]">
                          {item.sub}
                        </span>
                      ) : null}
                    </span>
                    {item.badge ? <Badge tone={tone(item.tone)}>{item.badge}</Badge> : null}
                  </li>
                );
              })}
            </ul>
          </div>
        ))}

        <div className="flex flex-col gap-1 pt-1">
          {detail.actions.map((a, i) =>
            i === detail.actions.length - 1 ? (
              <Button
                key={a}
                size="sm"
                className="h-8 w-full justify-center gap-2 border border-[#5b4bbd] bg-[#4c3fb0]/40 text-xs text-[#c4b5fd] hover:bg-[#4c3fb0]/60"
              >
                {a}
              </Button>
            ) : (
              <button
                key={a}
                type="button"
                className="flex items-center gap-2 rounded-md px-1.5 py-1 text-left text-[0.72rem] text-[var(--tessera-green)] transition-colors hover:bg-[var(--tessera-muted)]"
              >
                {a}
              </button>
            ),
          )}
          {cta ? <span className="sr-only">{cta}</span> : null}
        </div>
      </CardContent>
    </Card>
  );
}

/* --------------------------------------------------------------- sections */

function MiniMultiline({
  series,
}: { series: { label: string; color: string; points: number[] }[] }) {
  const W = 100;
  const H = 36;
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-16 w-full"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      {series.map((s) => {
        const min = Math.min(...s.points);
        const max = Math.max(...s.points);
        const span = max - min || 1;
        const d = s.points
          .map(
            (p, i) =>
              `${i === 0 ? "M" : "L"}${((i / (s.points.length - 1)) * W).toFixed(1)},${(
                H - ((p - min) / span) * (H - 4) - 2
              ).toFixed(1)}`,
          )
          .join(" ");
        return (
          <path
            key={s.label}
            d={d}
            fill="none"
            stroke={s.color}
            strokeWidth="1.4"
            vectorEffect="non-scaling-stroke"
            strokeLinejoin="round"
          />
        );
      })}
    </svg>
  );
}

function Donut({ value, label }: { value: number; label?: string | null }) {
  const R = 30;
  const C = 2 * Math.PI * R;
  const t = value >= 0.9 ? "#10b981" : value >= 0.7 ? "#f59e0b" : "#ef4444";
  return (
    <div className="relative h-[84px] w-[84px] shrink-0">
      <svg viewBox="0 0 80 80" className="h-full w-full -rotate-90" aria-hidden="true">
        <circle cx="40" cy="40" r={R} fill="none" stroke="var(--tessera-border)" strokeWidth="9" />
        <circle
          cx="40"
          cy="40"
          r={R}
          fill="none"
          stroke={t}
          strokeWidth="9"
          strokeDasharray={`${value * C} ${C}`}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-base font-semibold tabular-nums">{Math.round(value * 100)}%</span>
        {label ? (
          <span className="text-[0.5rem] text-[var(--muted-foreground)]">{label}</span>
        ) : null}
      </div>
    </div>
  );
}

const BAR_BG: Record<BadgeTone, string> = {
  neutral: "bg-slate-400",
  navy: "bg-navy-500",
  gold: "bg-gold-500",
  success: "bg-emerald-500",
  warning: "bg-amber-500",
  danger: "bg-red-500",
  info: "bg-sky-500",
};

function ItemRow({ it }: { it: SectionItem }) {
  return (
    <li className="flex items-center justify-between gap-2 text-[0.7rem]">
      <span className="min-w-0">
        <span className="block truncate">{it.label}</span>
        {it.sub ? (
          <span className="block truncate text-[0.58rem] text-[var(--muted-foreground)]">
            {it.sub}
          </span>
        ) : null}
      </span>
      {it.value ? (
        it.badge_tone ? (
          <Badge tone={tone(it.badge_tone)}>{it.value}</Badge>
        ) : (
          <span className="shrink-0 tabular-nums text-[var(--muted-foreground)]">{it.value}</span>
        )
      ) : it.badge ? (
        <Badge tone={tone(it.badge_tone)}>{it.badge}</Badge>
      ) : null}
    </li>
  );
}

function Section({ s }: { s: TabSection }) {
  let body: ReactNode;
  switch (s.kind) {
    case "donut":
      body = (
        <div className="flex items-center gap-3">
          <Donut value={s.donut_value ?? 0} label={s.donut_label} />
          <ul className="flex min-w-0 flex-1 flex-col gap-1">
            {s.items.map((it) => (
              <ItemRow key={it.label} it={it} />
            ))}
          </ul>
        </div>
      );
      break;
    case "bars":
      body = (
        <ul className="flex flex-col gap-1.5">
          {s.bars.map((b) => {
            const bar = b as { label: string; value: number; tone?: string };
            return (
              <li key={bar.label} className="flex items-center gap-2 text-[0.68rem]">
                <span className="w-24 shrink-0 truncate">{bar.label}</span>
                <span className="h-[4px] flex-1 overflow-hidden rounded-full bg-[var(--tessera-border)]">
                  <span
                    className={`block h-full rounded-full ${BAR_BG[tone(bar.tone)]}`}
                    style={{ width: `${Math.round(bar.value * 100)}%` }}
                  />
                </span>
              </li>
            );
          })}
        </ul>
      );
      break;
    case "chart":
      body = (
        <div className="flex flex-col gap-1.5">
          <MiniMultiline
            series={s.series as { label: string; color: string; points: number[] }[]}
          />
          <ul className="flex flex-wrap gap-x-3 gap-y-0.5">
            {(s.series as { label: string; color: string }[]).map((se) => (
              <li
                key={se.label}
                className="flex items-center gap-1 text-[0.58rem] text-[var(--muted-foreground)]"
              >
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: se.color }} />
                {se.label}
              </li>
            ))}
          </ul>
        </div>
      );
      break;
    case "actions":
      body = (
        <div className="flex flex-col gap-0.5">
          {s.actions.map((a) => (
            <button
              key={a}
              type="button"
              className="flex items-center gap-2 rounded-md px-1.5 py-1 text-left text-[0.72rem] text-[var(--tessera-green)] transition-colors hover:bg-[var(--tessera-muted)]"
            >
              {a}
            </button>
          ))}
        </div>
      );
      break;
    default:
      body = (
        <ul className="flex flex-col gap-1.5">
          {s.items.map((it) => (
            <ItemRow key={it.label} it={it} />
          ))}
        </ul>
      );
  }
  return (
    <Card className="flex min-w-0 flex-col">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-1.5 text-[0.78rem] font-medium">
          {s.title}
          <ExplainInfo title={s.title} explain={s.explain} />
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col justify-between gap-2">
        {body}
        {s.cta ? (
          <button
            type="button"
            className="mt-1 self-start text-[0.62rem] text-[var(--tessera-green)] hover:underline"
          >
            {s.cta}
          </button>
        ) : null}
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------- view */

/**
 * Renders any command-bar catalogue tab (KPI strip + main table with a sticky
 * detail panel + bottom sections). Pages pass a page-specific `footer`.
 */
export function CatalogTabView({ tab, footer }: { tab: CatalogTab; footer?: ReactNode }) {
  const [selected, setSelected] = useState(tab.rows[0]?.id ?? "");

  return (
    <div className="flex flex-col gap-2">
      {/* KPI strip */}
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
        {tab.kpis.map((k) => (
          <KpiTile key={k.label} k={k} />
        ))}
      </div>

      <div className="grid gap-2 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-w-0 flex-col gap-2">
          <TablePanel
            title={tab.table_title}
            explain={tab.table_explain}
            columns={tab.columns}
            rows={tab.rows}
            selected={selected}
            onSelect={setSelected}
          />
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
            {tab.sections.map((s) => (
              <Section key={s.title} s={s} />
            ))}
          </div>
        </div>

        {tab.detail ? <DetailPanel detail={tab.detail} cta="" /> : null}
      </div>

      {footer}
    </div>
  );
}
