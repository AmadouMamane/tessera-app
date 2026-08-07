"use client";

import { CheckCircle2, ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";

import { AlertRibbon, type RibbonSeverity } from "@/components/cockpit/alert-ribbon";

/**
 * The client half of the launch verdict — and the reason it has to exist.
 *
 * `AlertRibbon` is a Client Component and its `icon` prop is a `ComponentType`. A function
 * cannot cross the server/client boundary, so an async Server Component that renders the ribbon
 * directly crashes the whole view at request time ("Functions cannot be passed directly to
 * Client Components") — a failure no unit test, no typecheck and no lint sees, because the type
 * is perfectly valid on both sides. It is very likely one reason the evaluations view had never
 * adopted a single component of the cockpit mould.
 *
 * So the split follows the boundary rather than fighting it: the server component reads the
 * payload, resolves the sentences and hands down only SERIALISABLE values; this picks the glyph
 * from the severity, which is a rendering decision anyway.
 */
export function ReleaseVerdictBand({
  severity,
  title,
  meta,
  action,
}: {
  severity: RibbonSeverity;
  title: string;
  meta: ReactNode;
  action: ReactNode;
}) {
  return (
    <AlertRibbon
      variant="slim"
      severity={severity}
      icon={severity === "ok" ? CheckCircle2 : ShieldAlert}
      title={title}
      meta={meta}
      action={action}
    />
  );
}
