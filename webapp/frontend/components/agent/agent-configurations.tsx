"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronRight,
  Copy,
  ExternalLink,
  Info,
  MoreHorizontal,
  Plus,
  RotateCcw,
  Save,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";
import { Download } from "lucide-react";
import type { Route } from "next";
import { useLocale, useTranslations } from "next-intl";
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Link } from "@/i18n/navigation";
import {
  fetchAgentConfigurations,
  fetchReadiness,
  saveAgentConfigurations,
} from "@/lib/api/client";
import type { AgentConfigurations as Data } from "@/lib/api/schemas";
import { cn } from "@/lib/cn";
import { useAgentId } from "@/lib/use-agent-id";
import { AgentCrossLinks } from "./agent-cross-links";
import { DefineInstanceBanner } from "./define-instance-banner";

type Field = NonNullable<Data["identity"]>["left"][number];
type Slider = NonNullable<Data["behavior"]>["sliders"][number];
type Runtime = NonNullable<Data["behavior"]>["runtime"];
// `null` is a real value (ADR 0031): it UNSETS a sampling slider — the
// parameter is no longer sent and the backend default serves.
type Override = string | number | boolean | string[] | null;

/** Pending edits keyed by field key; effective value = override ?? server value. */
type Draft = Record<string, Override>;

interface Ctx {
  draft: Draft;
  setField: (key: string, serverValue: Override, value: Override) => void;
}

export function AgentConfigurations() {
  const t = useTranslations("agentConfigurations");
  const locale = useLocale();
  const qc = useQueryClient();
  const agentId = useAgentId();
  const queryKey = ["agent-configurations", agentId, locale];
  const { data } = useQuery({
    queryKey,
    queryFn: ({ signal }) => fetchAgentConfigurations(agentId, locale, signal),
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  const [draft, setDraft] = useState<Draft>({});
  const [error, setError] = useState(false);
  const save = useMutation({
    mutationFn: (changes: Draft) => saveAgentConfigurations(agentId, changes, locale),
    onSuccess: (fresh) => {
      setError(false);
      setDraft({});
      qc.setQueryData(queryKey, fresh);
    },
    onError: () => setError(true),
  });
  // Archive is a standalone durable toggle (it must not clobber pending edits).
  const archiveMut = useMutation({
    mutationFn: (changes: Draft) => saveAgentConfigurations(agentId, changes, locale),
    onSuccess: (fresh) => qc.setQueryData(queryKey, fresh),
  });

  const setField = (key: string, serverValue: Override, value: Override) => {
    setDraft((prev) => {
      const next = { ...prev };
      if (eq(value, serverValue)) delete next[key];
      else next[key] = value;
      return next;
    });
  };

  const dirty = Object.keys(draft).length > 0;
  const ctx: Ctx = { draft, setField };

  if (!data?.available) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-sm text-[var(--tessera-text-muted)]">
        {data ? t("unavailable") : t("loading")}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 pb-2 text-[var(--tessera-text)]">
      <AgentCrossLinks page="configurations" />
      <Header
        data={data}
        dirty={dirty}
        saving={save.isPending}
        error={error}
        onSave={() => save.mutate(draft)}
        onReset={() => setDraft({})}
      />
      <DefineInstanceBanner
        definition={data.definition}
        governanceBanner={data.governance_banner}
        instanceLabel="Configuration pour cet agent (instance)"
        instanceHint="éditable · gouvernée en production"
      />
      <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="min-w-0 overflow-hidden rounded-lg border border-[var(--tessera-border)] bg-[linear-gradient(180deg,rgba(8,28,48,0.94),rgba(5,20,35,0.94))] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
          <FieldSection block={data.identity} ctx={ctx} />
          <FieldSection block={data.model} ctx={ctx} />
          <Behavior data={data} ctx={ctx} />
          <FieldSection block={data.routing} ctx={ctx} compact />
          <Tags
            data={data}
            ctx={ctx}
            onArchive={() => archiveMut.mutate({ archived: !(data.tags?.archived ?? false) })}
            archiving={archiveMut.isPending}
          />
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

function MoreMenu({ data, label }: { data: Data; label: string }) {
  const [open, setOpen] = useState(false);
  const ref = useDismiss(
    open,
    useCallback(() => setOpen(false), []),
  );
  const exportJson = () => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "tessera-agent-configuration.json";
    link.click();
    URL.revokeObjectURL(url);
    setOpen(false);
  };
  const itemCls =
    "flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-[0.74rem] text-[var(--tessera-text-muted)] hover:bg-[var(--tessera-bg)] hover:text-[var(--tessera-text)]";
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={label}
        onClick={() => setOpen((o) => !o)}
        className="grid h-9 w-10 place-items-center rounded-md border border-[var(--tessera-border-strong)] bg-[var(--tessera-bg)] text-[var(--tessera-text)]"
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-30 mt-1 w-56 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-1 shadow-lg"
        >
          <button type="button" role="menuitem" onClick={exportJson} className={itemCls}>
            <Download className="h-3.5 w-3.5" /> Exporter la configuration (JSON)
          </button>
          <Link href="/configurer/parametres" role="menuitem" className={itemCls}>
            <ExternalLink className="h-3.5 w-3.5" /> Paramètres avancés
          </Link>
        </div>
      ) : null}
    </div>
  );
}

function eq(a: Override, b: Override): boolean {
  if (Array.isArray(a) && Array.isArray(b))
    return a.length === b.length && a.every((v, i) => v === b[i]);
  return a === b;
}

function Header({
  data,
  dirty,
  saving,
  error,
  onSave,
  onReset,
}: {
  data: Data;
  dirty: boolean;
  saving: boolean;
  error: boolean;
  onSave: () => void;
  onReset: () => void;
}) {
  const t = useTranslations("agentConfigurations");
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
        {error ? (
          <span className="text-[0.72rem] text-red-300">{t("saveError")}</span>
        ) : !dirty ? (
          <span className="text-[0.72rem] text-emerald-300">{actions?.saved}</span>
        ) : null}
        {dirty ? (
          <button
            type="button"
            onClick={onReset}
            disabled={saving}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-[var(--tessera-border-strong)] bg-[var(--tessera-bg)] px-3 text-xs font-medium text-[var(--tessera-text)] disabled:opacity-50"
          >
            <RotateCcw className="h-3.5 w-3.5" /> {actions?.reset}
          </button>
        ) : null}
        {data.governed ? (
          // Production: model/behaviour changes are governed - route the pending
          // edit to Release Control (RBAC + versioned + dual-control) instead of
          // a silent inline save.
          <Link
            href="/agir/release-control"
            className="inline-flex h-9 items-center gap-2 rounded-md border border-[#d98b1f]/55 bg-[linear-gradient(180deg,#f4c76a,#b87923)] px-4 text-xs font-semibold text-[#08111d]"
          >
            <ShieldCheck className="h-3.5 w-3.5" />
            {actions?.propose ?? "Proposer un changement"}
          </Link>
        ) : (
          <button
            type="button"
            onClick={onSave}
            disabled={!dirty || saving}
            className="inline-flex h-9 items-center gap-2 rounded-md border border-cyan-400/45 bg-[linear-gradient(180deg,#58d6df,#2597a6)] px-4 text-xs font-semibold text-[#04131b] shadow-[0_8px_20px_rgba(37,151,166,0.18)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Save className="h-3.5 w-3.5" />
            {actions?.save}
          </button>
        )}
        <MoreMenu data={data} label={actions?.more ?? "Plus d'options"} />
      </div>
    </div>
  );
}

function FieldSection({
  block,
  ctx,
  compact = false,
}: {
  block?: {
    title: string;
    left: Field[];
    right: Field[];
    link?: { label: string; href: string };
  };
  ctx: Ctx;
  compact?: boolean;
}) {
  if (!block) return null;
  return (
    <div className={cn("border-b border-[var(--tessera-border)] px-5 py-2.5", compact && "py-2")}>
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <h2 className="font-sans text-[0.92rem] font-semibold text-[var(--tessera-text)]">
          {block.title}
        </h2>
        {block.link ? (
          <Link
            href={block.link.href as "/configurer/modeles"}
            className="inline-flex items-center gap-1 text-[0.68rem] text-[#5fd0c6] hover:text-white"
          >
            {block.link.label} <ChevronRight className="h-3 w-3" />
          </Link>
        ) : null}
      </div>
      <div className="grid gap-x-12 gap-y-2 lg:grid-cols-2">
        <FieldColumn fields={block.left} ctx={ctx} compact={compact} />
        <FieldColumn fields={block.right} ctx={ctx} compact={compact} />
      </div>
    </div>
  );
}

function FieldColumn({
  fields,
  ctx,
  compact,
}: {
  fields: Field[];
  ctx: Ctx;
  compact?: boolean;
}) {
  return (
    <div className={cn("flex flex-col", compact ? "gap-1" : "gap-1.5")}>
      {fields.map((field) => (
        <LabeledControl
          key={field.key ?? `${field.label}-${field.value}`}
          field={field}
          ctx={ctx}
        />
      ))}
    </div>
  );
}

const FIELD_BOX =
  "relative flex items-center rounded-md border border-[var(--tessera-border)] bg-[rgba(5,20,35,0.76)] px-3 text-[0.78rem] text-[var(--tessera-text)] shadow-[inset_0_1px_0_rgba(255,255,255,0.025)]";
// Editable controls get a clear interactive affordance (hover + focus glow);
// read-only fields stay flat + dimmed so the two are visually distinguishable.
const EDIT_BOX = `${FIELD_BOX} transition-colors hover:border-[#5fd0c6]/45 focus-within:border-[#5fd0c6]/70 focus-within:ring-1 focus-within:ring-[#5fd0c6]/25`;
const READONLY_BOX =
  "relative flex items-center rounded-md border border-dashed border-[var(--tessera-border)]/70 bg-[rgba(5,20,35,0.4)] px-3 text-[0.78rem] text-[var(--tessera-text-muted)]";

function LabeledControl({ field, ctx }: { field: Field; ctx: Ctx }) {
  const locale = useLocale();
  const editable = field.editable && field.key;
  const current = editable ? String(ctx.draft[field.key as string] ?? field.value) : field.value;
  const onLabel = locale === "de" ? "Aktiviert" : locale === "en" ? "Enabled" : "Activé";
  const offLabel = locale === "de" ? "Deaktiviert" : locale === "en" ? "Disabled" : "Désactivée";

  let control: ReactNode;
  if (editable && field.kind === "textarea") {
    control = (
      <textarea
        value={current}
        aria-label={field.label}
        onChange={(e) => ctx.setField(field.key as string, field.value, e.target.value)}
        className={cn(EDIT_BOX, "min-h-[44px] cursor-text resize-none py-1.5 leading-snug")}
        rows={2}
      />
    );
  } else if (editable && field.kind === "select") {
    control = (
      <span className={cn(EDIT_BOX, "h-7 cursor-pointer pr-2")}>
        <select
          value={current}
          aria-label={field.label}
          onChange={(e) => ctx.setField(field.key as string, field.value, e.target.value)}
          className="w-full cursor-pointer appearance-none bg-transparent text-[0.78rem] text-[var(--tessera-text)] outline-none"
        >
          {(field.options ?? [current]).map((o) => (
            <option key={o} value={o} className="bg-[#0a1f33] text-[var(--tessera-text)]">
              {o}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none ml-auto h-3.5 w-3.5 shrink-0 text-[#5fd0c6]" />
      </span>
    );
  } else if (editable && field.kind === "toggle") {
    // `field.on` is the locale-independent state; `field.value` is the localized
    // display label (so it can't be string-compared).
    const baseOn = field.on ?? false;
    const on = (ctx.draft[field.key as string] ?? baseOn) === true;
    control = (
      <span className={cn(EDIT_BOX, "h-7 justify-between")}>
        <span className="text-[var(--tessera-text-muted)]">{on ? onLabel : offLabel}</span>
        <Toggle
          on={on}
          onToggle={() => ctx.setField(field.key as string, baseOn, !on)}
          label={field.label}
        />
      </span>
    );
  } else if (editable) {
    control = (
      <input
        value={current}
        aria-label={field.label}
        onChange={(e) => ctx.setField(field.key as string, field.value, e.target.value)}
        className={cn(EDIT_BOX, "h-7 cursor-text")}
      />
    );
  } else {
    // Read-only: copy fields keep an interactive button; pure facts read as dashed/dimmed.
    const box = field.kind === "copy" ? FIELD_BOX : READONLY_BOX;
    control = (
      <span
        className={cn(
          box,
          field.kind === "textarea" ? "min-h-[38px] items-start py-1.5 leading-snug" : "h-7",
        )}
      >
        <span className={cn("min-w-0 truncate", field.kind === "textarea" && "whitespace-normal")}>
          {current}
        </span>
        {field.badge ? (
          <span className="ml-auto shrink-0 rounded-full bg-[var(--tessera-muted)] px-2 py-0.5 text-[0.62rem] font-semibold text-[var(--tessera-text)]">
            {field.badge}
          </span>
        ) : null}
        {field.kind === "copy" ? (
          <button
            type="button"
            aria-label="Copier l'identifiant"
            onClick={() => navigator.clipboard?.writeText(current)}
            className="ml-auto flex shrink-0 items-center gap-1 rounded border border-[var(--tessera-border)] px-1.5 py-0.5 text-[0.62rem] text-[var(--tessera-text-muted)] transition-colors hover:border-[#5fd0c6]/50 hover:text-[#5fd0c6]"
          >
            <Copy className="h-3.5 w-3.5" /> Copier
          </button>
        ) : null}
        {field.kind === "info" ? (
          <Info className="ml-auto h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)]" />
        ) : null}
      </span>
    );
  }

  return (
    <div className="grid gap-1">
      <span className="text-[0.68rem] font-medium text-[var(--tessera-text-muted)]">
        {field.label}
      </span>
      {control}
    </div>
  );
}

function Behavior({ data, ctx }: { data: Data; ctx: Ctx }) {
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
            <SelectRow key={item.key ?? item.label} field={item} ctx={ctx} />
          ))}
          {b.sliders.slice(0, 2).map((item) => (
            <SliderRow key={item.key ?? item.label} item={item} ctx={ctx} runtime={b.runtime} />
          ))}
        </div>
        <div className="grid gap-2">
          {b.sliders.slice(2).map((item) => (
            <SliderRow key={item.key ?? item.label} item={item} ctx={ctx} runtime={b.runtime} />
          ))}
          <ToolsRow tools={b.tools} />
        </div>
      </div>
      {b.runtime ? (
        <div
          data-testid="behavior-runtime"
          className="mt-2 rounded-md border border-[var(--tessera-border)] bg-[rgba(5,20,35,0.5)] px-3 py-2"
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[0.68rem] font-medium text-[var(--tessera-text)]">
              {b.runtime.label}
            </span>
            <span className="rounded border border-cyan-400/40 bg-cyan-400/10 px-1.5 text-[0.62rem] text-cyan-300">
              {b.runtime.backend}
            </span>
            <span className="text-[0.62rem] tabular-nums text-[var(--tessera-text-muted)]">
              {b.runtime.model}
            </span>
          </div>
          <p className="mt-1 text-[0.64rem] text-[var(--tessera-text-muted)]">{b.runtime.note}</p>
        </div>
      ) : null}
      {b.escalation ? (
        // ADR 0033 — the escalation threshold: the one guard behaviour the
        // business tunes. Unset says where the org default comes from.
        <div
          data-testid="behavior-escalation"
          className="mt-2 rounded-md border border-[var(--tessera-border)] bg-[rgba(5,20,35,0.5)] px-3 py-2"
        >
          <span className="text-[0.68rem] font-medium text-[var(--tessera-text)]">
            {b.escalation.title}
          </span>
          <div className="mt-1.5">
            <SliderRow item={b.escalation.slider} ctx={ctx} runtime={b.runtime} />
          </div>
          <p className="mt-1 text-[0.64rem] text-[var(--tessera-text-muted)]">
            {b.escalation.note}
          </p>
        </div>
      ) : null}
      {b.retrieval ? (
        // ADR 0035 — retrieval depth + reranking, per agent, same seam.
        <div
          data-testid="behavior-retrieval"
          className="mt-2 rounded-md border border-[var(--tessera-border)] bg-[rgba(5,20,35,0.5)] px-3 py-2"
        >
          <span className="text-[0.68rem] font-medium text-[var(--tessera-text)]">
            {b.retrieval.title}
          </span>
          <div className="mt-1.5 grid gap-2">
            <SliderRow item={b.retrieval.slider} ctx={ctx} runtime={b.runtime} />
            <LabeledControl field={b.retrieval.toggle} ctx={ctx} />
          </div>
          <p className="mt-1 text-[0.64rem] text-[var(--tessera-text-muted)]">{b.retrieval.note}</p>
        </div>
      ) : null}
      {b.memory ? (
        // ADR 0036 — memory tier + window, per agent, same seam.
        <div
          data-testid="behavior-memory"
          className="mt-2 rounded-md border border-[var(--tessera-border)] bg-[rgba(5,20,35,0.5)] px-3 py-2"
        >
          <span className="text-[0.68rem] font-medium text-[var(--tessera-text)]">
            {b.memory.title}
          </span>
          <div className="mt-1.5 grid gap-2">
            <SelectRow field={b.memory.select} ctx={ctx} />
            <SliderRow item={b.memory.slider} ctx={ctx} runtime={b.runtime} />
          </div>
          <p className="mt-1 text-[0.64rem] text-[var(--tessera-text-muted)]">{b.memory.note}</p>
        </div>
      ) : null}
      <p className="mt-2 flex items-center gap-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
        <Info className="h-3.5 w-3.5 text-cyan-300" />
        {b.note}
      </p>
    </div>
  );
}

function ToolsRow({ tools }: { tools: NonNullable<Data["behavior"]>["tools"] }) {
  const [open, setOpen] = useState(false);
  const ref = useDismiss(
    open,
    useCallback(() => setOpen(false), []),
  );
  const items = tools.items ?? [];
  return (
    <div className="grid grid-cols-[170px_1fr] items-center gap-3">
      <span className="text-[0.68rem] text-[var(--tessera-text-muted)]">{tools.label}</span>
      <div className="relative" ref={ref}>
        <button
          type="button"
          aria-haspopup="menu"
          aria-expanded={open}
          onClick={() => setOpen((o) => !o)}
          className="flex h-7 w-full items-center justify-between rounded-md border border-[var(--tessera-border)] bg-[rgba(5,20,35,0.76)] px-3 text-[0.76rem] text-[var(--tessera-text)] transition-colors hover:border-[#5fd0c6]/45"
        >
          {tools.value}
          <ChevronDown
            className={cn("h-3.5 w-3.5 text-[#5fd0c6] transition-transform", open && "rotate-180")}
          />
        </button>
        {open ? (
          <div
            role="menu"
            className="absolute right-0 z-30 mt-1 w-64 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-1.5 shadow-lg"
          >
            <ul className="flex flex-col gap-0.5">
              {items.map((tool) => (
                <li
                  key={tool}
                  className="flex items-center gap-2 rounded px-2 py-1.5 text-[0.72rem] text-[var(--tessera-text)]"
                >
                  <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
                  {tool}
                </li>
              ))}
              {items.length === 0 ? (
                <li className="px-2 py-1.5 text-[0.72rem] text-[var(--tessera-text-muted)]">
                  Aucun outil autorisé
                </li>
              ) : null}
            </ul>
            {tools.href ? (
              <Link
                href={tools.href as Route}
                className="mt-1 flex items-center gap-1 border-t border-[var(--tessera-border)] px-2 pt-1.5 text-[0.68rem] text-[#5fd0c6] hover:text-white"
              >
                Gérer dans les garde-fous <ChevronRight className="h-3 w-3" />
              </Link>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function SelectRow({ field, ctx }: { field: Field; ctx: Ctx }) {
  const current = field.key ? String(ctx.draft[field.key] ?? field.value) : field.value;
  return (
    <div className="grid grid-cols-[140px_1fr] items-center gap-3">
      <span className="flex flex-wrap items-center gap-1.5 text-[0.68rem] text-[var(--tessera-text-muted)]">
        {field.label}
        {field.badge ? (
          // ADR 0032 — the select says HOW it takes effect (prompt injection /
          // hard token cap), next to the control — never silently cosmetic.
          <span className="rounded border border-cyan-400/40 bg-cyan-400/10 px-1 text-[0.58rem] text-cyan-300">
            {field.badge}
          </span>
        ) : null}
      </span>
      <span className="relative flex h-7 items-center rounded-md border border-[var(--tessera-border)] bg-[rgba(5,20,35,0.76)] px-3 text-[0.76rem] text-[var(--tessera-text)]">
        <select
          value={current}
          aria-label={field.label}
          onChange={(e) => field.key && ctx.setField(field.key, field.value, e.target.value)}
          className="w-full appearance-none bg-transparent outline-none"
        >
          {(field.options ?? [current]).map((o) => (
            <option key={o} value={o} className="bg-[#0a1f33] text-[var(--tessera-text)]">
              {o}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none ml-auto h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
      </span>
    </div>
  );
}

function SliderRow({ item, ctx, runtime }: { item: Slider; ctx: Ctx; runtime?: Runtime }) {
  const t = useTranslations("agentConfigurations");
  const draftVal = item.key ? ctx.draft[item.key] : undefined;
  const isDraftNumber = typeof draftVal === "number";
  const isDraftReset = draftVal === null;
  // ADR 0031 — unset means NOT SENT: the backend default serves and no number
  // is invented. The server value (item.num) may itself be unset.
  const serverValue: number | null = item.unset ? null : (item.num ?? 0);
  const unset = isDraftReset || (serverValue === null && !isDraftNumber);
  const num = isDraftNumber ? draftVal : (serverValue ?? 0);
  const max = item.max ?? 1;
  // ADR 0033 — a knob may define what "unset" means for it (e.g. the org
  // default for the escalation threshold); the backend default is the default.
  const display = unset
    ? (item.unset_label ?? t("backendDefault"))
    : Number(num.toFixed(2)).toString().replace(".", ",");
  const pct = unset ? 0 : Math.round((100 * num) / max);
  const applied = item.applied !== false;
  return (
    <div className="grid grid-cols-[170px_84px_1fr_auto] items-center gap-3">
      <span className="flex items-center gap-1.5 text-[0.68rem] text-[var(--tessera-text-muted)]">
        {item.label}
        {!applied && runtime ? (
          <span
            title={runtime.note}
            className="rounded border border-amber-400/40 bg-amber-400/10 px-1 text-[0.58rem] text-amber-300"
          >
            {t("notApplied", { backend: runtime.backend })}
          </span>
        ) : null}
      </span>
      <span
        className={cn(
          "text-[0.76rem] tabular-nums",
          unset ? "text-[var(--tessera-text-muted)] italic" : "text-[var(--tessera-text)]",
        )}
      >
        {display}
      </span>
      <input
        type="range"
        min={item.min ?? 0}
        max={max}
        step={item.step ?? 0.05}
        value={num}
        aria-label={item.label}
        onChange={(e) =>
          item.key && ctx.setField(item.key, serverValue, Number.parseFloat(e.target.value))
        }
        className={cn(
          "h-1.5 w-full cursor-pointer appearance-none rounded-full bg-[var(--tessera-border)] accent-cyan-300 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-cyan-300",
          unset && "opacity-50",
        )}
        style={{
          background: `linear-gradient(90deg, #67e8f9 ${pct}%, var(--tessera-border) ${pct}%)`,
        }}
      />
      {!unset && item.key ? (
        <button
          type="button"
          aria-label={`${t("resetToDefault")} — ${item.label}`}
          title={t("resetToDefault")}
          onClick={() => item.key && ctx.setField(item.key, serverValue, null)}
          className="text-[var(--tessera-text-muted)] transition-colors hover:text-[var(--tessera-text)]"
        >
          <RotateCcw className="h-3 w-3" />
        </button>
      ) : (
        <span className="w-3" />
      )}
    </div>
  );
}

function Tags({
  data,
  ctx,
  onArchive,
  archiving,
}: { data: Data; ctx: Ctx; onArchive: () => void; archiving: boolean }) {
  const tags = data.tags;
  const [adding, setAdding] = useState("");
  const serverTags = useMemo(() => tags?.tags ?? [], [tags]);
  if (!tags) return null;
  const current = (ctx.draft.tags as string[] | undefined) ?? serverTags;
  const commit = (next: string[]) => ctx.setField("tags", serverTags, next);
  const add = () => {
    const v = adding.trim();
    if (v && !current.includes(v)) commit([...current, v]);
    setAdding("");
  };
  return (
    <div className="px-5 py-2.5">
      <h2 className="mb-1.5 font-sans text-[0.92rem] font-semibold text-[var(--tessera-text)]">
        {tags.title}
      </h2>
      <div className="grid gap-x-12 gap-y-2 lg:grid-cols-2">
        <div>
          <p className="mb-1.5 text-[0.68rem] text-[var(--tessera-text-muted)]">Tags</p>
          <div className="flex min-h-[34px] flex-wrap items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[rgba(5,20,35,0.76)] px-2 py-1">
            {current.map((tag) => (
              <span
                key={tag}
                className="inline-flex h-6 items-center gap-1 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-muted)] px-2 text-[0.7rem] text-[var(--tessera-text)]"
              >
                {tag}
                <button
                  type="button"
                  aria-label={`Retirer ${tag}`}
                  onClick={() => commit(current.filter((x) => x !== tag))}
                  className="text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
            <input
              value={adding}
              onChange={(e) => setAdding(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  add();
                }
              }}
              placeholder={tags.add_tag}
              aria-label={tags.add_tag}
              className="h-6 min-w-[110px] flex-1 bg-transparent text-[0.7rem] text-[var(--tessera-text)] outline-none placeholder:text-[var(--tessera-text-muted)]"
            />
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
              onClick={add}
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
          onClick={onArchive}
          disabled={archiving}
          aria-pressed={tags.archived ?? false}
          className={cn(
            "inline-flex h-8 items-center gap-2 rounded-md border px-3 text-[0.68rem] font-medium disabled:opacity-50",
            tags.archived
              ? "border-emerald-500/45 bg-emerald-500/10 text-emerald-300"
              : "border-red-500/45 bg-red-500/10 text-red-300",
          )}
        >
          <Trash2 className="h-3.5 w-3.5" /> {tags.archive}
        </button>
      </div>
    </div>
  );
}

function Status({ data }: { data: Data }) {
  const s = data.status;
  // Real liveness: the /readyz probe verifies the chat backend is reachable
  // (503/error when the LLM is down). Parallel + cached, so it never blocks the
  // page; the row marked `live` is replaced with this real signal.
  const readiness = useQuery({
    queryKey: ["agent-readiness"],
    queryFn: ({ signal }) => fetchReadiness(signal),
    retry: false,
    staleTime: 10_000,
    refetchInterval: 30_000,
  });
  if (!s) return null;
  const liveReady = !readiness.isError && readiness.data?.status === "ready";
  return (
    <Panel>
      <div className="mb-2.5 flex items-center gap-3 border-b border-[var(--tessera-border)] pb-2">
        <h2 className="font-sans text-[0.95rem] font-semibold text-[var(--tessera-text)]">
          {s.title}
        </h2>
        <span
          className={cn(
            "rounded-full px-2.5 py-1 text-[0.65rem] font-semibold",
            s.badge_tone === "crit"
              ? "bg-red-500/15 text-red-300"
              : "bg-emerald-500/15 text-emerald-300",
          )}
        >
          {s.badge}
        </span>
      </div>
      <div className="grid gap-2">
        {s.rows.map((row) => {
          // Replace the placeholder liveness with the real readiness probe.
          const online = row.live ? liveReady : row.online;
          const value = row.live
            ? readiness.isLoading
              ? "Verification..."
              : liveReady
                ? "En ligne"
                : "LLM injoignable"
            : row.value;
          return (
            <div key={row.label} className="grid grid-cols-[1fr_auto] gap-3 text-[0.72rem]">
              <span className="text-[var(--tessera-text-muted)]">{row.label}</span>
              <span className="flex items-center gap-2 text-right text-[var(--tessera-text)]">
                {row.badge ? (
                  <Badge>{value}</Badge>
                ) : (
                  <span className={cn(row.live && !online && "text-red-300")}>{value}</span>
                )}
                {online ? <span className="h-2 w-2 rounded-full bg-emerald-400" /> : null}
                {row.live && !online && !readiness.isLoading ? (
                  <span className="h-2 w-2 rounded-full bg-red-400" />
                ) : null}
                {row.info ? (
                  <Info className="h-3.5 w-3.5 text-[var(--tessera-text-muted)]" />
                ) : null}
              </span>
            </div>
          );
        })}
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
        <Link
          href="/prouver/audit-logs"
          className="text-[0.76rem] font-medium text-cyan-300 hover:text-cyan-200"
        >
          {h.cta}
        </Link>
      </div>
      <div className="grid gap-2.5">
        {h.items.map((item, index) => (
          <div
            key={`${item.time}-${item.label}-${index}`}
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
            className="group grid cursor-pointer grid-cols-[1fr_auto] items-center gap-3 rounded-md border border-[var(--tessera-border)] bg-[rgba(5,20,35,0.5)] px-3 py-2 text-left transition-colors hover:border-[#5fd0c6]/50 hover:bg-[rgba(95,208,198,0.06)]"
          >
            <span className="min-w-0">
              <span className="block text-[0.76rem] font-medium text-[var(--tessera-text)] group-hover:text-[#5fd0c6]">
                {link.title}
              </span>
              <span className="mt-0.5 block text-[0.68rem] leading-snug text-[var(--tessera-text-muted)]">
                {link.desc}
              </span>
            </span>
            <ExternalLink className="h-4 w-4 shrink-0 text-[var(--tessera-text-muted)] transition-colors group-hover:text-[#5fd0c6]" />
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

function Toggle({ on, onToggle, label }: { on: boolean; onToggle: () => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={onToggle}
      className={cn(
        "ml-auto inline-flex h-4 w-8 items-center rounded-full p-0.5 transition-colors",
        on ? "bg-cyan-400/60" : "bg-[var(--tessera-border)]",
      )}
    >
      <span
        className={cn(
          "h-3 w-3 rounded-full bg-white transition-transform",
          on ? "translate-x-4" : "translate-x-0",
        )}
      />
    </button>
  );
}
