export function TypingDots() {
  return (
    <div className="flex items-center" aria-label="typing">
      <style>{`
        @keyframes d1 {
          0%, 100% { transform: translate(10.5px, 8px) rotate(0deg) translate(-3.5px, 6px) scale(1); opacity: 0.3; }
          50%      { transform: translate(10.5px, 8px) rotate(180deg) translate(-3.5px, 6px) scale(1.15); opacity: 1; }
        }
        @keyframes d2 {
          0%, 100% { transform: translate(17.5px, 14px) rotate(0deg) translate(-3.5px, 0px) scale(1); opacity: 0.3; }
          50%      { transform: translate(17.5px, 14px) rotate(-180deg) translate(-3.5px, 0px) scale(0.95); opacity: 0.8; }
        }
        @keyframes d3 {
          0%, 100% { transform: translate(14px, 14px) rotate(0deg) translate(7px, 0px) scale(1); opacity: 0.3; }
          50%      { transform: translate(14px, 14px) rotate(180deg) translate(7px, 0px) scale(1.0); opacity: 0.8; }
        }
      `}</style>
      <div className="relative h-7 w-9 ml-1">
        <div 
          className="absolute top-0 left-0 h-1.5 w-1.5 rounded-full bg-gradient-to-br from-gold-300 to-gold-500 shadow-[0_0_4px_rgba(234,179,8,0.4)]" 
          style={{ animation: 'd1 6s infinite ease-in-out' }} 
        />
        <div 
          className="absolute top-0 left-0 h-1.5 w-1.5 rounded-full bg-gradient-to-br from-gold-400 to-gold-600 shadow-[0_0_4px_rgba(234,179,8,0.4)]" 
          style={{ animation: 'd2 6s infinite ease-in-out' }} 
        />
        <div 
          className="absolute top-0 left-0 h-1.5 w-1.5 rounded-full bg-gradient-to-br from-gold-500 to-gold-700 shadow-[0_0_4px_rgba(234,179,8,0.4)]" 
          style={{ animation: 'd3 6s infinite ease-in-out' }} 
        />
      </div>
    </div>
  );
}
