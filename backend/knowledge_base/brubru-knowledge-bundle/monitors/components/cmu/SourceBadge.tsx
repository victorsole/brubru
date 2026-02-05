import { Badge } from '@/components/ui/badge';
import { DATA_SOURCE_LABELS, type DataSource } from '@/types/cmu';

interface SourceBadgeProps {
  source: DataSource;
  className?: string;
  size?: 'sm' | 'default';
}

export function SourceBadge({ source, className = '', size = 'default' }: SourceBadgeProps) {
  const label = DATA_SOURCE_LABELS[source] || source;
  const sizeClasses = size === 'sm' ? 'text-[9px] px-1.5 py-0' : 'text-[10px] px-2 py-0.5';

  return (
    <Badge
      variant="outline"
      className={`${sizeClasses} font-medium bg-primary/5 text-primary border-primary/20 ${className}`}
    >
      {label}
    </Badge>
  );
}

interface SourceBadgesProps {
  sources: DataSource[];
  className?: string;
  size?: 'sm' | 'default';
}

export function SourceBadges({ sources, className = '', size = 'default' }: SourceBadgesProps) {
  return (
    <div className={`flex gap-1 flex-wrap ${className}`}>
      {sources.map((source) => (
        <SourceBadge key={source} source={source} size={size} />
      ))}
    </div>
  );
}
