import { getTranslations, setRequestLocale } from "next-intl/server";

import { LauncherFooter } from "@/components/landing/launcher-footer";
import { LauncherWaves } from "@/components/landing/launcher-waves";
import { AppHeader } from "@/components/layout/app-header";
import { DemoBadge } from "@/components/layout/demo-badge";
import {
  SpacesDirectory,
  type SurfaceGroup,
  type SurfaceView,
} from "@/components/spaces/spaces-directory";
import { currentRole, hasCollectionsAccess, hasProductAccess } from "@/lib/auth/session";

interface PageProps {
  params: Promise<{ locale: string }>;
}

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "spaces" });
  return { title: t("title") };
}

// Static directory of business surfaces (ADR 0008/0010/0013). A business surface
// advertises its ACCESS (open vs sign-in required) and audience — NOT the backing
// agent's eval-gate release verdict. That verdict is control-plane and lives in
// the cockpit (Flotte / Vue d'ensemble); showing "Bloqué" here would be both
// cross-plane and misleading (the surface IS usable in the demo). ADR 0013
// amendment: public-safe surface health = access/availability, not the verdict.
const SURFACES: Array<{
  key: "client" | "recouvrement";
  href: "/produit" | "/recouvrement";
  group: "external" | "internal";
  authRequired: boolean;
}> = [
  {
    key: "client",
    href: "/produit",
    group: "external",
    authRequired: false,
  },
  {
    key: "recouvrement",
    href: "/recouvrement",
    group: "internal",
    authRequired: true,
  },
];

// ADR 0013 — a reviewer/operator directory, NOT the front door. It never
// redirects: a real user is role-routed at the locale root (spaceRedirectForRole
// is unchanged); this is the +1-click exploration surface. Open to anyone — the
// guarded surfaces' layout RBAC stays the authority.
export default async function SpacesDirectoryPage({ params }: PageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "spaces" });
  const tl = await getTranslations({ locale, namespace: "landing" });

  const role = await currentRole();

  // Whether the CURRENT authenticated role may actually enter a surface. An
  // anonymous session is always "accessible" — its Lock/auth note (and demo
  // login) already tells the honest story. But an authenticated role the surface
  // rejects (e.g. `collections` and the customer product) must NOT be shown an
  // open link that the layout would bounce to its own landing (ADR 0013): the
  // card is rendered inert with a "réservé à votre rôle" note instead.
  const accessibleForRole = (s: (typeof SURFACES)[number]): boolean => {
    if (role === null) return true;
    return s.key === "client" ? hasProductAccess(role) : hasCollectionsAccess(role);
  };

  const toView = (s: (typeof SURFACES)[number]): SurfaceView => ({
    key: s.key,
    href: s.href,
    name: tl(`${s.key}.title`),
    desc: tl(`${s.key}.desc`),
    authRequired: s.authRequired,
    authNote: s.authRequired ? tl(`${s.key}.authNote`) : "",
    accessible: accessibleForRole(s),
  });

  const groups: SurfaceGroup[] = (["external", "internal"] as const).map((key) => ({
    key,
    label: key === "external" ? t("groupExternal") : t("groupInternal"),
    desc: key === "external" ? t("groupExternalDesc") : t("groupInternalDesc"),
    surfaces: SURFACES.filter((s) => s.group === key).map(toView),
  }));

  return (
    <div className="launcher-surface relative min-h-screen overflow-hidden bg-[var(--bg-app)] text-[var(--text-primary)]">
      <div
        className="pointer-events-none absolute inset-0 z-0"
        style={{ background: "var(--launcher-backdrop)" }}
      />
      <div className="relative z-10 flex min-h-screen flex-col">
        {/* Unified header (docs/design/header-normative.md) — business variant:
            brand at left (links back to the launcher), the global cluster at
            right. Auth is OPTIONAL here (anonymous → customer), so "Se connecter"
            legitimately appears for a visitor (the only plan besides /produit). */}
        <AppHeader plan="business" auth="optional" brandHref="/select-space" />

        {/* `relative` + the band as first child: same continuous wave band as the
            launcher, and like there it ends at the footer's rule rather than under it. */}
        <main className="relative flex flex-1 flex-col items-center px-6 pb-16 pt-10 sm:pt-12">
          <LauncherWaves />
          <section className="mb-10 flex w-full max-w-[1040px] flex-col items-start gap-[10px]">
            <DemoBadge />
            <h1 className="font-sans text-[30px] font-semibold leading-[1.1] tracking-[-0.02em] text-[var(--text-primary)]">
              {t("title")}
            </h1>
            <p className="max-w-[680px] text-[14px] leading-[1.5] text-[var(--text-secondary)]">
              {t("subtitle")}
            </p>
            {/* No cross-plane link here (ADR 0013): a business page shows ONLY its
                plane. The /espaces↔Flotte symmetry is a design rationale, not a
                user link — the two planes meet only at the launcher. */}
          </section>

          <SpacesDirectory groups={groups} />

          <p className="mt-10 w-full max-w-[1040px] text-[11px] leading-[1.5] text-[var(--text-secondary)]">
            {t("accessLegend")}
          </p>
        </main>
        <LauncherFooter width="narrow" />
      </div>
    </div>
  );
}
