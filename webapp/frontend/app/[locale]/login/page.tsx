import { ArrowLeft, ShieldCheck } from "lucide-react";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { AuthControl } from "@/components/auth/auth-control";
import { DemoCredentials } from "@/components/auth/demo-credentials";
import { LoginForm } from "@/components/auth/login-form";
import { Card, CardContent } from "@/components/ui/card";
import { Link } from "@/i18n/navigation";

interface LoginPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: LoginPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "auth" });
  return { title: t("login.title") };
}

export default async function LoginPage({ params }: LoginPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "auth" });
  const tc = await getTranslations({ locale, namespace: "comprendre" });

  return (
    <div className="bg-canvas-glow flex h-screen items-center justify-center overflow-y-auto bg-[var(--background)] px-6 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-navy-900 text-gold-400 ring-1 ring-gold-500/20 dark:bg-gold-500 dark:text-navy-950">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <h1 className="font-serif text-2xl font-semibold">{t("login.title")}</h1>
          <p className="text-sm text-[var(--muted-foreground)]">{t("login.subtitle")}</p>
        </div>

        {/* One welcome line above the form, and only one: a visitor who lands here has already
            chosen a world. Saying that this is a demonstration, once, before they type a
            password they do not have, is the whole job. */}
        <p className="mb-4 text-center text-[0.8rem] text-[var(--muted-foreground)]">
          {tc("loginWelcome")}
        </p>

        <Card>
          <CardContent className="flex flex-col gap-5 p-6">
            <LoginForm />
            <DemoCredentials locale={locale} />
          </CardContent>
        </Card>

        <div className="mt-5 flex items-center justify-between">
          <Link
            href="/produit"
            className="inline-flex items-center gap-1.5 text-sm text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
          >
            <ArrowLeft className="h-4 w-4" />
            {t("login.back")}
          </Link>
          {/* Lets an already-signed-in operator see their state / sign out here. */}
          <AuthControl />
        </div>
      </div>
    </div>
  );
}
