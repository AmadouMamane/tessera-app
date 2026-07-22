"use client";

import { useTranslations } from "next-intl";

const ROLE_KEYS = {
  admin: "admin",
  "admin+": "admin",
  operator: "operator",
  "operator+": "operator",
  compliance: "compliance",
  "compliance+": "compliance",
  auditor: "auditor",
  "auditor+": "auditor",
  dual: "dualControl",
  "dual control": "dualControl",
} as const;

export function AuthorityLabel({ authority }: { authority: string }) {
  const t = useTranslations("authority");
  const key = ROLE_KEYS[authority.trim().toLowerCase() as keyof typeof ROLE_KEYS];

  return <span title={t("technical", { role: authority })}>{key ? t(key) : authority}</span>;
}
