"use client";

import { useQuery } from "@tanstack/react-query";
import { Check, Cpu, Lock } from "lucide-react";
import { useSession } from "next-auth/react";
import { useLocale, useTranslations } from "next-intl";
import { useTheme } from "next-themes";
import { type ReactNode, useEffect, useState, useTransition } from "react";

import { ThemeSwatch } from "@/components/layout/theme-swatch";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { usePathname, useRouter } from "@/i18n/navigation";
import { LOCALE_LABELS, type Locale, routing } from "@/i18n/routing";
import { fetchHealth } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import {
  CHAT_MODELS,
  DEFAULT_CHAT_MODEL,
  getStoredModel,
  isModelAllowedForRole,
  modelHosting,
  setStoredModel,
} from "@/lib/models";

const REDUCE_MOTION_KEY = "tessera.reduceMotion";

interface SegmentOption {
  value: string;
  label: string;
  icon?: ReactNode;
}

function Segmented({
  options,
  value,
  onChange,
  disabled,
}: {
  options: SegmentOption[];
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="inline-flex rounded-lg border border-[var(--border)] bg-[var(--muted)]/40 p-1">
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            disabled={disabled}
            aria-pressed={active}
            onClick={() => onChange(opt.value)}
            className={cn(
              "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-50",
              active
                ? "bg-[var(--card)] text-[var(--foreground)] shadow-sm"
                : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]",
            )}
          >
            {opt.icon}
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--background)]",
        checked ? "bg-blue-600" : "bg-[var(--muted)]",
      )}
    >
      <span
        className={cn(
          "inline-block h-5 w-5 transform rounded-full bg-white shadow-sm transition-transform",
          checked ? "translate-x-[1.375rem]" : "translate-x-0.5",
        )}
      />
    </button>
  );
}

function Row({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-6 py-3.5">
      <div className="flex flex-col gap-0.5">
        <span className="text-sm font-medium text-[var(--foreground)]">{title}</span>
        {hint ? <span className="text-xs text-[var(--muted-foreground)]">{hint}</span> : null}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

export function SettingsView() {
  const t = useTranslations("settings");
  const tTheme = useTranslations("common.theme");
  const locale = useLocale() as Locale;
  const router = useRouter();
  const pathname = usePathname();
  const { data: session } = useSession();
  const role = session?.user?.role ?? null;
  const [isPending, startTransition] = useTransition();

  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(false);
  const [chatModel, setChatModel] = useState(DEFAULT_CHAT_MODEL);

  useEffect(() => {
    setMounted(true);
    const stored = window.localStorage.getItem(REDUCE_MOTION_KEY) === "1";
    setReduceMotion(stored);
    document.documentElement.classList.toggle("reduce-motion", stored);
    setChatModel(getStoredModel());
  }, []);

  function changeMotion(next: boolean) {
    setReduceMotion(next);
    window.localStorage.setItem(REDUCE_MOTION_KEY, next ? "1" : "0");
    document.documentElement.classList.toggle("reduce-motion", next);
  }

  function changeModel(next: string) {
    // Gated (paid frontier) models are selectable only by the superadmin; the
    // server enforces it too, but don't even let the UI persist the choice.
    if (!isModelAllowedForRole(next, role)) return;
    setChatModel(next);
    setStoredModel(next);
  }

  const modelTags: Record<string, string> = {
    modelTagFast: t("modelTagFast"),
    modelTagCompact: t("modelTagCompact"),
    modelTagReasoning: t("modelTagReasoning"),
    modelTagBalanced: t("modelTagBalanced"),
    modelTagCapable: t("modelTagCapable"),
    modelTagFrontier: t("modelTagFrontier"),
  };

  function changeLocale(next: string) {
    if (next === locale) return;
    startTransition(() => router.replace(pathname, { locale: next as Locale }));
  }

  const health = useQuery({
    queryKey: ["health-settings"],
    queryFn: ({ signal }) => fetchHealth(signal),
    staleTime: 30_000,
    retry: 1,
  });
  const serviceUp = !health.isError && health.data?.status !== "down";

  // Superadmin-only: grant the `admin` role visibility of the failure synthesis.
  // Persisted server-side (DB) via the superadmin-gated settings route.
  const synthesisAccess = useQuery({
    queryKey: ["synthesis-access"],
    queryFn: async ({ signal }) => {
      const res = await fetch("/api/settings/synthesis-access", { signal });
      if (!res.ok) throw new Error("failed");
      return (await res.json()) as { enabled: boolean };
    },
    enabled: role === "superadmin",
    staleTime: 30_000,
    retry: 1,
  });
  const [synthAdmin, setSynthAdmin] = useState(false);
  useEffect(() => {
    if (synthesisAccess.data) setSynthAdmin(Boolean(synthesisAccess.data.enabled));
  }, [synthesisAccess.data]);

  async function changeSynthAdmin(next: boolean) {
    setSynthAdmin(next); // optimistic
    try {
      const res = await fetch("/api/settings/synthesis-access", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: next }),
      });
      if (!res.ok) setSynthAdmin(!next); // revert on failure
    } catch {
      setSynthAdmin(!next);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>{t("appearance")}</CardTitle>
          <CardDescription>{t("appearanceHint")}</CardDescription>
        </CardHeader>
        <CardContent className="divide-y divide-[var(--border)] pt-0">
          <Row title={t("theme")}>
            <Segmented
              value={mounted ? (theme ?? "system") : "system"}
              onChange={setTheme}
              options={[
                { value: "light", label: tTheme("light"), icon: <ThemeSwatch theme="light" /> },
                { value: "dark", label: tTheme("dark"), icon: <ThemeSwatch theme="dark" /> },
                {
                  value: "deep-night",
                  label: tTheme("slate"),
                  icon: <ThemeSwatch theme="deep-night" />,
                },
                {
                  value: "system",
                  label: tTheme("system"),
                  icon: <ThemeSwatch theme="system" />,
                },
              ]}
            />
          </Row>
          <Row title={t("language")}>
            <Segmented
              value={locale}
              disabled={isPending}
              onChange={changeLocale}
              options={routing.locales.map((l) => ({ value: l, label: LOCALE_LABELS[l].short }))}
            />
          </Row>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("display")}</CardTitle>
          <CardDescription>{t("displayHint")}</CardDescription>
        </CardHeader>
        <CardContent className="pt-0">
          <Row title={t("reduceMotion")} hint={t("reduceMotionHint")}>
            <Toggle checked={reduceMotion} onChange={changeMotion} label={t("reduceMotion")} />
          </Row>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("model")}</CardTitle>
          <CardDescription>{t("modelHint")}</CardDescription>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="grid gap-3 sm:grid-cols-2">
            {CHAT_MODELS.map((m) => {
              const active = (mounted ? chatModel : DEFAULT_CHAT_MODEL) === m.id;
              const tag = modelTags[m.tagKey] ?? "";
              // Gated models stay visible (the integration is on show) but are
              // locked for anyone who isn't the superadmin.
              const locked = m.gated === true && role !== "superadmin";
              return (
                <button
                  key={m.id}
                  type="button"
                  aria-pressed={active}
                  disabled={locked}
                  title={locked ? t("modelLockedHint") : undefined}
                  onClick={() => changeModel(m.id)}
                  className={cn(
                    "group relative flex flex-col gap-2 rounded-xl border p-4 text-left transition-all",
                    active
                      ? "border-gold-500/60 bg-gold-500/[0.06] shadow-[var(--shadow-card-glow)]"
                      : "border-[var(--border)] bg-[var(--muted)]/30 hover:bg-[var(--muted)]/50",
                    locked && "cursor-not-allowed opacity-60 hover:bg-[var(--muted)]/30",
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-2 font-medium text-[var(--foreground)]">
                      <Cpu className="h-4 w-4 text-gold-500" />
                      {m.label}
                    </span>
                    {locked ? (
                      <Lock className="h-3.5 w-3.5 text-[var(--muted-foreground)]" aria-hidden />
                    ) : active ? (
                      <Check className="h-4 w-4 text-gold-500" />
                    ) : null}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-[var(--muted-foreground)]">
                    <Badge tone="neutral">{m.params}</Badge>
                    <span>{modelHosting(m)}</span>
                  </div>
                  <span className="text-xs text-[var(--muted-foreground)]">
                    {locked ? t("modelLockedHint") : tag}
                  </span>
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {role === "superadmin" ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("access")}</CardTitle>
            <CardDescription>{t("accessHint")}</CardDescription>
          </CardHeader>
          <CardContent className="pt-0">
            <Row title={t("synthesisAccess")} hint={t("synthesisAccessHint")}>
              <Toggle
                checked={synthAdmin}
                onChange={changeSynthAdmin}
                label={t("synthesisAccess")}
              />
            </Row>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>{t("platform")}</CardTitle>
          <CardDescription>{t("platformHint")}</CardDescription>
        </CardHeader>
        <CardContent className="divide-y divide-[var(--border)] pt-0">
          <Row title={t("service")}>
            {health.isPending ? (
              <span className="text-sm text-[var(--muted-foreground)]">…</span>
            ) : (
              <Badge tone={serviceUp ? "success" : "danger"}>
                {serviceUp ? t("statusOk") : t("statusDown")}
              </Badge>
            )}
          </Row>
          <Row title={t("version")}>
            <span className="font-mono text-sm text-[var(--muted-foreground)]">
              {health.data?.version ?? "—"}
            </span>
          </Row>
          <Row title={t("environment")}>
            <Badge tone="info">{t("environmentValue")}</Badge>
          </Row>
        </CardContent>
      </Card>
    </div>
  );
}
