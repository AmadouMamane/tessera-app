import { getTranslations, setRequestLocale } from "next-intl/server";

import {
  type DemoCred,
  type DemoLogin,
  LandingLauncher,
} from "@/components/landing/landing-launcher";
import { demoCredentials } from "@/lib/auth/accounts";
import { currentRole } from "@/lib/auth/session";
import { isDemoMode } from "@/lib/server/demo-mode";
import { loadLauncherSignal } from "@/lib/server/launcher-signal";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "landing" });
  return { title: t("demoTitle") };
}

// ADR 0013 — demoted from front door to a labelled DEMO LAUNCHER. The real entry
// is identity (the locale root role-routes server-side). This page is a reviewer
// convenience that shows both audiences without juggling accounts, so it is open
// to anyone and never redirects: the two cards just *link* to /produit and the
// cockpit. Following the operator card without operator-rbac hits the cockpit
// guard (no bypass) — routing here is not authorization.
export default async function DemoLauncherPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  // Public-safe aggregate signal (ADR 0009): real fleet rollup + last eval, or
  // null → the launcher shows an honest "indisponible" (never a fabricated number).
  const signal = await loadLauncherSignal();

  // Current role drives GRACEFUL per-row entry on the cards (deep-link when the
  // role may enter, else the auth page) — UX only; the layout guards stay the
  // authority (ADR 0013). Null for an anonymous visitor.
  const role = await currentRole();

  // 1-click seeded-account login on the guarded cards — DEMO MODE ONLY (off in
  // prod by default). When off, demoLogin is null and the cards keep the
  // "sign-in required" note; no seeded credentials are sent to the client.
  let demoLogin: DemoLogin | null = null;
  if (isDemoMode()) {
    const creds = demoCredentials();
    const pick = (role: string): DemoCred | undefined => {
      const c = creds.find((x) => x.role === role);
      return c ? { username: c.username, password: c.password } : undefined;
    };
    demoLogin = { operator: pick("admin") ?? pick("auditor"), collections: pick("collections") };
  }

  return <LandingLauncher signal={signal} demoLogin={demoLogin} role={role} />;
}
