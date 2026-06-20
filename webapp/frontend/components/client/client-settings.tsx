"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Download, Globe, Lock, ShieldCheck, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { fetchClientSettings, mutateClientSetting } from "@/lib/api/client";
import { cn } from "@/lib/cn";

const GROUP_ICON = { notifications: Bell, privacy: ShieldCheck, security: Lock };
const PRIVACY_MAIL = "privacy@credit-aurore.example";

export function ClientSettings() {
  const t = useTranslations("clientSettings");
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["client-settings"],
    queryFn: ({ signal }) => fetchClientSettings(signal),
    staleTime: 30_000,
  });
  const save = useMutation({
    mutationFn: mutateClientSetting,
    onSuccess: (fresh) => qc.setQueryData(["client-settings"], fresh),
  });

  if (!data) return <Loading />;
  if (!data.available) return <Unavailable text={t("unavailable")} />;

  const values = data.values ?? {};
  const language = typeof values.language === "string" ? values.language : "fr";

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 pb-2 text-[var(--tessera-text)]">
      <p className="text-sm text-[var(--tessera-text-muted)]">{t("subtitle")}</p>

      <section className="rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4">
        <div className="flex items-center gap-2">
          <Globe className="h-4 w-4 text-[var(--tessera-text-muted)]" />
          <h2 className="text-sm font-semibold text-[var(--tessera-text)]">
            {t("group.language")}
          </h2>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {(data.languages ?? ["fr", "de", "en"]).map((lng) => (
            <button
              key={lng}
              type="button"
              onClick={() => save.mutate({ key: "language", value: lng })}
              className={cn(
                "rounded-md border px-3 py-1.5 text-xs font-medium transition-colors",
                language === lng
                  ? "border-[var(--tessera-green)] bg-[var(--tessera-surface-elevated)] text-white"
                  : "border-[var(--tessera-border)] bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)] hover:text-[var(--tessera-text)]",
              )}
            >
              {t(`lang.${lng}`)}
            </button>
          ))}
        </div>
      </section>

      {(data.groups ?? []).map((group) => {
        const Icon = GROUP_ICON[group.key as keyof typeof GROUP_ICON] ?? Bell;
        return (
          <section
            key={group.key}
            className="rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4"
          >
            <div className="flex items-center gap-2">
              <Icon className="h-4 w-4 text-[var(--tessera-text-muted)]" />
              <h2 className="text-sm font-semibold text-[var(--tessera-text)]">
                {t(`group.${group.key}`)}
              </h2>
            </div>
            <div className="mt-2 divide-y divide-[var(--tessera-border)]">
              {group.items.map((item) => (
                <Toggle
                  key={item}
                  label={t(`item.${item}`)}
                  hint={t(`hint.${item}`)}
                  checked={values[item] === true}
                  disabled={save.isPending}
                  onChange={(checked) => save.mutate({ key: item, value: checked })}
                />
              ))}
            </div>
          </section>
        );
      })}

      <section className="rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-4">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-[var(--tessera-text-muted)]" />
          <h2 className="text-sm font-semibold text-[var(--tessera-text)]">{t("group.gdpr")}</h2>
        </div>
        <p className="mt-1 text-[0.72rem] leading-relaxed text-[var(--tessera-text-muted)]">
          {t("gdpr.intro")}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <a
            href={`mailto:${PRIVACY_MAIL}?subject=${encodeURIComponent(t("gdpr.exportSubject"))}`}
            className="inline-flex items-center gap-2 rounded-md border border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-3 py-2 text-xs text-[var(--tessera-text)] transition-colors hover:border-[var(--tessera-green)]/50"
          >
            <Download className="h-4 w-4" /> {t("gdpr.export")}
          </a>
          <a
            href={`mailto:${PRIVACY_MAIL}?subject=${encodeURIComponent(t("gdpr.eraseSubject"))}`}
            className="inline-flex items-center gap-2 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300 transition-colors hover:bg-red-500/15"
          >
            <Trash2 className="h-4 w-4" /> {t("gdpr.erase")}
          </a>
        </div>
      </section>

      <footer className="mt-1 flex flex-wrap items-center gap-x-5 border-t border-[var(--tessera-border)] pt-2 text-[0.68rem] text-[var(--tessera-text-muted)]">
        <span>
          {t("updatedAt")}: {data.updated_at ?? "—"}
        </span>
        {data.footer ? <span>{t("footer.source", { src: data.footer.source })}</span> : null}
      </footer>
    </div>
  );
}

function Toggle({
  label,
  hint,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  hint: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <div className="min-w-0">
        <p className="text-[0.82rem] font-medium text-[var(--tessera-text)]">{label}</p>
        <p className="text-[0.68rem] text-[var(--tessera-text-muted)]">{hint}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative h-5 w-9 shrink-0 rounded-full transition-colors disabled:opacity-50",
          checked ? "bg-[var(--tessera-green)]" : "bg-[var(--tessera-border)]",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform",
            checked ? "translate-x-[18px]" : "translate-x-0.5",
          )}
        />
      </button>
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

function Unavailable({ text }: { text: ReactNode }) {
  return (
    <div className="flex min-h-[200px] flex-1 items-center justify-center rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] p-8 text-center text-sm text-[var(--tessera-text-muted)]">
      {text}
    </div>
  );
}
