import { NextIntlClientProvider } from "next-intl";
import { getMessages, setRequestLocale } from "next-intl/server";
/**
 * Locale-aware layout — owns the <html lang>, loads the message catalogue
 * and renders the persistent app shell.
 */
import { IBM_Plex_Serif, Inter, JetBrains_Mono } from "next/font/google";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";

import { Providers } from "@/components/providers";
import { Telemetry } from "@/components/telemetry";
import { type Locale, routing } from "@/i18n/routing";
import { cn } from "@/lib/cn";

const inter = Inter({
  subsets: ["latin", "latin-ext"],
  variable: "--font-sans",
  display: "swap",
});

const serif = IBM_Plex_Serif({
  subsets: ["latin", "latin-ext"],
  weight: ["400", "500", "600"],
  variable: "--font-serif",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

interface LocaleLayoutProps {
  children: ReactNode;
  params: Promise<{ locale: string }>;
}

export default async function LocaleLayout({ children, params }: LocaleLayoutProps) {
  const { locale } = await params;
  if (!(routing.locales as readonly string[]).includes(locale)) notFound();
  setRequestLocale(locale);
  const messages = await getMessages();

  return (
    <html
      lang={locale}
      suppressHydrationWarning
      className={cn(inter.variable, serif.variable, mono.variable)}
    >
      <body className="h-screen overflow-hidden font-sans antialiased">
        <Telemetry />
        <NextIntlClientProvider locale={locale as Locale} messages={messages}>
          <Providers>{children}</Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
