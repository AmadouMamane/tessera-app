"use client";

import { Cpu } from "lucide-react";
import { useEffect, useState } from "react";

import {
  CHAT_MODEL_EVENT,
  DEFAULT_CHAT_MODEL,
  findModel,
  getStoredModel,
  modelHostingShort,
} from "@/lib/models";

/**
 * Topbar badge showing the active chat model, reactive to the Settings picker
 * (same-tab via a custom event, cross-tab via the storage event). Renders the
 * default on the server to keep hydration stable, then syncs on mount.
 */
export function ModelBadge() {
  const [modelId, setModelId] = useState(DEFAULT_CHAT_MODEL);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setModelId(getStoredModel());
    const sync = () => setModelId(getStoredModel());
    window.addEventListener(CHAT_MODEL_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(CHAT_MODEL_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  const model = findModel(mounted ? modelId : DEFAULT_CHAT_MODEL);
  const hosting = modelHostingShort(model);

  return (
    <span
      title={`Modèle actif : ${model.label} · ${model.params} · ${hosting}`}
      className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] bg-[var(--muted)]/40 py-1 pl-2 pr-2.5 text-xs font-medium shadow-sm backdrop-blur transition-colors"
    >
      <Cpu className="h-3.5 w-3.5 text-[var(--tessera-fg-gold)]" aria-hidden />
      <span className="text-[var(--foreground)]">{model.label}</span>
      <span
        aria-hidden
        className="h-1.5 w-1.5 rounded-full bg-green-500 shadow-[0_0_6px_1px_oklch(0.7_0.17_150/0.6)]"
      />
      <span className="hidden text-[var(--muted-foreground)] sm:inline">{hosting}</span>
    </span>
  );
}
