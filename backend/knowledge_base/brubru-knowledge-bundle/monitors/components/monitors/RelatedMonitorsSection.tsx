import { Link } from 'react-router-dom';
import { ArrowRight, Compass } from 'lucide-react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { getRelatedMonitors, type MonitorId } from '@/data/monitorRelationships';

interface RelatedMonitorsSectionProps {
  currentMonitor: MonitorId;
  className?: string;
}

const strengthBadge = {
  high: 'bg-green-100 text-green-700 border-green-200',
  medium: 'bg-amber-100 text-amber-700 border-amber-200',
  low: 'bg-gray-100 text-gray-600 border-gray-200',
};

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.1 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

export function RelatedMonitorsSection({
  currentMonitor,
  className = '',
}: RelatedMonitorsSectionProps) {
  const relatedMonitors = getRelatedMonitors(currentMonitor, 3);

  if (relatedMonitors.length === 0) return null;

  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Compass className="w-5 h-5 text-primary" />
          <CardTitle className="text-lg text-secondary">Related Intelligence</CardTitle>
        </div>
        <p className="text-sm text-muted-foreground">
          Explore connected policy areas and market intelligence
        </p>
      </CardHeader>
      <CardContent>
        <motion.div
          className="grid grid-cols-1 md:grid-cols-3 gap-4"
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
        >
          {relatedMonitors.map(({ monitor, reason, strength }) => {
            const IconComponent = monitor.icon;
            return (
              <motion.div key={monitor.id} variants={itemVariants}>
                <Link
                  to={monitor.path}
                  className={`block h-full p-4 rounded-lg border ${monitor.colourClasses.border} ${monitor.colourClasses.bg} hover:shadow-md transition-all group`}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className={`w-10 h-10 rounded-lg ${monitor.colourClasses.bg} border ${monitor.colourClasses.border} flex items-center justify-center`}>
                      <IconComponent className={`w-5 h-5 ${monitor.colourClasses.text}`} />
                    </div>
                    <span className={`px-2 py-0.5 text-xs rounded-full border ${strengthBadge[strength]}`}>
                      {strength === 'high' ? 'Strong' : strength === 'medium' ? 'Related' : 'Connected'}
                    </span>
                  </div>
                  <h4 className="font-semibold text-secondary mb-1 group-hover:text-primary transition-colors">
                    {monitor.name}
                  </h4>
                  <p className="text-xs text-muted-foreground mb-3 line-clamp-2">
                    {reason}
                  </p>
                  <div className={`flex items-center gap-1 text-xs font-medium ${monitor.colourClasses.text}`}>
                    Explore <ArrowRight className="w-3 h-3 group-hover:translate-x-1 transition-transform" />
                  </div>
                </Link>
              </motion.div>
            );
          })}
        </motion.div>
      </CardContent>
    </Card>
  );
}
