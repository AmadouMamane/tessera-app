export function TypingDots() {
  return (
    <div className="flex items-center" aria-label="typing">
      <style>{`
        @keyframes d1 {
          0%, 15% { transform: translate(4px, 14px); opacity: 0.2; }
          25% { transform: translate(4px, 8px); opacity: 0.6; }
          35%, 45% { transform: translate(4px, 14px); opacity: 0.2; }
          
          55% { transform: translate(14px, 4px) scale(1.05); opacity: 0.8; }
          65% { transform: translate(14px, 2px) scale(1.1); opacity: 1; }
          80% { transform: translate(14px, 4px) scale(1.05); opacity: 0.8; }
          
          95%, 100% { transform: translate(4px, 14px); opacity: 0.2; }
        }
        @keyframes d2 {
          0%, 25% { transform: translate(14px, 14px); opacity: 0.2; }
          35% { transform: translate(14px, 8px); opacity: 0.6; }
          45%, 50% { transform: translate(14px, 14px); opacity: 0.2; }
          
          60% { transform: translate(22px, 14px) scale(0.95); opacity: 0.7; }
          70% { transform: translate(24px, 16px) scale(1); opacity: 0.9; }
          80% { transform: translate(22px, 14px) scale(0.95); opacity: 0.7; }
          
          95%, 100% { transform: translate(14px, 14px); opacity: 0.2; }
        }
        @keyframes d3 {
          0%, 35% { transform: translate(24px, 14px); opacity: 0.2; }
          45% { transform: translate(24px, 8px); opacity: 0.6; }
          55%, 60% { transform: translate(24px, 14px); opacity: 0.2; }
          
          68% { transform: translate(6px, 14px) scale(0.95); opacity: 0.7; }
          78% { transform: translate(4px, 16px) scale(1); opacity: 0.9; }
          88% { transform: translate(6px, 14px) scale(0.95); opacity: 0.7; }
          
          95%, 100% { transform: translate(24px, 14px); opacity: 0.2; }
        }
      `}</style>
      <div className="relative h-7 w-9 ml-1">
        <div 
          className="absolute top-0 left-0 h-1.5 w-1.5 rounded-full bg-gradient-to-br from-gold-300 to-gold-500 shadow-[0_0_4px_rgba(234,179,8,0.4)]" 
          style={{ animation: 'd1 6s infinite cubic-bezier(0.4, 0, 0.2, 1)' }} 
        />
        <div 
          className="absolute top-0 left-0 h-1.5 w-1.5 rounded-full bg-gradient-to-br from-gold-400 to-gold-600 shadow-[0_0_4px_rgba(234,179,8,0.4)]" 
          style={{ animation: 'd2 6s infinite cubic-bezier(0.4, 0, 0.2, 1)' }} 
        />
        <div 
          className="absolute top-0 left-0 h-1.5 w-1.5 rounded-full bg-gradient-to-br from-gold-500 to-gold-700 shadow-[0_0_4px_rgba(234,179,8,0.4)]" 
          style={{ animation: 'd3 6s infinite cubic-bezier(0.4, 0, 0.2, 1)' }} 
        />
      </div>
    </div>
  );
}
