"use client";

import { Eye, EyeOff, KeyRound, LogIn, UserRound } from "lucide-react";
import { signIn } from "next-auth/react";
import { useTranslations } from "next-intl";
import { type FormEvent, useState } from "react";

import { type DemoAccount, DemoCredentials } from "@/components/auth/demo-credentials";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useRouter } from "@/i18n/navigation";

/**
 * Credentials sign-in form (ADR 0009). Calls Auth.js with redirect:false so we
 * can show an inline error, then returns the user to the guarded internal route
 * they requested. A direct visit without a return target keeps the locale root
 * fallback.
 */
export function LoginForm({
  returnTo,
  demoAccounts,
}: {
  returnTo: string | null;
  demoAccounts: DemoAccount[];
}) {
  const t = useTranslations("auth.login");
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [selectedUsername, setSelectedUsername] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(false);
  const [pending, setPending] = useState(false);

  function selectDemoAccount(account: DemoAccount) {
    setUsername(account.username);
    setPassword(account.password);
    setSelectedUsername(account.username);
    setError(false);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(false);
    const result = await signIn("credentials", { username, password, redirect: false });
    setPending(false);
    if (!result || result.error) {
      setError(true);
      return;
    }
    router.push(returnTo ?? "/");
    router.refresh();
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col">
      <DemoCredentials
        accounts={demoAccounts}
        selectedUsername={selectedUsername}
        onSelect={selectDemoAccount}
      />

      <div className="my-5 flex items-center gap-3" aria-hidden="true">
        <span className="h-px flex-1 bg-[var(--border-subtle)]" />
        <span className="text-xs font-medium uppercase tracking-[0.14em] text-[var(--text-tertiary)]">
          {t("manualCredentials")}
        </span>
        <span className="h-px flex-1 bg-[var(--border-subtle)]" />
      </div>

      <label htmlFor="login-username" className="flex flex-col gap-2 text-sm">
        <span className="text-[12px] font-medium text-[var(--text-secondary)]">
          {t("username")}
        </span>
        <span className="relative">
          <UserRound className="-translate-y-1/2 pointer-events-none absolute top-1/2 left-4 z-10 h-4 w-4 text-slate-500" />
          <Input
            id="login-username"
            value={username}
            onChange={(e) => {
              setUsername(e.target.value);
              setSelectedUsername(null);
            }}
            autoComplete="username"
            required
            className="h-12 rounded-xl border-[var(--border-subtle)] bg-[var(--launcher-field-bg)] pr-4 pl-11 text-[14px] text-[var(--text-primary)] shadow-inner focus-visible:ring-1 focus-visible:ring-emerald-300/55"
          />
        </span>
      </label>

      <label htmlFor="login-password" className="mt-4 flex flex-col gap-2 text-sm">
        <span className="text-[12px] font-medium text-[var(--text-secondary)]">
          {t("password")}
        </span>
        <span className="relative">
          <KeyRound className="-translate-y-1/2 pointer-events-none absolute top-1/2 left-4 z-10 h-4 w-4 text-slate-500" />
          <Input
            id="login-password"
            type={showPassword ? "text" : "password"}
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              setSelectedUsername(null);
            }}
            autoComplete="current-password"
            required
            className="h-12 rounded-xl border-[var(--border-subtle)] bg-[var(--launcher-field-bg)] pr-12 pl-11 text-[14px] text-[var(--text-primary)] shadow-inner focus-visible:ring-1 focus-visible:ring-emerald-300/55"
          />
          <button
            type="button"
            onClick={() => setShowPassword((visible) => !visible)}
            aria-label={showPassword ? t("hidePassword") : t("showPassword")}
            className="-translate-y-1/2 absolute top-1/2 right-2.5 grid h-8 w-8 place-items-center rounded-lg text-slate-500 transition-colors hover:bg-white/[0.05] hover:text-[var(--tessera-text-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
          >
            {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </span>
      </label>

      {error ? (
        <p
          role="alert"
          className="mt-3 rounded-xl border border-red-400/20 bg-red-400/[0.06] px-3 py-2.5 text-[12px] text-[var(--tessera-fg-danger)]"
        >
          {t("error")}
        </p>
      ) : null}

      <Button
        type="submit"
        variant="accent"
        size="lg"
        disabled={pending}
        // Four colour literals used to live on this line, and a literal cannot follow a
        // theme: under "Clair" the page's single most important action was a yellow slab.
        // The look now comes from `--launcher-btn-primary*` (dark unchanged, light teal).
        className="launcher-btn-primary mt-5 h-12 w-full rounded-lg border text-[14px] font-semibold"
      >
        <LogIn className="h-4 w-4" />
        {pending ? t("submitting") : t("submit")}
      </Button>
    </form>
  );
}
