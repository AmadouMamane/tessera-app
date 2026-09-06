"use client";

import { Check, HandCoins, KeyRound, ScanSearch, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";

export interface DemoAccount {
  username: string;
  password: string;
  role: "admin" | "auditor" | "superadmin" | "collections";
}

interface DemoCredentialsProps {
  accounts: DemoAccount[];
  selectedUsername: string | null;
  onSelect: (account: DemoAccount) => void;
}

const ROLE_ICONS = {
  admin: ShieldCheck,
  auditor: ScanSearch,
  collections: HandCoins,
  superadmin: ShieldCheck,
} as const;

/**
 * Selectable demo accounts for the theatrical gate documented by ADR 0009.
 * Selection only fills the form: the user keeps control of the sign-in action.
 */
export function DemoCredentials({ accounts, selectedUsername, onSelect }: DemoCredentialsProps) {
  const t = useTranslations("auth");
  const tRoles = useTranslations("auth.roles");

  return (
    <div>
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-[12px] font-semibold text-[var(--text-primary)]">
            <KeyRound className="h-3.5 w-3.5 text-[var(--champagne-strong)]" />
            {t("demo.title")}
          </div>
          <p className="mt-1.5 text-xs leading-[1.45] text-[var(--text-secondary)]">
            {t("demo.hint")}
          </p>
          <p className="mt-1 text-[11px] leading-[1.45] text-[var(--tessera-text-muted)]">
            {t("demo.ephemeral")}
          </p>
        </div>
      </div>
      <fieldset className="grid grid-cols-3 gap-2">
        <legend className="sr-only">{t("demo.title")}</legend>
        {accounts.map((account) => {
          const selected = account.username === selectedUsername;
          const RoleIcon = ROLE_ICONS[account.role];

          return (
            <button
              key={account.username}
              type="button"
              aria-label={`${tRoles(account.role)} ${account.username}·${account.password}`}
              aria-pressed={selected}
              onClick={() => onSelect(account)}
              className={`group flex min-h-[112px] w-full flex-col rounded-2xl border p-3 text-left transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] ${
                selected
                  ? "border-emerald-300/35 bg-emerald-300/[0.065] shadow-[inset_0_0_0_1px_rgba(110,231,183,0.05)]"
                  : "border-white/[0.055] bg-white/[0.018] hover:border-white/[0.1] hover:bg-white/[0.035]"
              }`}
            >
              <span className="flex w-full items-start justify-between">
                <span
                  className={`grid h-8 w-8 shrink-0 place-items-center rounded-xl border ${
                    selected
                      ? "border-emerald-300/30 bg-emerald-300/[0.1] text-[var(--tessera-fg-success)]"
                      : "border-white/[0.06] bg-[var(--launcher-chip-bg)] text-[var(--tessera-text-muted)]"
                  }`}
                >
                  <RoleIcon className="h-3.5 w-3.5" />
                </span>
                <span
                  className={`grid h-5 w-5 shrink-0 place-items-center rounded-full border transition-colors ${
                    selected
                      ? "border-emerald-300/35 bg-emerald-300/[0.12] text-[var(--tessera-fg-success)]"
                      : "border-white/[0.06] text-transparent group-hover:border-white/[0.12]"
                  }`}
                >
                  <Check className="h-3 w-3" />
                </span>
              </span>
              <span className="mt-2.5 min-w-0">
                <span className="block text-xs font-medium leading-[1.25] text-[var(--text-primary)]">
                  {tRoles(account.role)}
                </span>
                {/* The role label already names the profile — the raw username/password
                    were three near-duplicate identity strings per card, and the longest
                    (`tessera-collections`) truncated. The click fills the form (which shows
                    what it filled); the full pair stays in aria-label for screen readers. */}
                <span className="mt-1 block text-[11px] leading-4 text-[var(--tessera-text-muted)]">
                  {t("demo.enter")}
                </span>
              </span>
            </button>
          );
        })}
      </fieldset>
    </div>
  );
}
