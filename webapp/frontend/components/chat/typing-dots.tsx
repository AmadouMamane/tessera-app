export function TypingDots() {
  return (
    <div className="flex items-center" aria-label="typing">
      <style>{`
        @keyframes d1 {
          0%, 20%, 45% { transform: translate(4px, 14px); opacity: 0.4; }
          10%, 30% { transform: translate(4px, 6px); opacity: 1; }
          55% { transform: translate(14px, 2px) scale(1.1); opacity: 1; }
          70% { transform: translate(14px, -1px) scale(1.2); opacity: 0.8; }
          85% { transform: translate(14px, 3px) scale(1.1); opacity: 1; }
          100% { transform: translate(4px, 14px); opacity: 0.4; }
        }
        @keyframes d2 {
          0%, 5%, 25%, 45% { transform: translate(14px, 14px); opacity: 0.4; }
          15%, 35% { transform: translate(14px, 6px); opacity: 1; }
          55% { transform: translate(22px, 14px) scale(0.9); opacity: 0.8; }
          70% { transform: translate(25px, 16px) scale(1); opacity: 1; }
          85% { transform: translate(21px, 13px) scale(0.9); opacity: 0.8; }
          100% { transform: translate(14px, 14px); opacity: 0.4; }
        }
        @keyframes d3 {
          0%, 10%, 30%, 45% { transform: translate(24px, 14px); opacity: 0.4; }
          20%, 40% { transform: translate(24px, 6px); opacity: 1; }
          55% { transform: translate(6px, 14px) scale(1); opacity: 0.8; }
          70% { transform: translate(3px, 16px) scale(1.1); opacity: 1; }
          85% { transform: translate(7px, 13px) scale(1); opacity: 0.8; }
          100% { transform: translate(24px, 14px); opacity: 0.4; }
        }
      `}</style>
      <div className="relative h-7 w-9 ml-1">
        <div 
          className="absolute top-0 left-0 h-1.5 w-1.5 rounded-full bg-gradient-to-br from-gold-300 to-gold-500 shadow-[0_0_8px_rgba(234,179,8,0.6)]" 
          style={{ animation: 'd1 4s infinite ease-in-out' }} 
        />
        <div 
          className="absolute top-0 left-0 h-1.5 w-1.5 rounded-full bg-gradient-to-br from-gold-400 to-gold-600 shadow-[0_0_8px_rgba(234,179,8,0.6)]" 
          style={{ animation: 'd2 4s infinite ease-in-out' }} 
        />
        <div 
          className="absolute top-0 left-0 h-1.5 w-1.5 rounded-full bg-gradient-to-br from-gold-500 to-gold-700 shadow-[0_0_8px_rgba(234,179,8,0.6)]" 
          style={{ animation: 'd3 4s infinite ease-in-out' }} 
        />
      </div>
    </div>
  );
}
