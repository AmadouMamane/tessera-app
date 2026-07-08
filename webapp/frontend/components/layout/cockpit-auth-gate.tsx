"use client";

import { useSession } from "next-auth/react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";
import { useEffect } from "react";

import { useRouter } from "@/i18n/navigation";

function hasCockpitRole(role: string | undefined): boolean {
  return role === "admin" || role === "auditor" || role === "superadmin";
}

export function CockpitAuthGate({ children }: { children: ReactNode }) {
  const { data: session, status } = useSession();
  const router = useRouter();
  const t = useTranslations("auth.locked");
  const role = session?.user?.role;
  const allowed = hasCockpitRole(role);

  useEffect(() => {
    if (status !== "loading" && !allowed) router.replace("/login");
  }, [allowed, router, status]);

  if (status === "loading" || !allowed) {
    return (
      <div className="flex h-screen items-center justify-center bg-[var(--tessera-bg)] text-[var(--tessera-text-muted)]">
        <div className="rounded-lg border border-[var(--tessera-border)] bg-[var(--tessera-surface)] px-4 py-3 text-sm shadow-[var(--shadow-card)]">
          {t("title")}
        </div>
      </div>
    );
  }

  return children;
}
