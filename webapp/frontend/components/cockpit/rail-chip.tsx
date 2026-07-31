"use client";

import { Check, ChevronDown, Info } from "lucide-react";
import type { ComponentType } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/cn";

/**
 * The command-bar chip grammar shared by EVERY temporal rail (SR-01 registre §5,
 * extended to the AGIR/AT-01 rails). The deep lacquered rail would swallow plain
 * controls, so chips are raised just enough to read as active controls — a cool,
 * faintly cyan-tinted glass (the temporal-structure hue), NOT the cards' neutral
 * surface, with a clear hover and no heavy outline. The PRIMARY reading control
 * and the chosen instant wear a discreet champagne instead — never a status
 * colour. One source so the grammar never drifts between surfaces.
 */
export const CHIP_BASE =
  "flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-lg border px-3 text-xs shadow-[inset_0_1px_0_rgba(160,220,250,0.09)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(96,194,242,0.35)]";
export const CHIP_NEUTRAL =
  "border-[rgba(96,194,242,0.26)] bg-[rgba(96,194,242,0.05)] text-[var(--tessera-text-muted)] hover:bg-[rgba(96,194,242,0.12)] hover:border-[rgba(96,194,242,0.4)]";
export const CHIP_ACTIVE =
  "border-gold-500/45 bg-gold-500/[0.12] text-gold-700 hover:bg-gold-500/[0.18] focus-visible:ring-gold-500/50 dark:text-gold-200";

/**
 * A compact labeled chooser styled to match the command bar. Rendered as a
 * DropdownMenu (not a native `<select>`) so its OPEN panel wears the rail's
 * harmonized `sr01-menu` surface (a native select's dropdown is OS-drawn and can't
 * be themed). The value logic is unchanged — selecting an item calls `onChange`.
 */
export function SelectChip({
  icon: Icon,
  label,
  value,
  onChange,
  options,
  accent,
  noteTitle,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string; disabled?: boolean }[];
  accent?: boolean;
  /**
   * Discreet "not available" reason for the CURRENT value (e.g. "Période précédente"
   * is shown but not computable here). Rendered as a small info glyph with the reason
   * in its tooltip — so the chip stays narrow and the long reason never widens it.
   */
  noteTitle?: string;
}) {
  const selected = options.find((o) => o.value === value);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={cn(CHIP_BASE, "cursor-pointer", accent ? CHIP_ACTIVE : CHIP_NEUTRAL)}
        >
          <Icon className="h-3.5 w-3.5 shrink-0 text-gold-600 dark:text-gold-400" />
          {label}
          <span className="font-semibold text-[var(--tessera-text)]">
            {selected?.label ?? value}
          </span>
          {noteTitle ? (
            <span title={noteTitle} aria-label={noteTitle} className="flex shrink-0 cursor-help">
              <Info className="h-3.5 w-3.5 text-[var(--tessera-fg-warning)]/70" aria-hidden />
            </span>
          ) : (
            <ChevronDown className="h-3.5 w-3.5 shrink-0 text-gold-600/70 dark:text-gold-400/70" />
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="sr01-menu min-w-[12rem]">
        {options.map((o) => (
          <DropdownMenuItem
            key={o.value}
            disabled={o.disabled}
            onSelect={() => onChange(o.value)}
            className="flex items-center justify-between gap-3 text-[var(--tessera-text)]"
          >
            {o.label}
            {o.value === value ? (
              <Check className="h-3.5 w-3.5 shrink-0 text-gold-600 dark:text-gold-400" />
            ) : null}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
