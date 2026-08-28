import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Download, ShieldCheck } from "lucide-react";

import { Button } from "./button";

const meta = {
  title: "Primitives/Button",
  component: Button,
  args: {
    children: "Confirm decision",
  },
  argTypes: {
    variant: {
      control: "select",
      options: ["primary", "secondary", "outline", "ghost", "accent", "danger", "link"],
    },
    size: { control: "select", options: ["sm", "md", "lg", "icon"] },
  },
} satisfies Meta<typeof Button>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Primary: Story = {};

export const Destructive: Story = {
  args: { variant: "danger", children: "Block publication" },
};

export const WithIcon: Story = {
  args: {
    variant: "outline",
    children: (
      <>
        <Download aria-hidden />
        Export evidence
      </>
    ),
  },
};

export const IconOnly: Story = {
  args: {
    size: "icon",
    variant: "ghost",
    "aria-label": "View controls",
    children: <ShieldCheck aria-hidden />,
  },
};
