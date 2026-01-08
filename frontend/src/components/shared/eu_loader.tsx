// frontend/src/components/shared/eu_loader.tsx
import './eu_loader.css';

interface EULoaderProps {
  size?: number;
  message?: string;
}

export const EULoader = ({ size = 60, message }: EULoaderProps) => {
  return (
    <div className="eu-loader">
      <div className="eu-loader__spinner" style={{ width: size, height: size }}>
        <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
          <circle
            className="eu-loader__circle"
            cx="50"
            cy="50"
            r="45"
            fill="none"
            stroke="#0693e3"
            strokeWidth="2"
          />
          {/* 12 EU stars in a circle */}
          {Array.from({ length: 12 }).map((_, i) => {
            const angle = (i * 30 - 90) * (Math.PI / 180);
            const x = 50 + 35 * Math.cos(angle);
            const y = 50 + 35 * Math.sin(angle);
            return (
              <g key={i}>
                <circle
                  className="eu-loader__star"
                  cx={x}
                  cy={y}
                  r="4"
                  fill="#0693e3"
                  style={{ animationDelay: `${i * 0.083}s` }}
                />
              </g>
            );
          })}
        </svg>
      </div>
      {message && <p className="eu-loader__message">{message}</p>}
    </div>
  );
};
