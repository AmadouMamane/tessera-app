"use client";

import * as Popover from "@radix-ui/react-popover";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Cpu, ServerCog, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { LedgerIntegrityText } from "@/components/layout/ledger-integrity";
import { fetchAuditIntegrity, fetchHealth } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import {
  CHAT_MODEL_EVENT,
  DEFAULT_CHAT_MODEL,
  findModel,
  getStoredModel,
  modelHostingShort,
} from "@/lib/models";

type StatusKind = "ok" | "degraded" | "down";

const STATUS_STYLE: Record<StatusKind, { pill: string; dot: string }> = {
  ok: {
    pill: "border-green-500/20 bg-green-500/10 text-green-600 dark:border-green-400/20 dark:bg-green-400/10 dark:text-green-400",
    dot: "bg-green-500 dark:bg-green-400",
  },
  degraded: {
    pill: "border-amber-500/20 bg-amber-500/10 text-amber-600 dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-400",
    dot: "bg-amber-500 dark:bg-amber-400",
  },
  down: {
    pill: "border-red-500/20 bg-red-500/10 text-red-600 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-400",
    dot: "bg-red-500 dark:bg-red-400",
  },
};

interface SystemStatusPillProps {
  className?: string;
}

export function SystemStatusPill({ className }: SystemStatusPillProps) {
  const t = useTranslations("systemStatus");
  const th = useTranslations("health.status");
  const tf = useTranslations("appFooter");
  const [modelId, setModelId] = useState(DEFAULT_CHAT_MODEL);
  const [mounted, setMounted] = useState(false);

  const { data: health, isError } = useQuery({
    queryKey: ["health-badge"],
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: 15_000,
    retry: 1,
    staleTime: 10_000,
  });
  const { data: integrity } = useQuery({
    queryKey: ["audit-integrity-footer"],
    queryFn: ({ signal }) => fetchAuditIntegrity(signal),
    staleTime: 60_000,
  });

  useEffect(() => {
    setMounted(true);
    setModelId(getStoredModel());
    const sync = () => setModelId(getStoredModel());
    window.addEventListener(CHAT_MODEL_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(CHAT_MODEL_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  const status: StatusKind =
    isError || health?.status === "down"
      ? "down"
      : health?.status === "degraded"
        ? "degraded"
        : "ok";
  const model = findModel(mounted ? modelId : DEFAULT_CHAT_MODEL);
  const hosting = modelHostingShort(model);
  const environment = environmentLabel(health?.environment, t);
  const style = STATUS_STYLE[status];

  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button
          type="button"
          aria-label={t("triggerLabel")}
          className={cn(
            "inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-2.5 py-1 text-[0.65rem] font-medium outline-none transition-colors hover:brightness-110 focus-visible:ring-2 focus-visible:ring-[var(--ring)]",
            style.pill,
            className,
          )}
        >
          <span className={cn("h-1.5 w-1.5 rounded-full", style.dot)} />
          {th(status)}
          <ChevronDown className="h-3 w-3 opacity-70" aria-hidden />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="end"
          sideOffset={8}
          collisionPadding={12}
          className={cn(
            "z-50 w-80 rounded-lg border border-[var(--tessera-border)] bg-[var(--popover)] p-3 text-left shadow-[var(--shadow-card)]",
            "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
          )}
        >
          <p className="font-semibold text-[var(--tessera-text)] text-xs">{t("title")}</p>
          <dl className="mt-3 space-y-2 text-[0.72rem]">
            <StatusRow icon={ServerCog} label={t("environment")} value={environment} />
            <StatusRow icon={Cpu} label={t("model")} value={`${model.label} · ${hosting}`} />
            <StatusRow icon={ShieldCheck} label={t("residence")} value={t("residenceValue")} />
            <div className="grid grid-cols-[6.5rem_1fr] items-start gap-3 border-[var(--tessera-border)] border-t pt-2">
              <dt className="text-[var(--tessera-text-muted)]">{t("ledger")}</dt>
              <dd className="min-w-0 text-[var(--tessera-text)]">
                <LedgerIntegrityText data={integrity} t={tf} />
              </dd>
            </div>
          </dl>
          <Popover.Arrow className="fill-[var(--tessera-border)]" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

function StatusRow({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Cpu;
  label: string;
  value: string;
}) {
  return (
    <div className="grid grid-cols-[6.5rem_1fr] items-center gap-3">
      <dt className="text-[var(--tessera-text-muted)]">{label}</dt>
      <dd className="flex min-w-0 items-center gap-1.5 text-[var(--tessera-text)]">
        <Icon className="h-3.5 w-3.5 shrink-0 text-[var(--tessera-text-muted)]" aria-hidden />
        <span className="truncate">{value}</span>
      </dd>
    </div>
  );
}

function environmentLabel(environment: string | undefined, t: (key: string) => string): string {
  if (!environment) return t("unknown");
  if (environment === "production") return t("environmentValue.production");
  if (environment === "staging") return t("environmentValue.staging");
  if (environment === "ci") return t("environmentValue.ci");
  if (environment === "local") return t("environmentValue.local");
  return environment.charAt(0).toUpperCase() + environment.slice(1);
}
