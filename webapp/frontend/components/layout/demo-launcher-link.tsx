"use client";

import { useTranslations } from "next-intl";

import { DemoBadge } from "@/components/layout/demo-badge";

/**
 * Discreet, labelled shortcut to the demo launcher (/select-space).
 *
 * ADR 0013 keeps identity as the real front door (the root role-routes); the demo
 * launcher is only a reviewer convenience and was otherwise unreachable. This is a
 * small, clearly-labelled affordance — never the door — surfaced on the customer
 * product and in the cockpit so an evaluator can jump between spaces.
 *
 * `floating` pins it to a screen corner (for the full-bleed product host);
 * otherwise it renders inline (e.g. in the cockpit topbar).
 */
export function DemoLauncherLink({
  className,
  floating = false,
}: {
  className?: string;
  floating?: boolean;
}) {
  const t = useTranslations("app");
  return <DemoBadge className={className} floating={floating} label={t("demoExplore")} />;
}
