// frontend/src/components/shared/trainer_badge.tsx
import type { ReactNode } from 'react';
import './trainer_badge.css';

/**
 * TrainerStarRing - Wraps any avatar element with a rotating ring of gold stars.
 * 12 four-pointed stars at 30-degree intervals orbiting the avatar.
 */
export const TrainerStarRing = ({
  size,
  children,
}: {
  size: number; // 44 = profile, 28 = header
  children: ReactNode;
}) => {
  const ringRadius = size / 2 + 6;
  const starSize = size >= 40 ? 6 : 4;
  const stars = Array.from({ length: 12 }, (_, i) => i * 30);

  return (
    <span
      className="trainer-star-ring"
      style={{
        width: size,
        height: size,
        '--trainer-ring-radius': `${ringRadius}px`,
      } as React.CSSProperties}
    >
      {children}
      <span className="trainer-star-ring__orbit" aria-hidden="true">
        {stars.map((deg) => (
          <svg
            key={deg}
            className="trainer-star-ring__star"
            style={{
              transform: `rotate(${deg}deg) translateY(-${ringRadius}px)`,
            }}
            width={starSize}
            height={starSize}
            viewBox="0 0 24 24"
          >
            <path
              d="M12 1L14.5 9.5L23 12L14.5 14.5L12 23L9.5 14.5L1 12L9.5 9.5Z"
              fill="#d97706"
            />
          </svg>
        ))}
      </span>
    </span>
  );
};

/**
 * TrainerShieldBadge - Inline SVG shield with "BT" monogram.
 * Gold fill, white text. Appended after trainer names.
 */
export const TrainerShieldBadge = ({
  size = 'md',
}: {
  size?: 'sm' | 'md';
}) => {
  const px = size === 'sm' ? 14 : 18;

  return (
    <svg
      className="trainer-shield-badge"
      width={px}
      height={px}
      viewBox="0 0 24 24"
      aria-label="Brubru Trainer"
    >
      <path
        d="M12 1L3 5V11C3 16.55 6.84 21.74 12 23C17.16 21.74 21 16.55 21 11V5L12 1Z"
        fill="#d97706"
      />
      <text
        x="12"
        y="15"
        textAnchor="middle"
        fill="#ffffff"
        fontSize="9"
        fontWeight="700"
        fontFamily="sans-serif"
      >
        BT
      </text>
    </svg>
  );
};

/**
 * TrainerNameGlow - Wraps a name in a shimmering gradient text effect.
 * Gradient sweeps from text colour through blue and gold.
 */
export const TrainerNameGlow = ({
  children,
}: {
  children: ReactNode;
}) => (
  <span className="trainer-name-glow">{children}</span>
);
