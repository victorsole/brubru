import { Link } from 'react-router-dom';
import { ExternalLink } from 'lucide-react';
import { motion } from 'framer-motion';
import { getPrimaryRelationship, type MonitorId } from '@/data/monitorRelationships';

interface RelatedMonitorBannerProps {
  currentMonitor: MonitorId;
  className?: string;
}

export function RelatedMonitorBanner({
  currentMonitor,
  className = '',
}: RelatedMonitorBannerProps) {
  const relationship = getPrimaryRelationship(currentMonitor);

  if (!relationship) return null;

  const { monitor, reason } = relationship;
  const IconComponent = monitor.icon;

  return (
    <motion.div
      className={`p-4 rounded-lg border ${monitor.colourClasses.bg} ${monitor.colourClasses.border} ${className}`}
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.1 }}
    >
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <IconComponent className={`w-5 h-5 ${monitor.colourClasses.text}`} />
          <div>
            <p className="text-sm font-medium text-secondary">
              Related: {monitor.name}
            </p>
            <p className="text-xs text-muted-foreground">
              {reason}
            </p>
          </div>
        </div>
        <Link
          to={monitor.path}
          className={`inline-flex items-center gap-2 px-4 py-2 ${monitor.colourClasses.text} bg-background rounded-lg text-sm font-medium hover:bg-muted transition-colors border ${monitor.colourClasses.border}`}
        >
          View {monitor.shortName} Monitor <ExternalLink className="w-4 h-4" />
        </Link>
      </div>
    </motion.div>
  );
}
