import { ArrowLeft, Check, Fingerprint, KeyRound, LockKeyhole, ShieldCheck } from "lucide-react";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { LoginForm } from "@/components/auth/login-form";
import { TesseraLogo, TesseraMark } from "@/components/brand/tessera-logo";
import { DemoBadge } from "@/components/layout/demo-badge";
import { Link } from "@/i18n/navigation";
import { demoCredentials } from "@/lib/auth/accounts";
import { safeLoginReturnTo } from "@/lib/auth/return-to";

interface LoginPageProps {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export async function generateMetadata({ params }: LoginPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "auth" });
  return { title: t("login.title") };
}

export default async function LoginPage({ params, searchParams }: LoginPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "auth" });
  const returnTo = safeLoginReturnTo((await searchParams).next);
  const demoAccounts = demoCredentials();

  return (
    <div className="launcher-surface relative min-h-screen overflow-y-auto bg-[var(--bg-app)] text-[var(--text-primary)]">
      <div
        className="pointer-events-none absolute inset-0"
        style={{ background: "var(--launcher-backdrop-auth)" }}
      />
      <div
        className="pointer-events-none absolute inset-x-0 bottom-0 h-[300px]"
        style={{
          backgroundImage: "url('/assets/tessera-waves-band.png')",
          backgroundRepeat: "no-repeat",
          backgroundPosition: "center bottom",
          backgroundSize: "100% 100%",
          /* 0.7 of whatever the theme allows: full-strength artwork on the dark
             themes, softened under "Clair". */
          opacity: "calc(var(--launcher-waves-opacity) * 0.7)",
          maskImage: "linear-gradient(to top, #000 48%, transparent 100%)",
          WebkitMaskImage: "linear-gradient(to top, #000 48%, transparent 100%)",
        }}
      />

      <header className="relative z-10 flex min-h-[82px] items-center justify-between border-b border-[var(--border-subtle)] px-6 lg:px-10">
        <Link href="/select-space" className="rounded-md outline-none focus-visible:ring-2">
          <TesseraLogo className="h-[42px]" />
        </Link>
        <Link
          href="/select-space"
          className="inline-flex items-center gap-2 rounded-xl border border-transparent px-3 py-2 text-[13px] text-[var(--text-secondary)] transition-colors hover:border-white/[0.06] hover:bg-white/[0.04] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
        >
          <ArrowLeft className="h-4 w-4" />
          {t("login.back")}
        </Link>
      </header>

      <main className="relative z-10 mx-auto grid min-h-[calc(100vh-82px)] w-full max-w-[1540px] grid-cols-1 items-center px-6 py-10 lg:grid-cols-[minmax(0,1fr)_minmax(440px,520px)] lg:gap-20 lg:px-10 xl:gap-28">
        <section className="flex items-center py-2">
          <div className="flex w-full max-w-[720px] flex-col items-start">
            <DemoBadge className="mb-5" />
            <h1 className="max-w-[680px] font-sans text-[30px] font-semibold leading-[1.1] tracking-[-0.02em] text-[var(--text-primary)]">
              {t("login.title")}
            </h1>
            <p className="mt-5 max-w-[630px] text-[16px] leading-[1.65] text-[var(--text-secondary)]">
              {t("login.subtitle")}
            </p>
            <div className="mt-7 flex flex-wrap gap-2.5">
              {[t("login.accessIdentity"), t("login.accessRights"), t("login.accessTrace")].map(
                (item) => (
                  <span
                    key={item}
                    className="inline-flex items-center gap-2 rounded-full border border-white/[0.07] bg-white/[0.025] px-3 py-2 text-[12px] text-[var(--tessera-text-muted)]"
                  >
                    <Check className="h-3.5 w-3.5 text-[var(--tessera-fg-success)]" />
                    {item}
                  </span>
                ),
              )}
            </div>

            <div
              className="relative mt-9 hidden h-[270px] w-full max-w-[680px] lg:block"
              aria-hidden="true"
            >
              <div className="-translate-x-1/2 -translate-y-1/2 absolute top-1/2 left-1/2 h-[250px] w-[560px] rounded-full bg-[radial-gradient(circle,rgba(45,212,191,0.11),transparent_64%)] blur-2xl" />
              <div className="absolute inset-0 opacity-[0.16] [background-image:radial-gradient(rgba(148,163,184,0.52)_0.8px,transparent_0.8px)] [background-size:18px_18px] [mask-image:radial-gradient(ellipse_at_center,#000_18%,transparent_70%)]" />
              <div className="-translate-x-1/2 -translate-y-1/2 absolute top-1/2 left-1/2 h-[198px] w-[500px] rounded-[50%] border border-cyan-300/15" />
              <div className="-translate-x-1/2 -translate-y-1/2 absolute top-1/2 left-1/2 h-[138px] w-[340px] rounded-[50%] border border-emerald-300/20" />
              <div className="-translate-x-1/2 -translate-y-1/2 absolute top-1/2 left-1/2 grid h-[88px] w-[88px] place-items-center rounded-3xl border border-emerald-300/30 bg-[var(--launcher-tile-mark)] shadow-[0_0_44px_rgba(45,212,191,0.16)]">
                <TesseraMark className="h-[48px] w-[48px]" />
              </div>
              <div className="absolute top-[30px] left-[112px] grid h-11 w-11 place-items-center rounded-xl border border-cyan-300/25 bg-[var(--launcher-tile-teal)] text-[var(--tessera-fg-teal)] shadow-[0_10px_30px_rgba(0,0,0,0.25)]">
                <Fingerprint className="h-5 w-5" />
              </div>
              <div className="absolute right-[94px] bottom-[36px] grid h-11 w-11 place-items-center rounded-xl border border-emerald-300/25 bg-[var(--launcher-tile-green)] text-[var(--tessera-fg-success)] shadow-[0_10px_30px_rgba(0,0,0,0.25)]">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <div className="absolute right-[86px] top-[36px] grid h-11 w-11 place-items-center rounded-xl border border-violet-300/20 bg-[var(--launcher-tile-violet)] text-[var(--tessera-fg-accent)] shadow-[0_10px_30px_rgba(0,0,0,0.25)]">
                <LockKeyhole className="h-5 w-5" />
              </div>
              <div className="absolute bottom-[34px] left-[96px] grid h-11 w-11 place-items-center rounded-xl border border-amber-200/20 bg-[var(--launcher-tile-amber)] text-[var(--tessera-fg-warning)] shadow-[0_10px_30px_rgba(0,0,0,0.25)]">
                <KeyRound className="h-5 w-5" />
              </div>
            </div>
          </div>
        </section>

        <section className="relative flex min-h-0 w-full items-center border-t border-[var(--border-subtle)] py-10 lg:min-h-[690px] lg:border-t-0 lg:pl-16">
          <div
            className="pointer-events-none absolute inset-y-8 left-0 hidden w-px lg:block"
            aria-hidden="true"
            style={{
              background:
                "linear-gradient(180deg, transparent 0%, rgba(148, 163, 184, 0.12) 18%, rgba(110, 231, 183, 0.18) 50%, rgba(148, 163, 184, 0.12) 82%, transparent 100%)",
            }}
          />
          <div className="mx-auto w-full max-w-[460px]">
            <div className="mb-6 flex items-center gap-4 border-b border-[var(--border-subtle)] pb-6">
              <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl border border-emerald-300/25 bg-emerald-300/[0.08] text-[var(--tessera-fg-success)] shadow-[0_0_28px_rgba(45,212,191,0.08)]">
                <ShieldCheck className="h-6 w-6" />
              </div>
              <div className="min-w-0">
                <p className="text-[16px] font-semibold text-[var(--text-primary)]">
                  {t("login.panelTitle")}
                </p>
                <p className="mt-1 text-[12px] leading-5 text-[var(--text-secondary)]">
                  {t("login.panelHint")}
                </p>
              </div>
            </div>

            <LoginForm returnTo={returnTo} demoAccounts={demoAccounts} />
          </div>
        </section>
      </main>
    </div>
  );
}
