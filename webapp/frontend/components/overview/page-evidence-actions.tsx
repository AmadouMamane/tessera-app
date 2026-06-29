"use client";

import { Download, PackageCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { exportSnapshot } from "@/lib/evidence-export";

/**
 * Page-level export / evidence actions — "Exporter rapport" + "Générer le dossier de
 * preuves". They used to float right in the cockpit header (row 2); rendered here so
 * a page can place them in its body, just ABOVE the SR-01 rail. Same wiring and look
 * as the former header buttons: a click runs `exportSnapshot(kind)`.
 */
export function PageEvidenceActions({ className }: { className?: string } = {}) {
  const ta = useTranslations("overview.actions");
  return (
    <div className={cn("flex flex-wrap items-center justify-end gap-2", className)}>
      <EvidenceButton kind="export" label={ta("exportReport")} variant="outline" />
      <EvidenceButton kind="evidence" label={ta("generateEvidencePack")} variant="accent" />
    </div>
  );
}

function EvidenceButton({
  kind,
  label,
  variant,
}: {
  kind: "export" | "evidence";
  label: string;
  variant: "outline" | "accent";
}) {
  const [pending, setPending] = useState(false);
  const Icon = kind === "export" ? Download : PackageCheck;
  async function onClick() {
    setPending(true);
    try {
      await exportSnapshot(kind);
    } finally {
      setPending(false);
    }
  }
  return (
    <Button
      type="button"
      variant={variant}
      size="sm"
      disabled={pending}
      onClick={onClick}
      className={cn(
        "h-9 rounded-md px-3 text-xs shadow-none",
        variant === "outline" &&
          "border-[var(--tessera-border-strong)] bg-[var(--tessera-surface)] text-[var(--tessera-text)] hover:bg-[var(--tessera-muted)]",
        variant === "accent" &&
          "border border-[#007a55] bg-[#005c42] text-[#d6f0e3] hover:bg-[#006d4e]",
      )}
    >
      <Icon className="h-4 w-4" />
      {label}
    </Button>
  );
}
