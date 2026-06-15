"use client";

import { LogIn } from "lucide-react";
import { signIn } from "next-auth/react";
import { useTranslations } from "next-intl";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useRouter } from "@/i18n/navigation";

/**
 * Credentials sign-in form (ADR 0009). Calls Auth.js with redirect:false so we
 * can show an inline error, then navigates to the selector on success. The
 * server route redirects single-space users to their only allowed shell.
 */
export function LoginForm() {
  const t = useTranslations("auth.login");
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(false);
  const [pending, setPending] = useState(false);

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
    router.push("/select-space");
    router.refresh();
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3">
      <label htmlFor="login-username" className="flex flex-col gap-1.5 text-sm">
        <span className="font-medium text-[var(--muted-foreground)]">{t("username")}</span>
        <Input
          id="login-username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          required
        />
      </label>
      <label htmlFor="login-password" className="flex flex-col gap-1.5 text-sm">
        <span className="font-medium text-[var(--muted-foreground)]">{t("password")}</span>
        <Input
          id="login-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
        />
      </label>
      {error ? (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {t("error")}
        </p>
      ) : null}
      <Button type="submit" variant="primary" disabled={pending} className="mt-1 gap-2">
        <LogIn className="h-4 w-4" />
        {pending ? t("submitting") : t("submit")}
      </Button>
    </form>
  );
}
