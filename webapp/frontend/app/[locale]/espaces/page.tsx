import { getTranslations, setRequestLocale } from "next-intl/server";

import { AuthControl } from "@/components/auth/auth-control";
import { TesseraLogo } from "@/components/brand/tessera-logo";
import { SPACE_SELECTOR_TOKENS } from "@/components/landing/landing-launcher";
import { LanguageSwitcher } from "@/components/layout/language-switcher";
import {
  SpacesDirectory,
  type SurfaceDemo,
  type SurfaceGroup,
  type SurfaceView,
} from "@/components/spaces/spaces-directory";
import { Link } from "@/i18n/navigation";
import { demoCredentials } from "@/lib/auth/accounts";
import { currentRole, hasCollectionsAccess, hasProductAccess } from "@/lib/auth/session";
import { isDemoMode } from "@/lib/server/demo-mode";

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
  demoRole?: string;
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
    demoRole: "collections",
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

  const demoCred = (role: string): SurfaceDemo | null => {
    if (!isDemoMode()) return null;
    const c = demoCredentials().find((x) => x.role === role);
    return c ? { username: c.username, password: c.password, label: t("demoLogin") } : null;
  };

  const toView = (s: (typeof SURFACES)[number]): SurfaceView => ({
    key: s.key,
    href: s.href,
    name: tl(`${s.key}.title`),
    desc: tl(`${s.key}.desc`),
    authRequired: s.authRequired,
    authNote: s.authRequired ? tl(`${s.key}.authNote`) : "",
    demo: s.demoRole ? demoCred(s.demoRole) : null,
    accessible: accessibleForRole(s),
  });

  const groups: SurfaceGroup[] = (["external", "internal"] as const).map((key) => ({
    key,
    label: key === "external" ? t("groupExternal") : t("groupInternal"),
    desc: key === "external" ? t("groupExternalDesc") : t("groupInternalDesc"),
    surfaces: SURFACES.filter((s) => s.group === key).map(toView),
  }));

  return (
    <div
      className="relative min-h-screen overflow-hidden bg-[var(--bg-app)] text-[var(--text-primary)]"
      style={SPACE_SELECTOR_TOKENS}
    >
      <div
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          background:
            "radial-gradient(circle at 50% 12%, rgba(13, 38, 71, 0.55), transparent 46%), linear-gradient(180deg, #001025 0%, #00101f 60%, #000b18 100%)",
        }}
      />
      {/* Same continuous wave band as the launcher — visual continuity. */}
      <div
        className="pointer-events-none absolute inset-x-0 bottom-0 z-0 h-[300px]"
        style={{
          backgroundImage: "url('/assets/tessera-waves-band.png')",
          backgroundRepeat: "no-repeat",
          backgroundPosition: "center bottom",
          backgroundSize: "100% 100%",
          maskImage: "linear-gradient(to top, #000 55%, transparent 100%)",
          WebkitMaskImage: "linear-gradient(to top, #000 55%, transparent 100%)",
        }}
      />
      <div className="relative z-10 flex min-h-screen flex-col">
        <header className="flex h-[88px] shrink-0 items-center justify-between border-b border-[var(--border-subtle)] px-6">
          <Link href="/select-space" className="flex items-center gap-2">
            <TesseraLogo className="h-[40px]" />
          </Link>
          <div className="flex items-center gap-3 text-[var(--text-secondary)]">
            <LanguageSwitcher />
            <AuthControl />
          </div>
        </header>

        <main className="flex flex-1 flex-col items-center px-6 pb-24 pt-12">
          <section className="mb-10 flex w-full max-w-[1040px] flex-col items-start gap-[10px]">
            <span className="inline-flex items-center gap-[7px] rounded-full border border-[var(--border-gold)] bg-[color-mix(in_srgb,var(--gold)_12%,transparent)] px-[12px] py-[5px] text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--gold-strong)]">
              <span className="h-[6px] w-[6px] rounded-full bg-[var(--gold-strong)]" />
              {t("demoBadge")}
            </span>
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
      </div>
    </div>
  );
}
