"use client";

import { QueryClient, QueryClientProvider, isServer } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { SessionProvider } from "next-auth/react";
import { ThemeProvider } from "next-themes";
import type { ReactNode } from "react";
import { useState } from "react";
import { Toaster } from "sonner";

import { TooltipProvider } from "@/components/ui/tooltip";

/**
 * Bootstrap a single QueryClient per browser tab.
 *
 * On the server we always build a fresh client so requests do not leak
 * across users. On the client we cache the instance on `window` so
 * Suspense boundaries do not recreate it on every navigation.
 */
let browserClient: QueryClient | undefined;

function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Revisiting an already-seen tab reads from cache instantly, then
        // revalidates in the background (stale-while-revalidate). gcTime keeps
        // the cache around for ~5 min so back/forward stays instant too.
        staleTime: 60_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        retry: 1,
      },
    },
  });
}

function getQueryClient(): QueryClient {
  if (isServer) return makeQueryClient();
  if (!browserClient) browserClient = makeQueryClient();
  return browserClient;
}

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(getQueryClient);
  return (
    <SessionProvider>
      <ThemeProvider
        attribute="class"
        defaultTheme="dark"
        enableSystem
        themes={["light", "dark", "deep-night"]}
        disableTransitionOnChange
      >
        <QueryClientProvider client={queryClient}>
          <TooltipProvider delayDuration={200} skipDelayDuration={120}>
            {children}
          </TooltipProvider>
          <Toaster position="bottom-right" theme="system" richColors closeButton />
          {/* Opt-in only (set NEXT_PUBLIC_RQ_DEVTOOLS=true). Hidden by default even
              in dev, so the floating toggle never shows on the public demo, which
              runs `next dev` behind a tunnel (NODE_ENV stays "development"). */}
          {process.env.NEXT_PUBLIC_RQ_DEVTOOLS === "true" ? (
            <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-left" />
          ) : null}
        </QueryClientProvider>
      </ThemeProvider>
    </SessionProvider>
  );
}
