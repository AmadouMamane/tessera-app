import type { Preview } from "@storybook/nextjs-vite";

import { TooltipProvider } from "../components/ui/tooltip";
import "../app/globals.css";

const preview: Preview = {
  decorators: [
    (Story) => (
      <TooltipProvider>
        <main className="min-h-screen bg-[var(--tessera-bg)] p-6 text-[var(--tessera-text)]">
          <Story />
        </main>
      </TooltipProvider>
    ),
  ],
  parameters: {
    layout: "fullscreen",
    controls: { expanded: true },
    a11y: { test: "error" },
  },
};

export default preview;
