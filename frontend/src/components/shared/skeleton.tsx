// frontend/src/components/shared/skeleton.tsx
import { useTranslation } from 'react-i18next';
import './skeleton.css';

interface SkeletonProps {
  variant?: 'text' | 'circular' | 'rectangular';
  width?: string | number;
  height?: string | number;
  className?: string;
}

export const Skeleton = ({
  variant = 'text',
  width,
  height,
  className = '',
}: SkeletonProps) => {
  const { t } = useTranslation();
  const style: React.CSSProperties = {
    width: typeof width === 'number' ? `${width}px` : width,
    height: typeof height === 'number' ? `${height}px` : height,
  };

  return (
    <div
      className={`skeleton skeleton--${variant} ${className}`}
      style={style}
      role="status"
      aria-label={t('common.loading')}
    />
  );
};

// Preset skeleton components for common use cases
export const MessageSkeleton = () => (
  <div className="skeleton-message">
    <div className="skeleton-message__header">
      <Skeleton variant="circular" width={32} height={32} />
      <Skeleton variant="text" width="120px" height="16px" />
    </div>
    <div className="skeleton-message__body">
      <Skeleton variant="text" width="100%" height="16px" />
      <Skeleton variant="text" width="90%" height="16px" />
      <Skeleton variant="text" width="75%" height="16px" />
    </div>
  </div>
);

export const AmendmentSkeleton = () => (
  <div className="skeleton-amendment">
    <div className="skeleton-amendment__header">
      <Skeleton variant="text" width="60px" height="16px" />
      <Skeleton variant="rectangular" width="70px" height="20px" />
    </div>
    <Skeleton variant="text" width="100%" height="14px" />
    <Skeleton variant="text" width="85%" height="14px" />
    <Skeleton variant="text" width="40px" height="12px" />
  </div>
);

export const CitationSkeleton = () => (
  <div className="skeleton-citation">
    <div className="skeleton-citation__header">
      <Skeleton variant="circular" width={20} height={20} />
      <Skeleton variant="text" width="100px" height="14px" />
    </div>
    <Skeleton variant="text" width="100%" height="16px" />
    <Skeleton variant="text" width="80%" height="16px" />
    <Skeleton variant="text" width="60px" height="12px" />
  </div>
);

// MEUB shapes. Nearly every sub-tab is a list of cards, so the placeholder that
// actually reduces perceived wait is one shaped like the cards that will
// replace it -- not a centred "Loading..." line, which reads as an empty state
// and makes the layout jump when content lands.

export const CardSkeleton = ({ lines = 2 }: { lines?: number }) => (
  <div className="skeleton-card">
    <div className="skeleton-card__header">
      <Skeleton variant="text" width="34%" height="13px" />
      <Skeleton variant="rectangular" width="66px" height="18px" />
    </div>
    <Skeleton variant="text" width="92%" height="15px" />
    {Array.from({ length: Math.max(0, lines - 1) }).map((_, i) => (
      <Skeleton key={i} variant="text" width={`${78 - i * 12}%`} height="13px" />
    ))}
  </div>
);

interface ListSkeletonProps {
  /** How many placeholder cards to draw. Match the page size you request. */
  count?: number;
  lines?: number;
  /** Announced to screen readers in place of the visual shimmer. */
  label?: string;
}

export const ListSkeleton = ({ count = 4, lines = 2, label }: ListSkeletonProps) => {
  const { t } = useTranslation();
  return (
    <div
      className="skeleton-list"
      role="status"
      aria-busy="true"
      aria-label={label || t('common.loading', 'Loading…')}
    >
      {Array.from({ length: count }).map((_, i) => (
        <CardSkeleton key={i} lines={lines} />
      ))}
    </div>
  );
};

export const RowSkeleton = ({ count = 3 }: { count?: number }) => {
  const { t } = useTranslation();
  return (
    <div className="skeleton-rows" role="status" aria-busy="true" aria-label={t('common.loading', 'Loading…')}>
      {Array.from({ length: count }).map((_, i) => (
        <div className="skeleton-rows__row" key={i}>
          <Skeleton variant="text" width="6.5rem" height="13px" />
          <Skeleton variant="text" width={`${70 - i * 8}%`} height="13px" />
        </div>
      ))}
    </div>
  );
};

/**
 * For work that is computed rather than listed -- building a graph, running an
 * analysis -- where a card-shaped placeholder would be a lie about what is
 * coming. Keeps the explanatory message, adds motion so a long wait does not
 * read as a freeze, and announces itself.
 */
export const PendingNote = ({ message }: { message: string }) => (
  <div className="skeleton-pending" role="status" aria-busy="true">
    <span className="skeleton-pending__dots" aria-hidden="true">
      <i /><i /><i />
    </span>
    <span className="skeleton-pending__label">{message}</span>
  </div>
);
