"use client";

import { Lock } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import type { RunOption } from "@/components/eval/run-picker";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { usePathname, useRouter } from "@/i18n/navigation";
import { shortRunDate } from "@/lib/format";
import { findModel } from "@/lib/models";

/**
 * The référentiel FIRST, the models second (§3 C).
 *
 * The picker this replaces let a reader choose any two runs by id and appended `· 90%` to every
 * option. Two failures in one control: a raw pass rate — the one number this screen forbids — sat
 * inside the very thing used to choose what to compare, and nothing stopped the two runs from
 * having been scored on DIFFERENT case sets, which makes any gap between them a gap of *test*
 * before it is a gap of *model*.
 *
 * So the case set is shown as what it is: a LOCK on the comparison, not a filter. Only the runs
 * scored against it can be picked, and the options carry the date and the model — nothing else.
 */
type CompareControlsProps = {
  runs: RunOption[];
  a: string;
  b: string;
  version: string | null;
  labels: { referential: string; modelA: string; modelB: string; locked: string };
};

export function CompareControls(props: CompareControlsProps) {
  return (
    <Suspense
      fallback={
        <div className="flex flex-wrap items-end gap-4">
          <Skeleton className="h-9 w-56 rounded-md" />
          <Skeleton className="h-9 w-56 rounded-md" />
        </div>
      }
    >
      <CompareControlsInner {...props} />
    </Suspense>
  );
}

function CompareControlsInner({ runs, a, b, version, labels }: CompareControlsProps) {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();

  function navigate(key: "a" | "b", value: string) {
    const params = new URLSearchParams(search.toString());
    params.set("tab", "compare");
    params.set(key, value);
    router.replace(`${pathname}?${params.toString()}`);
  }

  return (
    <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
      <div className="flex flex-col gap-1">
        <span className="font-medium text-[var(--muted-foreground)] text-xs">
          {labels.referential}
        </span>
        <Badge tone="navy" className="gap-1.5 px-2.5 py-1.5 font-mono">
          <Lock className="h-3 w-3" />
          {version ?? "—"}
        </Badge>
      </div>
      <Picker label={labels.modelA} value={a} runs={runs} onChange={(v) => navigate("a", v)} />
      <Picker label={labels.modelB} value={b} runs={runs} onChange={(v) => navigate("b", v)} />
      <p className="max-w-md text-[11px] text-[var(--muted-foreground)] leading-relaxed">
        {labels.locked}
      </p>
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
  value: string;
  runs: RunOption[];
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="font-medium text-[var(--muted-foreground)] text-xs">{label}</span>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="w-60" aria-label={label}>
          <SelectValue placeholder={label} />
        </SelectTrigger>
        <SelectContent>
          {runs.map((run) => (
            <SelectItem key={run.id} value={run.id}>
              {`${shortRunDate(run.runAt ?? "")} · ${run.model ? findModel(run.model).label : "—"}`}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
