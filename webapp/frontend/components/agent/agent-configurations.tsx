"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronRight,
  Copy,
  ExternalLink,
  Info,
  MoreHorizontal,
  Plus,
  Save,
  Trash2,
} from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { Link } from "@/i18n/navigation";
import { fetchAgentConfigurations } from "@/lib/api/client";
import type { AgentConfigurations as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";

type Field = NonNullable<Data["identity"]>["left"][number];

export function AgentConfigurations() {
  const t = useTranslations("agentConfigurations");
  const { data } = useQuery({
    queryKey: ["agent-configurations"],
    queryFn: ({ signal }) => fetchAgentConfigurations(signal),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  if (!data?.available) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        {data ? t("unavailable") : t("loading")}
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      <Header data={data} />
      <div className="grid min-h-0 gap-3 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="min-w-0 overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[linear-gradient(180deg,rgba(8,28,48,0.94),rgba(5,20,35,0.94))] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
          <FieldSection block={data.identity} />
          <FieldSection block={data.model} />
          <Behavior data={data} />
          <FieldSection block={data.routing} compact />
          <Tags data={data} />
        </section>
        <aside className="flex min-w-0 flex-col gap-2.5">
          <Status data={data} />
          <ActiveModel data={data} />
          <Summary data={data} />
          <History data={data} />
          <LinksPanel data={data} />
        </aside>
      </div>
    </div>
  );
}

function Header({ data }: { data: Data }) {
  const actions = data.actions;
  return (
    <div className="flex min-h-[46px] flex-wrap items-start justify-between gap-3 border-b border-[var(--tessera-border)] pb-1.5">
      <div className="min-w-0">
        <h1 className="font-sans text-[1.55rem] font-semibold leading-tight tracking-normal text-[var(--tessera-text)]">
          {data.title}
        </h1>
        <p className="mt-0.5 text-[0.82rem] text-[var(--tessera-text-muted)]">{data.subtitle}</p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <button
          type="button"
          className="inline-flex h-9 items-center gap-2 rounded-md border border-cyan-400/45 bg-[linear-gradient(180deg,#58d6df,#2597a6)] px-4 text-xs font-semibold text-[#04131b] shadow-[0_8px_20px_rgba(37,151,166,0.18)]"
        >
          <Save className="h-3.5 w-3.5" />
          {actions?.save}
        </button>
        <button
          type="button"
          aria-label={actions?.more}
          className="grid h-9 w-10 place-items-center rounded-md border border-[var(--tessera-border-strong)] bg-[var(--tessera-bg)] text-[var(--tessera-text)]"
        >
          <MoreHorizontal className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

function FieldSection({
  block,
  compact = false,
}: {
  block?: { title: string; left: Field[]; right: Field[] };
  compact?: boolean;
}) {
  if (!block) return null;
  return (
    <div className={cn("border-b border-[var(--tessera-border)] px-5 py-2.5", compact && "py-2")}>
      <h2 className="mb-1.5 font-sans text-[0.92rem] font-semibold text-[var(--tessera-text)]">
        {block.title}
      </h2>
      <div className="grid gap-x-12 gap-y-2 lg:grid-cols-2">
        <FieldColumn fields={block.left} compact={compact} />
        <FieldColumn fields={block.right} compact={compact} />
      </div>
    </div>
  );
}

function FieldColumn({ fields, compact }: { fields: Field[]; compact?: boolean }) {
  return (
    <div className={cn("flex flex-col", compact ? "gap-1" : "gap-1.5")}>
      {fields.map((field) => (
        <LabeledControl key={`${field.label}-${field.value}`} field={field} />
      ))}
    </div>
  );
}

function LabeledControl({ field }: { field: Field }) {
  const isTextarea = field.kind === "textarea";
  return (
    <div className="grid gap-1">
      <span className="text-[0.68rem] font-medium text-[var(--tessera-text-muted)]">
        {field.label}
      </span>
      <span
        className={cn(
          "relative flex items-center rounded-md border border-[var(--tessera-border)] bg-[rgba(5,20,35,0.76)] px-3 text-[0.78rem] text-[var(--tessera-text)] shadow-[inset_0_1px_0_rgba(255,255,255,0.025)]",
          isTextarea ? "min-h-[38px] items-start py-1.5 leading-snug" : "h-7",
        )}
      >
        <span className={cn("min-w-0 truncate", isTextarea && "whitespace-normal")}>
          {field.value}
        </span>
        {field.badge ? (
          <span className="ml-auto shrink-0 rounded-full bg-[var(--tessera-muted)] px-2 py-0.5 text-[0.62rem] font-semibold text-[var(--tessera-text)]">
            {field.badge}
          </span>
        ) : null}
        {field.kind === "select" ? (
          <ChevronDown className="ml-auto h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)]" />
        ) : null}
        {field.kind === "copy" ? (
          <Copy className="ml-auto h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)]" />
        ) : null}
        {field.kind === "info" ? (
          <Info className="ml-auto h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)]" />
        ) : null}
        {field.kind === "toggle" ? <Toggle /> : null}
      </span>
    </div>
  );
}

function Behavior({ data }: { data: Data }) {
  const b = data.behavior;
  if (!b) return null;
  return (
    <div className="border-b border-[var(--tessera-border)] px-5 py-2.5">
      <h2 className="mb-1.5 font-sans text-[0.92rem] font-semibold text-[var(--tessera-text)]">
        {b.title}
      </h2>
      <div className="grid gap-x-12 gap-y-2 lg:grid-cols-2">
        <div className="grid gap-2">
          {b.selects.map((item) => (
            <div key={item.label} className="grid grid-cols-[140px_1fr] items-center gap-3">
              <span className="text-[0.68rem] text-[var(--tessera-text-muted)]">{item.label}</span>
              <span className="flex h-7 items-center justify-between rounded-md border border-[var(--tessera-border)] bg-[rgba(5,20,35,0.76)] px-3 text-[0.76rem] text-[var(--tessera-text)]">
                {item.value}
                <ChevronDown className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
              </span>
            </div>
          ))}
          {b.sliders.slice(0, 1).map((item) => (
            <SliderRow key={item.label} item={item} />
          ))}
        </div>
        <div className="grid gap-2">
          {b.sliders.slice(1).map((item) => (
            <SliderRow key={item.label} item={item} />
          ))}
          <div className="grid grid-cols-[170px_1fr] items-center gap-3">
            <span className="text-[0.68rem] text-[var(--tessera-text-muted)]">{b.tools.label}</span>
            <span className="flex h-7 items-center justify-between rounded-md border border-[var(--tessera-border)] bg-[rgba(5,20,35,0.76)] px-3 text-[0.76rem] text-[var(--tessera-text)]">
              {b.tools.value}
              <ChevronRight className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
            </span>
          </div>
        </div>
      </div>
      <p className="mt-2 flex items-center gap-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
        <Info className="h-3.5 w-3.5 text-cyan-300" />
        {b.note}
      </p>
    </div>
  );
}

function SliderRow({
  item,
}: {
  item: NonNullable<Data["behavior"]>["sliders"][number];
}) {
  return (
    <div className="grid grid-cols-[170px_44px_1fr] items-center gap-3">
      <span className="text-[0.68rem] text-[var(--tessera-text-muted)]">{item.label}</span>
      <span className="text-[0.76rem] tabular-nums text-[var(--tessera-text)]">{item.value}</span>
      <span className="relative h-1.5 rounded-full bg-[var(--tessera-border)]">
        <span
          className="absolute inset-y-0 left-0 rounded-full bg-cyan-300"
          style={{ width: `${item.pct}%` }}
        />
        <span
          className="absolute top-1/2 h-3 w-3 -translate-y-1/2 rounded-full bg-cyan-300 shadow-[0_0_12px_rgba(103,232,249,0.35)]"
          style={{ left: `calc(${item.pct}% - 6px)` }}
        />
      </span>
    </div>
  );
}

function Tags({ data }: { data: Data }) {
  const tags = data.tags;
  if (!tags) return null;
  return (
    <div className="px-5 py-2.5">
      <h2 className="mb-1.5 font-sans text-[0.92rem] font-semibold text-[var(--tessera-text)]">
        {tags.title}
      </h2>
      <div className="grid gap-x-12 gap-y-2 lg:grid-cols-2">
        <div>
          <p className="mb-1.5 text-[0.68rem] text-[var(--tessera-text-muted)]">Tags</p>
          <div className="flex h-8 items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[rgba(5,20,35,0.76)] px-2">
            {tags.tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex h-6 items-center gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-muted)] px-2 text-[0.7rem] text-[var(--tessera-text)]"
              >
                {tag}
                <span className="text-[var(--tessera-text-muted)]">x</span>
              </span>
            ))}
            <span className="ml-2 inline-flex items-center gap-1 text-[0.68rem] text-[var(--tessera-text-muted)]">
              <Plus className="h-3.5 w-3.5" /> {tags.add_tag}
            </span>
          </div>
        </div>
        <div>
          <p className="mb-1.5 text-[0.68rem] text-[var(--tessera-text-muted)]">
            {tags.metadata_label}
          </p>
          <div className="grid grid-cols-[1fr_auto] items-center gap-3">
            <span className="text-[0.76rem] text-[var(--tessera-text-muted)]">{tags.metadata}</span>
            <button
              type="button"
              className="inline-flex h-8 items-center gap-2 rounded-md border border-[var(--tessera-border-strong)] bg-[var(--tessera-bg)] px-4 text-xs font-medium text-[var(--tessera-text)]"
            >
              <Plus className="h-3.5 w-3.5" /> {tags.add_metadata}
            </button>
          </div>
        </div>
      </div>
      <div className="mt-2.5 flex flex-wrap items-center justify-between gap-3 border-t border-[var(--tessera-border)] pt-2">
        <p className="text-[0.66rem] text-[var(--tessera-text-muted)]">
          {tags.created} <span className="mx-2">-</span> {tags.modified}
        </p>
        <button
          type="button"
          className="inline-flex h-8 items-center gap-2 rounded-md border border-red-500/45 bg-red-500/10 px-3 text-[0.68rem] font-medium text-red-300"
        >
          <Trash2 className="h-3.5 w-3.5" /> {tags.archive}
        </button>
      </div>
    </div>
  );
}

function Status({ data }: { data: Data }) {
  const s = data.status;
  if (!s) return null;
  return (
    <Panel>
      <div className="mb-2.5 flex items-center gap-3 border-b border-[var(--tessera-border)] pb-2">
        <h2 className="font-sans text-[0.95rem] font-semibold text-[var(--tessera-text)]">
          {s.title}
        </h2>
        <span className="rounded-full bg-emerald-500/15 px-2.5 py-1 text-[0.65rem] font-semibold text-emerald-300">
          {s.badge}
        </span>
      </div>
      <div className="grid gap-2">
        {s.rows.map((row) => (
          <div key={row.label} className="grid grid-cols-[1fr_auto] gap-3 text-[0.72rem]">
            <span className="text-[var(--tessera-text-muted)]">{row.label}</span>
            <span className="flex items-center gap-2 text-right text-[var(--tessera-text)]">
              {row.badge ? <Badge>{row.value}</Badge> : row.value}
              {row.online ? <span className="h-2 w-2 rounded-full bg-emerald-400" /> : null}
              {row.info ? <Info className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" /> : null}
            </span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function ActiveModel({ data }: { data: Data }) {
  const m = data.active_model;
  if (!m) return null;
  return (
    <Panel>
      <h2 className="mb-2 font-sans text-[0.95rem] font-semibold text-[var(--tessera-text)]">
        {m.title}
      </h2>
      <div className="rounded-md border border-[var(--tessera-border)] bg-[rgba(5,20,35,0.72)] p-2.5">
        <div className="mb-2 flex items-center justify-between gap-2">
          <span className="truncate text-[0.9rem] font-medium text-[var(--tessera-text)]">
            {m.name}
          </span>
          <Badge>{m.provider}</Badge>
        </div>
        {m.rows.map((row) => (
          <div key={row.label} className="grid grid-cols-[1fr_auto] gap-2 text-[0.72rem]">
            <span className="text-[var(--tessera-text-muted)]">{row.label}</span>
            <span className="text-[var(--tessera-text)]">{row.value}</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function Summary({ data }: { data: Data }) {
  const s = data.summary;
  if (!s) return null;
  return (
    <Panel>
      <h2 className="mb-2 font-sans text-[0.95rem] font-semibold text-[var(--tessera-text)]">
        {s.title}
      </h2>
      <div className="grid gap-1.5">
        {s.rows.map((row) => (
          <div key={row.label} className="grid grid-cols-[1fr_1fr] gap-3 text-[0.74rem]">
            <span className="text-[var(--tessera-text-muted)]">{row.label}</span>
            <span className="text-[var(--tessera-text)]">{row.value}</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function History({ data }: { data: Data }) {
  const h = data.history;
  if (!h) return null;
  return (
    <Panel>
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="font-sans text-[0.95rem] font-semibold text-[var(--tessera-text)]">
          {h.title}
        </h2>
        <button type="button" className="text-[0.76rem] font-medium text-cyan-300">
          {h.cta}
        </button>
      </div>
      <div className="grid gap-2.5">
        {h.items.map((item, index) => (
          <div
            key={`${item.time}-${item.label}`}
            className="relative grid grid-cols-[34px_1fr] gap-2"
          >
            <span className="relative flex justify-center">
              <span className="grid h-7 w-7 place-items-center rounded-full border border-[#d98b1f] text-[#d98b1f]">
                <Save className="h-3.5 w-3.5" />
              </span>
              {index < h.items.length - 1 ? (
                <span className="absolute top-7 h-[24px] w-px bg-[#d98b1f]/45" />
              ) : null}
            </span>
            <span className="min-w-0">
              <span className="grid grid-cols-[1fr_auto] gap-2 text-[0.7rem] text-[var(--tessera-text-muted)]">
                <span>{item.time}</span>
                <span>{item.actor}</span>
              </span>
              <span className="mt-0.5 block text-[0.76rem] text-[var(--tessera-text)]">
                {item.label}
              </span>
            </span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function LinksPanel({ data }: { data: Data }) {
  const links = data.links;
  if (!links) return null;
  return (
    <Panel>
      <h2 className="mb-2 font-sans text-[0.95rem] font-semibold text-[var(--tessera-text)]">
        {links.title}
      </h2>
      <div className="grid gap-2.5">
        {links.items.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="grid grid-cols-[1fr_auto] gap-3 rounded-md text-left hover:text-cyan-200"
          >
            <span className="min-w-0">
              <span className="block text-[0.76rem] font-medium text-[var(--tessera-text)]">
                {link.title}
              </span>
              <span className="mt-0.5 block text-[0.68rem] leading-snug text-[var(--tessera-text-muted)]">
                {link.desc}
              </span>
            </span>
            <ExternalLink className="mt-1 h-4 w-4 text-[var(--tessera-text-muted)]" />
          </Link>
        ))}
      </div>
    </Panel>
  );
}

function Panel({ children }: { children: ReactNode }) {
  return (
    <section className="rounded-lg border border-[var(--tessera-border)] bg-[linear-gradient(180deg,rgba(8,28,48,0.92),rgba(5,20,35,0.92))] p-2.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      {children}
    </section>
  );
}

function Badge({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-full bg-cyan-500/10 px-2 py-0.5 text-[0.62rem] font-semibold text-cyan-300">
      {children}
    </span>
  );
}

function Toggle() {
  return (
    <span className="ml-auto inline-flex h-4 w-8 items-center rounded-full bg-cyan-400/35 p-0.5">
      <span className="ml-auto h-3 w-3 rounded-full bg-cyan-300" />
    </span>
  );
}
