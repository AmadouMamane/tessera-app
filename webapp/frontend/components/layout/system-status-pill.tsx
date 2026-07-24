"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { LedgerIntegrityText } from "@/components/layout/ledger-integrity";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
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

const STATUS_STYLE: Record<StatusKind, { dot: string }> = {
  ok: {
    dot: "bg-green-500 dark:bg-green-400",
  },
  degraded: {
    dot: "bg-amber-500 dark:bg-amber-400",
  },
  down: {
    dot: "bg-red-500 dark:bg-red-400",
  },
};

export interface SystemStatusState {
  status: StatusKind;
  modelLabel: string;
  hosting: string;
  environment: string | undefined;
  integrity: Awaited<ReturnType<typeof fetchAuditIntegrity>> | undefined;
}

interface SystemStatusTriggerProps {
  state: SystemStatusState;
  active: boolean;
  controls: string;
  onToggle: () => void;
  className?: string;
}

export function useSystemStatusState(): SystemStatusState {
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

  return {
    status,
    modelLabel: model.label,
    hosting: modelHostingShort(model),
    environment: health?.environment,
    integrity,
  };
}

export function SystemStatusTrigger({
  state,
  active,
  controls,
  onToggle,
  className,
}: SystemStatusTriggerProps) {
  const t = useTranslations("systemStatus");
  const th = useTranslations("health.status");
  const style = STATUS_STYLE[state.status];
  const label = t("triggerWithStatus", { status: th(state.status) });

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={label}
          aria-expanded={active}
          aria-controls={controls}
          data-state={active ? "open" : "closed"}
          onClick={onToggle}
          className={cn(
            "relative inline-flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg border border-transparent bg-transparent text-[var(--tessera-text-muted)] outline-none transition-colors after:pointer-events-none after:absolute after:left-1/2 after:-bottom-[1.625rem] after:h-px after:w-5 after:-translate-x-1/2 after:bg-transparent after:transition-colors hover:text-[var(--tessera-text)] focus-visible:ring-2 focus-visible:ring-[var(--ring)] data-[state=open]:text-[var(--tessera-green)] data-[state=open]:after:bg-[var(--tessera-green)]",
            className,
          )}
        >
          <Activity className="h-[18px] w-[18px]" strokeWidth={1.75} aria-hidden />
          <span
            aria-hidden
            className={cn(
              "absolute right-1 top-1 h-1.5 w-1.5 rounded-full ring-2 ring-[var(--tessera-bg)]",
              style.dot,
            )}
          />
        </button>
      </TooltipTrigger>
      <TooltipContent side="bottom" sideOffset={10}>
        {label}
      </TooltipContent>
    </Tooltip>
  );
}

export function SystemStatusPanel({
  state,
  titleId,
}: {
  state: SystemStatusState;
  titleId: string;
}) {
  const t = useTranslations("systemStatus");
  const tf = useTranslations("appFooter");
  const environment = environmentLabel(state.environment, t);

  return (
    <>
      <div className="px-2.5 pb-2 pt-1.5">
        <p id={titleId} className="text-sm font-semibold text-[var(--tessera-text)]">
          {t("title")}
        </p>
        <p className="mt-1 text-xs leading-relaxed text-[var(--tessera-text-muted)]">
          {t("description")}
        </p>
      </div>
      <dl className="border-[var(--tessera-border)] border-t text-[0.72rem]">
        <StatusRow label={t("environment")} value={environment} />
        <StatusRow label={t("model")} value={`${state.modelLabel} · ${state.hosting}`} />
        <StatusRow label={t("residence")} value={t("residenceValue")} />
        <div className="px-2.5 py-3">
          <dt className="text-[var(--tessera-text-muted)]">{t("ledger")}</dt>
          <dd className="mt-1.5 min-w-0 leading-relaxed text-[var(--tessera-text)] [&>span]:flex-wrap">
            <LedgerIntegrityText data={state.integrity} t={tf} />
          </dd>
        </div>
      </dl>
    </>
  );
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[7rem_minmax(0,1fr)] items-center gap-3 border-[var(--tessera-border)] border-b px-2.5 py-2.5">
      <dt className="text-[var(--tessera-text-muted)]">{label}</dt>
      <dd className="min-w-0 text-right leading-snug text-[var(--tessera-text)]">{value}</dd>
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
