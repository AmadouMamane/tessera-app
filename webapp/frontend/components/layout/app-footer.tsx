"use client";

import { useQuery } from "@tanstack/react-query";
import { GitBranch } from "lucide-react";
import { useTranslations } from "next-intl";

import { LedgerIntegrityText } from "@/components/layout/ledger-integrity";
import { fetchAuditIntegrity } from "@/lib/api/client";

/**
 * Global auditability footer (P1) — rendered once by the AppShell, so every cockpit
 * page carries it. States the source of truth (YAML · Git) and the **real**
 * hash-chain integrity of the audit log (verified live via `/audit/integrity`,
 * never cosmetic).
 *
 * TESS-LEDGER-001 — the verdict is now tree-aware, so it stops overstating tampering:
 * ✓ content verified + a single chain; ⑂ content verified but the total order carries
 * historical forks/orphans (attested or pending) — NOT a forgery; ✗ (red) only when a
 * present row was actually edited (content integrity fails). Never a fabricated "verified".
 */
export function AppFooter() {
  const t = useTranslations("appFooter");
  const { data } = useQuery({
    queryKey: ["audit-integrity-footer"],
    queryFn: ({ signal }) => fetchAuditIntegrity(signal),
    staleTime: 60_000,
  });

  return (
    <footer className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-1 border-t border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-4 py-1.5 text-[0.62rem] text-[var(--tessera-text-muted)]">
      <span className="inline-flex items-center gap-1.5">
        <GitBranch className="h-3 w-3" />
        {t("sourceOfTruth")}
      </span>
      <span className="text-[var(--tessera-border-strong)]">·</span>
      <LedgerIntegrityText data={data} t={t} />
      <span className="text-[var(--tessera-border-strong)]">·</span>
      <span>{t("env")}</span>
      <span className="ml-auto">{t("note")}</span>
    </footer>
  );
}
