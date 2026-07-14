import { EVAL_PATHNAME, evalQuery } from "@/components/eval/eval-route";
import { redirect } from "@/i18n/navigation";

interface EvalPageProps {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/** The params the eval screen understands — the only ones worth carrying through. */
const EVAL_PARAMS = ["tab", "run", "case", "lang", "a", "b"] as const;

/**
 * `/eval` moved INTO `/surveiller/qualite-ia` (its `?vue=evaluations` view) — the page whose
 * sidebar entry had been promising this content while the screen itself was an orphan. This
 * redirect keeps every deep link an operator ever sent working, params intact.
 */
export default async function EvalPage({ params, searchParams }: EvalPageProps) {
  const { locale } = await params;
  const sp = await searchParams;
  const carried: Record<string, string> = {};
  for (const key of EVAL_PARAMS) {
    const value = sp[key];
    if (typeof value === "string" && value) {
      carried[key] = value;
    }
  }
  redirect({ href: { pathname: EVAL_PATHNAME, query: evalQuery(carried) }, locale });
}
