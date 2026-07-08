import { GitBranch, ShieldCheck, ShieldX } from "lucide-react";

import type { AuditIntegrity } from "@/lib/api/schemas";

type FooterT = (key: string, values?: Record<string, number>) => string;

interface LedgerIntegrityTextProps {
  data?: AuditIntegrity | null;
  t: FooterT;
}

/**
 * Tree-aware ledger wording shared by the footer and the system-status popover.
 * Content integrity is not the same signal as total-order linearity.
 */
export function LedgerIntegrityText({ data, t }: LedgerIntegrityTextProps) {
  const contentIntact = data?.verified ?? null;
  const length = data?.length ?? null;
  const linear = data?.linear ?? true;
  const forks = data?.fork_count ?? 0;
  const orphans = data?.orphan_count ?? 0;
  const attested = data?.attested ?? false;

  if (contentIntact === null) {
    return <span className="inline-flex items-center gap-1.5">{t("checking")}</span>;
  }

  if (!contentIntact) {
    return (
      <span className="inline-flex items-center gap-1.5 text-red-400">
        <ShieldX className="h-3 w-3" />
        {t("integrityBroken")}
      </span>
    );
  }

  if (linear) {
    return (
      <span className="inline-flex items-center gap-1.5 text-emerald-400">
        <ShieldCheck className="h-3 w-3" />
        {t("integrityOk", { n: length ?? 0 })}
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 text-amber-400">
      <GitBranch className="h-3 w-3" />
      {t(attested ? "integrityForkedAttested" : "integrityForkedPending", { forks, orphans })}
    </span>
  );
}
