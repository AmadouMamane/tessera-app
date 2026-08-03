"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect } from "react";

import { TesseraLogo } from "@/components/brand/tessera-logo";
import { Button } from "@/components/ui/button";

export default function LocaleError({ error, reset }: { error: Error; reset: () => void }) {
  const t = useTranslations("errorBoundary");

  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="bg-canvas-glow grid min-h-dvh place-items-center bg-[var(--tessera-bg)] px-5 py-10 text-[var(--tessera-text)]">
      <section className="w-full max-w-lg overflow-hidden rounded-xl border border-[var(--tessera-border)] bg-[var(--tessera-surface)] shadow-[0_24px_80px_rgba(0,0,0,0.24)]">
        <div className="h-px bg-gradient-to-r from-transparent via-amber-400/60 to-transparent" />
        <div className="flex flex-col items-center px-7 py-8 text-center sm:px-10 sm:py-10">
          <TesseraLogo className="mb-7 h-10" />
          <span className="mb-4 grid h-11 w-11 place-items-center rounded-xl border border-amber-500/25 bg-amber-500/10 text-[var(--tessera-fg-warning)]">
            <AlertTriangle className="h-5 w-5" aria-hidden="true" />
          </span>
          <h1 className="text-xl font-semibold tracking-tight">{t("title")}</h1>
          <p className="mt-2 max-w-sm text-sm leading-relaxed text-[var(--tessera-text-muted)]">
            {t("detail")}
          </p>
          <Button type="button" onClick={reset} className="mt-6">
            <RefreshCw />
            {t("retry")}
          </Button>
        </div>
      </section>
    </main>
  );
}
