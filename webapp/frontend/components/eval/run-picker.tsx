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
import { shortRunDate } from "@/lib/format";
import { findModel } from "@/lib/models";

export interface RunOption {
  id: string;
  model: string | null;
  runAt: string | null;
}

/**
 * Which run's per-case detail is open. Selection drives the URL (`?run=`), so the server
 * re-renders the detail — the same URL-as-state contract the rest of this screen uses.
 *
 * The option label carries the date and the model and NOTHING else. The picker it replaces
 * appended `· 90%` to every option, which put a raw pass rate — the one number this screen
 * forbids — into the very control used to choose what to look at.
 */
type RunPickerProps = {
  runs: RunOption[];
  selected: string;
  label: string;
};

export function RunPicker(props: RunPickerProps) {
  return (
    <Suspense fallback={<Skeleton className="h-9 w-72 rounded-md" />}>
      <RunPickerInner {...props} />
    </Suspense>
  );
}

function RunPickerInner({ runs, selected, label }: RunPickerProps) {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();

  function navigate(value: string) {
    const params = new URLSearchParams(search.toString());
    params.set("run", value);
    router.replace(`${pathname}?${params.toString()}`);
  }

  return (
    <div className="flex flex-col gap-1">
      <span className="font-medium text-[var(--muted-foreground)] text-xs">{label}</span>
      <Select value={selected} onValueChange={navigate}>
        <SelectTrigger className="w-72" aria-label={label}>
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
