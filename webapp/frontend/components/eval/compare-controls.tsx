"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { usePathname, useRouter } from "@/i18n/navigation";
import type { RunMeta } from "@/lib/api/schemas";
import { shortRunDate } from "@/lib/format";
import { findModel } from "@/lib/models";

function optionLabel(run: RunMeta): string {
  const model = run.model ? findModel(run.model).label : "—";
  const pct = Math.round(run.summary.pass_rate * 100);
  const date = shortRunDate(run.run_at);
  return `${date} · ${model} · ${pct}%`;
}

/**
 * Two run pickers (A / B) for the model comparison. Selection drives the URL
 * (?run=A&vs=B) so the server re-renders the comparison for any two runs the
 * user chooses — not just the latest per model.
 */
type CompareControlsProps = {
  runs: RunMeta[];
  aFile?: string;
  bFile?: string;
  labels: { a: string; b: string };
};

export function CompareControls(props: CompareControlsProps) {
  return (
    <Suspense
      fallback={
        <div className="flex flex-wrap items-end gap-4">
          <Skeleton className="h-9 w-64 rounded-md" />
          <span className="pb-2 text-sm text-[var(--muted-foreground)]">vs</span>
          <Skeleton className="h-9 w-64 rounded-md" />
        </div>
      }
    >
      <CompareControlsInner {...props} />
    </Suspense>
  );
}

function CompareControlsInner({ runs, aFile, bFile, labels }: CompareControlsProps) {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();

  function navigate(key: "run" | "vs", value: string) {
    const params = new URLSearchParams(search.toString());
    params.set(key, value);
    router.replace(`${pathname}?${params.toString()}`);
  }

  return (
    <div className="flex flex-wrap items-end gap-4">
      <Picker label={labels.a} value={aFile} runs={runs} onChange={(v) => navigate("run", v)} />
      <span className="pb-2 text-sm text-[var(--muted-foreground)]">vs</span>
      <Picker label={labels.b} value={bFile} runs={runs} onChange={(v) => navigate("vs", v)} />
    </div>
  );
}

function Picker({
  label,
  value,
  runs,
  onChange,
}: {
  label: string;
  value?: string;
  runs: RunMeta[];
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium text-[var(--muted-foreground)]">{label}</span>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="w-64" aria-label={label}>
          <SelectValue placeholder={label} />
        </SelectTrigger>
        <SelectContent>
          {runs.map((run) => (
            <SelectItem key={run.filename} value={run.filename}>
              {optionLabel(run)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
