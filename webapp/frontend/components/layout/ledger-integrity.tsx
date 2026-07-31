import { GitBranch, ShieldCheck, ShieldX } from "lucide-react";
import { useFormatter } from "next-intl";

import type { AuditIntegrity } from "@/lib/api/schemas";

type FooterT = (key: string, values?: Record<string, number | string>) => string;

interface LedgerIntegrityTextProps {
  data?: AuditIntegrity | null;
  t: FooterT;
}

/**
 * Tree-aware ledger wording shared by the footer and the system-status popover.
 * Content integrity is not the same signal as total-order linearity.
 *
 * The badge also states HOW FRESH its claim is. Content integrity is verified incrementally
 * against a checkpoint — the ledger is append-only, so a verified prefix stays verified, and
 * re-hashing 25 634 rows on every page load cost a second. That is sound, but only because a
 * periodic pass re-walks the whole chain. A checkpoint trusted in silence would be an assumption
 * wearing the clothes of a proof, so the badge publishes the age of the last full walk and the
 * number of entries verified incrementally since. The reader judges it; we do not judge it for
 * them.
 */
export function LedgerIntegrityText({ data, t }: LedgerIntegrityTextProps) {
  const format = useFormatter();
  const contentIntact = data?.verified ?? null;
  const length = data?.length ?? null;
  const linear = data?.linear ?? true;
  const forks = data?.fork_count ?? 0;
  const orphans = data?.orphan_count ?? 0;
  const attested = data?.attested ?? false;
  const fullVerifiedAt = data?.full_verified_at ?? null;
  const sinceFull = data?.entries_since_full ?? 0;

  const freshness = fullVerifiedAt
    ? t(sinceFull > 0 ? "integrityFreshnessSince" : "integrityFreshness", {
        ago: format.relativeTime(new Date(fullVerifiedAt)),
        n: sinceFull,
      })
    : null;

  if (contentIntact === null) {
    return <span className="inline-flex items-center gap-1.5">{t("checking")}</span>;
  }

  if (!contentIntact) {
    return (
      <span className="inline-flex items-center gap-1.5 text-[var(--tessera-fg-danger)]">
        <ShieldX className="h-3 w-3" />
        {t("integrityBroken")}
      </span>
    );
  }

  if (linear) {
    return (
      <span className="inline-flex items-center gap-1.5 text-[var(--tessera-fg-success)]">
        <ShieldCheck className="h-3 w-3" />
        {t("integrityOk", { n: length ?? 0 })}
        {freshness ? <span className="text-muted-foreground">{freshness}</span> : null}
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 text-[var(--tessera-fg-warning)]">
      <GitBranch className="h-3 w-3" />
      {t(attested ? "integrityForkedAttested" : "integrityForkedPending", { forks, orphans })}
      {freshness ? <span className="text-muted-foreground">{freshness}</span> : null}
    </span>
  );
}
