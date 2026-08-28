import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { ShieldAlert } from "lucide-react";

import { Button } from "../ui/button";
import { AlertRibbon, RibbonChip } from "./alert-ribbon";

const meta = {
  title: "Cockpit/Alert ribbon",
  component: AlertRibbon,
  parameters: { viewport: { defaultViewport: "responsive" } },
} satisfies Meta<typeof AlertRibbon>;

export default meta;
type Story = StoryObj<typeof meta>;

export const QualityBreach: Story = {
  args: {
    severity: "critical",
    icon: ShieldAlert,
    eyebrow: "Quality objective",
    title: "Response fidelity below the publication threshold — intervention required",
    gauge: {
      value: 0.455,
      threshold: 0.8,
      thresholdLabel: "80 %",
      caption: <RibbonChip tone="critical">Burn rate 8,9×</RibbonChip>,
    },
    action: (
      <Button size="sm" variant="outline">
        Open analysis
      </Button>
    ),
    pulse: true,
    pulseStopLabel: "Acknowledge animation",
  },
};

export const Healthy: Story = {
  args: {
    variant: "slim",
    severity: "ok",
    icon: ShieldAlert,
    title: "All controls in this policy meet their objective",
    meta: "Local measurement · 2 min ago",
  },
};
