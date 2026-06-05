import type * as React from 'react';
import { mdiBrubru } from './mdi_brubru';

export type BrubruIconProps = {
  size?: number | string;
  color?: string;
  title?: string;
  className?: string;
  style?: React.CSSProperties;
};

export function BrubruIcon({
  size = 1,
  color = 'currentColor',
  title,
  className,
  style,
}: BrubruIconProps): React.ReactNode {
  const dim = typeof size === 'number' ? `${size * 1.5}rem` : size;
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      width={dim}
      height={dim}
      className={className}
      style={style}
      role={title ? 'img' : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
    >
      {title ? <title>{title}</title> : null}
      <path d={mdiBrubru} fill={color} fillRule="evenodd" />
    </svg>
  );
}

export { mdiBrubru };
