export function TypingDots() {
  return (
    <div className="flex items-center" aria-label="typing">
      <style>{`
        @keyframes d1 {
          0%, 100% { transform: translate(7px, 14px); opacity: 0.3; }
          50%      { transform: translate(14px, 2px) scale(1.15); opacity: 1; }
        }
        @keyframes d2 {
          0%, 100% { transform: translate(14px, 14px); opacity: 0.3; }
          50%      { transform: translate(21px, 14px) scale(0.95); opacity: 0.8; }
        }
        @keyframes d3 {
          0%, 100% { transform: translate(21px, 14px); opacity: 0.3; }
          50%      { transform: translate(7px, 14px) scale(1.0); opacity: 0.8; }
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
