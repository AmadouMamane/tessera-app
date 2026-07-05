export function TypingDots() {
  return (
    <div className="flex items-center" aria-label="typing">
      <style>{`
        @keyframes d1 {
          0%, 8% { transform: translate(4px, 14px); opacity: 0.4; }
          18% { transform: translate(4px, 4px); opacity: 1; }
          28%, 38% { transform: translate(4px, 14px); opacity: 0.4; }
          
          45% { transform: translate(12px, 12px) scale(0.8); opacity: 0.8; }
          55% { transform: translate(14px, 2px) scale(1.2); opacity: 1; }
          65% { transform: translate(16px, 0px) scale(1.1); opacity: 0.9; }
          75% { transform: translate(13px, 4px) scale(1.15); opacity: 1; }
          
          85% { transform: translate(6px, 10px) scale(0.9); opacity: 0.6; }
          95%, 100% { transform: translate(4px, 14px); opacity: 0.4; }
        }
        @keyframes d2 {
          0%, 15% { transform: translate(14px, 14px); opacity: 0.4; }
          25% { transform: translate(14px, 4px); opacity: 1; }
          35%, 38% { transform: translate(14px, 14px); opacity: 0.4; }
          
          45% { transform: translate(18px, 18px) scale(0.8); opacity: 0.8; }
          55% { transform: translate(22px, 14px) scale(0.9); opacity: 0.9; }
          65% { transform: translate(25px, 16px) scale(0.95); opacity: 1; }
          75% { transform: translate(20px, 12px) scale(0.9); opacity: 0.8; }
          
          85% { transform: translate(16px, 16px) scale(0.8); opacity: 0.6; }
          95%, 100% { transform: translate(14px, 14px); opacity: 0.4; }
        }
        @keyframes d3 {
          0%, 22% { transform: translate(24px, 14px); opacity: 0.4; }
          32% { transform: translate(24px, 4px); opacity: 1; }
          42% { transform: translate(24px, 14px); opacity: 0.4; }
          
          48% { transform: translate(15px, 6px) scale(0.8); opacity: 0.8; }
          55% { transform: translate(6px, 14px) scale(1.1); opacity: 1; }
          65% { transform: translate(2px, 16px) scale(1); opacity: 0.9; }
          75% { transform: translate(8px, 12px) scale(1.05); opacity: 1; }
          
          85% { transform: translate(16px, 8px) scale(0.9); opacity: 0.6; }
          95%, 100% { transform: translate(24px, 14px); opacity: 0.4; }
        }
      `}</style>
      <div className="relative h-7 w-9 ml-1">
        <div 
          className="absolute top-0 left-0 h-1.5 w-1.5 rounded-full bg-gradient-to-br from-gold-300 to-gold-500 shadow-[0_0_8px_rgba(234,179,8,0.6)]" 
          style={{ animation: 'd1 5s infinite ease-in-out' }} 
        />
        <div 
          className="absolute top-0 left-0 h-1.5 w-1.5 rounded-full bg-gradient-to-br from-gold-400 to-gold-600 shadow-[0_0_8px_rgba(234,179,8,0.6)]" 
          style={{ animation: 'd2 5s infinite ease-in-out' }} 
        />
        <div 
          className="absolute top-0 left-0 h-1.5 w-1.5 rounded-full bg-gradient-to-br from-gold-500 to-gold-700 shadow-[0_0_8px_rgba(234,179,8,0.6)]" 
          style={{ animation: 'd3 5s infinite ease-in-out' }} 
        />
      </div>
    </div>
  );
}
