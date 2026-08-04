import "@tanstack/react-query";

declare module "@tanstack/react-query" {
  interface Register {
    queryMeta: {
      health?: {
        /** Localised operator-facing source name. */
        label: string;
        /** Cockpit destination where the failed source is visible. */
        href?: string;
      };
    };
  }
}
