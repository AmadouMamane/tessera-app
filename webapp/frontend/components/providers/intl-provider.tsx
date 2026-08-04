"use client";

import { NextIntlClientProvider } from "next-intl";
import type { ComponentProps } from "react";

import { missingMessageFallback, reportMissingMessage } from "@/i18n/fallback";

type IntlProviderProps = ComponentProps<typeof NextIntlClientProvider>;

/**
 * Keep unresolved dynamic catalogue entries out of the rendered product UI.
 *
 * The two functions are shared with `i18n/request.ts` rather than written twice: the server
 * renderer had NEITHER until 2026-08-04, so the same missing key rendered an em dash in a
 * client component and its own dotted path in a server one. Read `i18n/fallback.ts` before
 * changing what a miss looks like — the choice is argued there, and it is a trade-off.
 */
export function IntlProvider(props: IntlProviderProps) {
  return (
    <NextIntlClientProvider
      {...props}
      onError={reportMissingMessage}
      getMessageFallback={missingMessageFallback}
    />
  );
}
