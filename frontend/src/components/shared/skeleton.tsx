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
