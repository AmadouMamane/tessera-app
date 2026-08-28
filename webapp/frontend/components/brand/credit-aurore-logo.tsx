import { cn } from "@/lib/cn";

interface CreditAuroreLogoMarkProps {
  className?: string;
  gradientIdPrefix?: string;
}

interface CreditAuroreLogoProps {
  className?: string;
  markClassName?: string;
  textClassName?: string;
  wordmarkClassName?: string;
  taglineClassName?: string;
  gradientIdPrefix?: string;
}

export function CreditAuroreLogoMark({
  className,
  gradientIdPrefix = "caLogo",
}: CreditAuroreLogoMarkProps) {
  const greenId = `${gradientIdPrefix}Green`;
  const goldId = `${gradientIdPrefix}Gold`;

  return (
    <svg className={className} viewBox="0 0 96 56" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={greenId} x1="4" x2="88" y1="4" y2="52">
          <stop offset="0" stopColor="#153f35" />
          <stop offset="1" stopColor="#071a17" />
        </linearGradient>
        <linearGradient id={goldId} x1="45" x2="83" y1="7" y2="49">
          <stop offset="0" stopColor="#d6bd4e" />
          <stop offset="1" stopColor="#8b7722" />
        </linearGradient>
      </defs>
      <path
        d="M42.8 10.2C35.4 4.6 23.6 5.4 16.1 13.3 5.3 24.8 8.4 45.6 24.2 50.2c6.5 1.9 13.6.2 18.4-4.2"
        fill="none"
        stroke={`url(#${greenId})`}
        strokeLinecap="round"
        strokeWidth="8.2"
      />
      <path
        d="M39.2 49.5 57.2 8.5 76 49.5"
        fill="none"
        stroke={`url(#${goldId})`}
        strokeLinejoin="miter"
        strokeWidth="7.6"
      />
      <path d="M48.6 34.3h17.9" stroke="#f3e4a8" strokeLinecap="round" strokeWidth="3.2" />
      <path
        d="M31.8 46.7C45.8 36.8 63.8 33.5 88 34.9"
        fill="none"
        stroke={`url(#${greenId})`}
        strokeLinecap="round"
        strokeWidth="3.4"
      />
      <path
        d="M76.9 7.1 79.8 15.1 87.9 18 79.8 20.9 76.9 28.9 74 20.9 65.9 18 74 15.1z"
        fill={`url(#${goldId})`}
      />
      <path
        d="M76.9 10.4 78.5 16.4 84.5 18 78.5 19.6 76.9 25.6 75.3 19.6 69.3 18 75.3 16.4z"
        fill="#f6e7a7"
        opacity="0.72"
      />
    </svg>
  );
}

export function CreditAuroreLogo({
  className,
  markClassName,
  textClassName,
  wordmarkClassName,
  taglineClassName,
  gradientIdPrefix,
}: CreditAuroreLogoProps) {
  return (
    <div className={cn("flex items-center", className)} aria-label="Crédit Aurore">
      <CreditAuroreLogoMark
        className={cn("block h-11 w-[74px] shrink-0 overflow-visible", markClassName)}
        gradientIdPrefix={gradientIdPrefix}
      />
      <span className={cn("text-[#050816] leading-[1.05]", textClassName)}>
        <strong
          className={cn("block font-[850] text-[13.5px] tracking-[0.45px]", wordmarkClassName)}
        >
          CRÉDIT AURORE
        </strong>
        <small
          className={cn(
            "mt-[3px] block font-bold text-xs text-[#6f5c35] uppercase tracking-[0.7px]",
            taglineClassName,
          )}
        >
          Banque & assurance
        </small>
      </span>
    </div>
  );
}
