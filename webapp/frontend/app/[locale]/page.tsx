import { getTranslations, setRequestLocale } from "next-intl/server";

import { AppShell } from "@/components/layout/app-shell";
import { OverviewDashboard } from "@/components/overview/overview-dashboard";

interface OverviewPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: OverviewPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "overview" });
  return { title: t("title") };
}

export default async function OverviewPage({ params }: OverviewPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "overview" });

  return (
    <AppShell
      title={t("title")}
      description={t("subtitle")}
      contentWidth="wide"
      topbarContext={[
        {
          label: t("context.environment"),
          value: "prod",
          tone: "success",
          leading: "status",
          control: "select",
          options: [
            { value: "prod", label: "Prod" },
            { value: "staging", label: "Staging" },
            { value: "dev", label: "Dev" },
          ],
        },
        {
          label: t("context.lifecycle"),
          value: "d7",
          leading: "history",
          control: "select",
          options: [
            { value: "h24", label: t("context.lifecycle24h") },
            { value: "d7", label: t("context.lifecycleValue") },
            { value: "d30", label: t("context.lifecycle30d") },
          ],
        },
        {
          label: t("context.agent"),
          value: "banking",
          control: "select",
          options: [
            { value: "banking", label: t("context.agentValue") },
            { value: "support", label: t("context.agentSupport") },
          ],
        },
        { label: t("context.model"), value: "Llama 3.2 3B", control: "model" },
        { label: t("context.language"), value: "FR", leading: "globe", control: "locale" },
      ]}
      topbarActions={[
        {
          label: t("actions.exportReport"),
          icon: "download",
          variant: "outline",
          action: "export",
        },
        {
          label: t("actions.generateEvidencePack"),
          icon: "evidence",
          variant: "accent",
          action: "evidence",
        },
      ]}
    >
      <OverviewDashboard />
    </AppShell>
  );
}
