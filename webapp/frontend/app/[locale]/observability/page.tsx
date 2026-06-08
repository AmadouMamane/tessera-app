import { getTranslations, setRequestLocale } from "next-intl/server";

import { OperatorLocked } from "@/components/auth/operator-locked";
import { AppShell } from "@/components/layout/app-shell";
import { currentRole, isOperator } from "@/lib/auth/session";
import { ExternalLink, Activity, MessageSquare, AlertTriangle, ShieldCheck, Zap, Server } from "lucide-react";

export const dynamic = "force-dynamic";

interface ObservabilityPageProps {
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: ObservabilityPageProps) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "observability" });
  return { title: t("title") };
}

export default async function ObservabilityPage({ params }: ObservabilityPageProps) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "observability" });
  const role = await currentRole();

  if (!isOperator(role)) {
    return (
      <AppShell title={t("title")} description={t("description")}>
        <OperatorLocked locale={locale} />
      </AppShell>
    );
  }

  const langfuseUrl = process.env.NEXT_PUBLIC_LANGFUSE_HOST || "http://localhost:3080";
  const pk = process.env.NEXT_PUBLIC_LANGFUSE_PUBLIC_KEY;
  const sk = process.env.LANGFUSE_SECRET_KEY || "sk-lf-1234567890"; 
  
  let totalTraces = 0;
  let errorRate = 0;
  let totalTokens = 0;
  let totalCost = 0.0;
  let canaryCount = 0;
  let traces: any[] = [];
  
  try {
    const auth = Buffer.from(`${pk}:${sk}`).toString("base64");
    const apiUrl = process.env.LANGFUSE_HOST || langfuseUrl;
    
    // Fetch 50 traces for aggregates
    const res = await fetch(`${apiUrl}/api/public/traces?page=1&limit=50`, {
      headers: { Authorization: `Basic ${auth}` },
      next: { revalidate: 10 }
    });
    
    if (res.ok) {
      const data = await res.json();
      traces = data.data || [];
      totalTraces = data.meta?.totalItems || traces.length;
      
      const errorCount = traces.filter((t: any) => t.tags?.includes("error") || t.metadata?.finish_reason === "error").length;
      errorRate = traces.length > 0 ? Math.round((errorCount / traces.length) * 100) : 0;

      // Calculate FinOps (Token usage & Cost approximation)
      traces.forEach(t => {
        totalTokens += t.totalUsage || 0;
        totalCost += t.totalCost || 0.0;
        // Canary count (Assuming tags or variant field)
        if (t.tags?.includes("canary") || t.metadata?.variant === "canary" || t.tags?.includes("shadow")) {
          canaryCount++;
        }
      });
    }
  } catch (e) {
    console.error("Failed to fetch Langfuse metrics", e);
  }

  const canaryRatio = traces.length > 0 ? Math.round((canaryCount / traces.length) * 100) : 0;
  
  // Extract the top 10 recent traces for the Heartbeat
  const recentTraces = traces.slice(0, 10);

  return (
    <AppShell title={t("title")} description={t("description")}>
      <div className="flex flex-col w-full gap-6 px-4 py-8 max-w-6xl mx-auto">
        
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">{t("title")}</h2>
            <p className="text-sm text-[var(--muted-foreground)] mt-1">
              Centre de contrôle temps-réel des requêtes LLM.
            </p>
          </div>
          <a
            href={langfuseUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            Ouvrir l'Interface Complète Langfuse
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
        
        {/* Global KPIs */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="flex flex-col p-5 rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-sm">
            <div className="flex items-center gap-2 text-[var(--muted-foreground)] mb-2">
              <MessageSquare className="w-4 h-4" />
              <span className="text-sm font-medium">Traces (Volume)</span>
            </div>
            <div className="text-2xl font-bold">{totalTraces}</div>
          </div>
          
          <div className="flex flex-col p-5 rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-sm">
            <div className="flex items-center gap-2 text-[var(--muted-foreground)] mb-2">
              <AlertTriangle className="w-4 h-4 text-red-500" />
              <span className="text-sm font-medium">Taux d'erreur récent</span>
            </div>
            <div className="text-2xl font-bold">{errorRate}%</div>
          </div>

          <div className="flex flex-col p-5 rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-sm">
            <div className="flex items-center justify-between text-[var(--muted-foreground)] mb-2">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-500" />
                <span className="text-sm font-medium">FinOps (Tokens & Coût)</span>
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold">{(totalTokens / 1000).toFixed(1)}k</span>
              <span className="text-sm text-[var(--muted-foreground)]">/ ${totalCost.toFixed(4)}</span>
            </div>
          </div>

          <div className="flex flex-col p-5 rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-sm">
            <div className="flex items-center gap-2 text-[var(--muted-foreground)] mb-2">
              <Server className="w-4 h-4 text-indigo-500" />
              <span className="text-sm font-medium">A/B Traffic (Canary)</span>
            </div>
            <div className="text-2xl font-bold">{canaryRatio}%</div>
          </div>
        </div>

        {/* Live Heartbeat Table */}
        <div className="border border-[var(--border)] bg-[var(--card)] rounded-xl overflow-hidden shadow-sm">
          <div className="p-5 border-b border-[var(--border)] flex items-center justify-between">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <Activity className="w-5 h-5 text-green-500" />
              Live Heartbeat (10 dernières requêtes)
            </h3>
            <span className="flex h-3 w-3 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-[var(--muted-foreground)] uppercase bg-[var(--muted)]/50">
                <tr>
                  <th className="px-6 py-3 font-medium">Trace ID</th>
                  <th className="px-6 py-3 font-medium">Statut</th>
                  <th className="px-6 py-3 font-medium">Latence</th>
                  <th className="px-6 py-3 font-medium">Tokens</th>
                  <th className="px-6 py-3 font-medium">Input Snippet</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {recentTraces.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-[var(--muted-foreground)]">
                      Aucune trace récente trouvée.
                    </td>
                  </tr>
                ) : (
                  recentTraces.map((trace) => (
                    <tr key={trace.id} className="hover:bg-[var(--muted)]/30 transition-colors">
                      <td className="px-6 py-4 font-mono text-xs text-[var(--muted-foreground)]">
                        {trace.id.substring(0, 8)}...
                      </td>
                      <td className="px-6 py-4">
                        {(trace.tags?.includes("error") || trace.metadata?.finish_reason === "error") ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400">
                            Erreur
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
                            Succès
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-[var(--muted-foreground)]">
                        {trace.latency ? `${(trace.latency * 1000).toFixed(0)} ms` : "-"}
                      </td>
                      <td className="px-6 py-4 text-[var(--muted-foreground)]">
                        {trace.totalUsage || 0}
                      </td>
                      <td className="px-6 py-4 truncate max-w-xs text-[var(--muted-foreground)]" title={typeof trace.input === 'string' ? trace.input : JSON.stringify(trace.input)}>
                        {trace.input ? (typeof trace.input === 'string' ? trace.input : JSON.stringify(trace.input)) : "N/A"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Time-Travel Replay Section */}
        <div className="border border-[var(--border)] bg-[var(--card)] rounded-xl overflow-hidden shadow-sm">
          <div className="p-6 border-b border-[var(--border)] bg-[var(--muted)]/30">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-blue-500" />
              Time-Travel Replay (Beta)
            </h3>
            <p className="text-sm text-[var(--muted-foreground)] mt-1">
              Rejouez l'état exact du graphe LangGraph à partir d'une trace de production pour déboguer une session utilisateur étape par étape.
            </p>
          </div>
          <div className="p-6">
            <div className="flex flex-col sm:flex-row gap-4">
              <input 
                type="text" 
                placeholder="Entrez un Trace ID Langfuse..." 
                className="flex-1 px-4 py-2 bg-transparent border border-[var(--border)] rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              />
              <button className="bg-[var(--foreground)] text-[var(--background)] px-6 py-2 rounded-lg font-medium hover:opacity-90 transition-opacity">
                Lancer le Replay
              </button>
            </div>
            <div className="mt-4 text-xs text-[var(--muted-foreground)]">
              * Le replay chargera les entrées/sorties depuis Langfuse et recréera le Thread ID de mémoire associé via l'API locale.
            </div>
          </div>
        </div>

      </div>
    </AppShell>
  );
}
