"use client";

import { NextIntlClientProvider } from "next-intl";
import type { ComponentProps } from "react";

type IntlProviderProps = ComponentProps<typeof NextIntlClientProvider>;

/** Keep unresolved dynamic catalogue entries out of the rendered product UI. */
export function IntlProvider(props: IntlProviderProps) {
  return (
    <NextIntlClientProvider
      {...props}
      onError={(error) => console.error(error)}
      getMessageFallback={() => "—"}
    />
  );
}
