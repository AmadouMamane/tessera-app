"use client";

import { useQuery } from "@tanstack/react-query";
import { GitBranch, ShieldCheck, ShieldX } from "lucide-react";
import { useTranslations } from "next-intl";

import { fetchAuditIntegrity } from "@/lib/api/client";

/**
 * Global auditability footer (P1) — rendered once by the AppShell, so every cockpit
 * page carries it. States the source of truth (YAML · Git) and the **real**
 * hash-chain integrity of the audit log (verified live via `/audit/integrity`,
 * never cosmetic). The integrity verdict is shown honestly: ✓ when the chain
 * verifies, ✗ (broken) otherwise — never a fabricated "verified".
 */
export function AppFooter() {
  const t = useTranslations("appFooter");
  const { data } = useQuery({
    queryKey: ["audit-integrity-footer"],
    queryFn: ({ signal }) => fetchAuditIntegrity(signal),
    staleTime: 60_000,
  });

  const verified = data?.verified ?? null;
  const length = data?.length ?? null;

  return (
    <footer className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-1 border-t border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-4 py-1.5 text-[0.62rem] text-[var(--tessera-text-muted)]">
      <span className="inline-flex items-center gap-1.5">
        <GitBranch className="h-3 w-3" />
        {t("sourceOfTruth")}
      </span>
      <span className="text-[var(--tessera-border-strong)]">·</span>
      {verified === null ? (
        <span className="inline-flex items-center gap-1.5">{t("checking")}</span>
      ) : verified ? (
        <span className="inline-flex items-center gap-1.5 text-emerald-400">
          <ShieldCheck className="h-3 w-3" />
          {t("integrityOk", { n: length ?? 0 })}
        </span>
      ) : (
        <span className="inline-flex items-center gap-1.5 text-red-400">
          <ShieldX className="h-3 w-3" />
          {t("integrityBroken")}
        </span>
      )}
      <span className="text-[var(--tessera-border-strong)]">·</span>
      <span>{t("env")}</span>
      <span className="ml-auto">{t("note")}</span>
    </footer>
  );
}
