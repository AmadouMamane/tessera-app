export function TypingDots() {
  return (
    <div className="flex items-center" aria-label="typing">
      <style>{`
        @keyframes d1 {
          0%  { transform: translate(9.5px, 8.5px) rotate(0deg) translate(-4.5px, 5.5px) scale(1); opacity: 0.4; animation-timing-function: ease-out; }
          6%  { transform: translate(9.5px, 8.5px) rotate(0deg) translate(-4.5px, 1.5px) scale(1); opacity: 1; animation-timing-function: ease-in; }
          12% { transform: translate(9.5px, 8.5px) rotate(0deg) translate(-4.5px, 5.5px) scale(1); opacity: 0.4; animation-timing-function: linear; }
          25% { transform: translate(9.5px, 8.5px) rotate(0deg) translate(-4.5px, 5.5px) scale(1); opacity: 0.4; animation-timing-function: ease-in-out; }
          50% { transform: translate(9.5px, 8.5px) rotate(180deg) translate(-4.5px, 5.5px) scale(1.15); opacity: 1; animation-timing-function: ease-in-out; }
          65% { transform: translate(9.5px, 8.5px) rotate(180deg) translate(-4.5px, 5.5px) scale(1.15); opacity: 1; animation-timing-function: ease-in-out; }
          90% { transform: translate(9.5px, 8.5px) rotate(0deg) translate(-4.5px, 5.5px) scale(1); opacity: 0.4; animation-timing-function: linear; }
          100%{ transform: translate(9.5px, 8.5px) rotate(0deg) translate(-4.5px, 5.5px) scale(1); opacity: 0.4; }
        }
        @keyframes d2 {
          0%  { transform: translate(17px, 14px) rotate(0deg) translate(-3px, 0px) scale(1); opacity: 0.4; animation-timing-function: linear; }
          6%  { transform: translate(17px, 14px) rotate(0deg) translate(-3px, 0px) scale(1); opacity: 0.4; animation-timing-function: ease-out; }
          12% { transform: translate(17px, 14px) rotate(0deg) translate(-3px, -4px) scale(1); opacity: 1; animation-timing-function: ease-in; }
          18% { transform: translate(17px, 14px) rotate(0deg) translate(-3px, 0px) scale(1); opacity: 0.4; animation-timing-function: linear; }
          25% { transform: translate(17px, 14px) rotate(0deg) translate(-3px, 0px) scale(1); opacity: 0.4; animation-timing-function: ease-in-out; }
          50% { transform: translate(17px, 14px) rotate(-180deg) translate(-3px, 0px) scale(0.95); opacity: 0.8; animation-timing-function: ease-in-out; }
          65% { transform: translate(17px, 14px) rotate(-180deg) translate(-3px, 0px) scale(0.95); opacity: 0.8; animation-timing-function: ease-in-out; }
          90% { transform: translate(17px, 14px) rotate(0deg) translate(-3px, 0px) scale(1); opacity: 0.4; animation-timing-function: linear; }
          100%{ transform: translate(17px, 14px) rotate(0deg) translate(-3px, 0px) scale(1); opacity: 0.4; }
        }
        @keyframes d3 {
          0%  { transform: translate(15.5px, 14px) rotate(0deg) translate(7.5px, 0px) scale(1); opacity: 0.4; animation-timing-function: linear; }
          12% { transform: translate(15.5px, 14px) rotate(0deg) translate(7.5px, 0px) scale(1); opacity: 0.4; animation-timing-function: ease-out; }
          18% { transform: translate(15.5px, 14px) rotate(0deg) translate(7.5px, -4px) scale(1); opacity: 1; animation-timing-function: ease-in; }
          24% { transform: translate(15.5px, 14px) rotate(0deg) translate(7.5px, 0px) scale(1); opacity: 0.4; animation-timing-function: linear; }
          25% { transform: translate(15.5px, 14px) rotate(0deg) translate(7.5px, 0px) scale(1); opacity: 0.4; animation-timing-function: ease-in-out; }
          50% { transform: translate(15.5px, 14px) rotate(180deg) translate(7.5px, 0px) scale(1.0); opacity: 0.8; animation-timing-function: ease-in-out; }
          65% { transform: translate(15.5px, 14px) rotate(180deg) translate(7.5px, 0px) scale(1.0); opacity: 0.8; animation-timing-function: ease-in-out; }
          90% { transform: translate(15.5px, 14px) rotate(0deg) translate(7.5px, 0px) scale(1); opacity: 0.4; animation-timing-function: linear; }
          100%{ transform: translate(15.5px, 14px) rotate(0deg) translate(7.5px, 0px) scale(1); opacity: 0.4; }
        }
      `}</style>
      <div className="relative h-7 w-9 ml-1">
        <div
          className="absolute top-0 left-0 h-1.5 w-1.5 rounded-full bg-gradient-to-br from-gold-300 to-gold-500 shadow-[0_0_4px_rgba(234,179,8,0.4)]"
          style={{ animation: "d1 6s infinite linear" }}
        />
        <div
          className="absolute top-0 left-0 h-1.5 w-1.5 rounded-full bg-gradient-to-br from-gold-400 to-gold-600 shadow-[0_0_4px_rgba(234,179,8,0.4)]"
          style={{ animation: "d2 6s infinite linear" }}
        />
        <div
          className="absolute top-0 left-0 h-1.5 w-1.5 rounded-full bg-gradient-to-br from-gold-500 to-gold-700 shadow-[0_0_4px_rgba(234,179,8,0.4)]"
          style={{ animation: "d3 6s infinite linear" }}
        />
      </div>
    </div>
  );
}
