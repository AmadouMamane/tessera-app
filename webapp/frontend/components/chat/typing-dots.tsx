import { useTranslations } from "next-intl";

export function TypingDots() {
  const t = useTranslations("chat");
  return (
    <div className="flex items-center" aria-label="typing">
      <div className="relative overflow-hidden rounded-full border border-gold-500/20 bg-navy-900/40 px-4 py-1.5 shadow-[inset_0_0_12px_rgba(185,146,69,0.1)] dark:border-gold-400/20 dark:bg-black/40">
        <span className="relative z-10 flex items-center gap-2 text-[0.7rem] font-medium uppercase tracking-wider text-gold-400/80">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-gold-400 opacity-75" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-gold-500" />
          </span>
          {t("assistantSaid")} réfléchit...
        </span>
        {/* Shimmer sweeping effect */}
        <div className="absolute inset-0 z-0 animate-[shimmer_2s_infinite] bg-[linear-gradient(110deg,transparent,rgba(215,190,138,0.15),transparent)] bg-[length:200%_100%]" />
      </div>
    </div>
  );
}
