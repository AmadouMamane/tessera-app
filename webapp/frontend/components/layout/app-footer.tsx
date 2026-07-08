"use client";

import { useQuery } from "@tanstack/react-query";
import { GitBranch, Lock, ShieldCheck, ShieldX } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

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

  const contentIntact = data?.verified ?? null; // `verified` is the content-integrity alias
  const length = data?.length ?? null;
  const linear = data?.linear ?? true;
  const forks = data?.fork_count ?? 0;
  const orphans = data?.orphan_count ?? 0;
  const attested = data?.attested ?? false;
  // Q5 — the footer gains ONLY a compact "· scellé <t>" suffix when a real seal verifies; nothing
  // otherwise (no partial text). The full opposability facet lives on TE-01 / Prouver.
  const sealVerified = data?.seal_state === "verified";
  const sealedAt = data?.sealed_at ?? null;

  let integrity: ReactNode;
  if (contentIntact === null) {
    integrity = <span className="inline-flex items-center gap-1.5">{t("checking")}</span>;
  } else if (!contentIntact) {
    // A present row was edited/forged — the real alarm.
    integrity = (
      <span className="inline-flex items-center gap-1.5 text-red-400">
        <ShieldX className="h-3 w-3" />
        {t("integrityBroken")}
      </span>
    );
  } else if (linear) {
    integrity = (
      <span className="inline-flex items-center gap-1.5 text-emerald-400">
        <ShieldCheck className="h-3 w-3" />
        {t("integrityOk", { n: length ?? 0 })}
      </span>
    );
  } else {
    // Content intact, but the total order carries historical forks/orphans — not tampering.
    integrity = (
      <span className="inline-flex items-center gap-1.5 text-amber-400">
        <GitBranch className="h-3 w-3" />
        {t(attested ? "integrityForkedAttested" : "integrityForkedPending", { forks, orphans })}
      </span>
    );
  }

  return (
    <footer className="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-1 border-t border-[var(--tessera-border)] bg-[var(--tessera-bg)] px-4 py-1.5 text-[0.62rem] text-[var(--tessera-text-muted)]">
      <span className="inline-flex items-center gap-1.5">
        <GitBranch className="h-3 w-3" />
        {t("sourceOfTruth")}
      </span>
      <span className="text-[var(--tessera-border-strong)]">·</span>
      {integrity}
      {sealVerified && sealedAt ? (
        <span className="inline-flex items-center gap-1 text-emerald-400/90">
          <Lock className="h-3 w-3" />
          {t("sealSuffix", { t: sealedAt.slice(0, 16).replace("T", " ") })}
        </span>
      ) : null}
      <span className="text-[var(--tessera-border-strong)]">·</span>
      <span>{t("env")}</span>
      <span className="ml-auto">{t("note")}</span>
    </footer>
  );
}
