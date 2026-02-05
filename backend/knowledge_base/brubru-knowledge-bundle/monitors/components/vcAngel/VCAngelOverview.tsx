import { TrendingUp, TrendingDown, Building2, Landmark } from 'lucide-react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { VC_MARKET_METRICS } from '@/data/vcAngelFallback';
import type { VCMarketMetrics } from '@/types/vcAngel';

interface VCAngelOverviewProps {
  metrics?: VCMarketMetrics;
  className?: string;
}

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

export function VCAngelOverview({
  metrics = VC_MARKET_METRICS,
  className = '',
}: VCAngelOverviewProps) {
  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-primary" />
          <CardTitle className="text-xl text-secondary">EU VC Market Position</CardTitle>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Europe's structural funding gap vs global competitors
        </p>
      </CardHeader>
      <CardContent>
        <motion.div
          className="grid grid-cols-2 md:grid-cols-4 gap-4"
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
        >
          {/* Global VC Share */}
          <motion.div
            variants={itemVariants}
            className="p-4 rounded-lg bg-red-50 border border-red-100"
          >
            <div className="flex items-center gap-2 mb-2">
              <TrendingDown className="w-4 h-4 text-red-500" />
              <span className="text-xs font-medium text-red-600">Global VC Share</span>
            </div>
            <div className="space-y-1">
              <div className="flex justify-between items-baseline">
                <span className="text-2xl font-bold text-red-600">{metrics.euGlobalShare}</span>
                <span className="text-xs text-muted-foreground">EU</span>
              </div>
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>US: {metrics.usGlobalShare}</span>
                <span>CN: {metrics.chinaGlobalShare}</span>
              </div>
            </div>
          </motion.div>

          {/* Average Fund Size */}
          <motion.div
            variants={itemVariants}
            className="p-4 rounded-lg bg-amber-50 border border-amber-100"
          >
            <div className="flex items-center gap-2 mb-2">
              <Building2 className="w-4 h-4 text-amber-600" />
              <span className="text-xs font-medium text-amber-700">Avg Fund Size</span>
            </div>
            <div className="space-y-1">
              <div className="flex justify-between items-baseline">
                <span className="text-2xl font-bold text-amber-700">{metrics.euAvgFundSize}</span>
                <span className="text-xs text-muted-foreground">EU</span>
              </div>
              <div className="text-xs text-muted-foreground">
                US: {metrics.usAvgFundSize}
              </div>
            </div>
          </motion.div>

          {/* Unicorns */}
          <motion.div
            variants={itemVariants}
            className="p-4 rounded-lg bg-purple-50 border border-purple-100"
          >
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-4 h-4 text-purple-600" />
              <span className="text-xs font-medium text-purple-700">Unicorns (Jan 2025)</span>
            </div>
            <div className="space-y-1">
              <div className="flex justify-between items-baseline">
                <span className="text-2xl font-bold text-purple-700">{metrics.euUnicorns}</span>
                <span className="text-xs text-muted-foreground">EU</span>
              </div>
              <div className="text-xs text-muted-foreground">
                US: {metrics.usUnicorns}
              </div>
            </div>
          </motion.div>

          {/* Pension Fund Contribution */}
          <motion.div
            variants={itemVariants}
            className="p-4 rounded-lg bg-blue-50 border border-blue-100"
          >
            <div className="flex items-center gap-2 mb-2">
              <Landmark className="w-4 h-4 text-blue-600" />
              <span className="text-xs font-medium text-blue-700">Pension Fund %</span>
            </div>
            <div className="space-y-1">
              <div className="flex justify-between items-baseline">
                <span className="text-2xl font-bold text-blue-700">{metrics.euPensionFundShare}</span>
                <span className="text-xs text-muted-foreground">EU</span>
              </div>
              <div className="text-xs text-muted-foreground">
                US: {metrics.usPensionFundShare}
              </div>
            </div>
          </motion.div>
        </motion.div>

        <div className="mt-4 p-3 bg-muted/30 rounded-lg">
          <p className="text-xs text-muted-foreground">
            <strong className="text-secondary">Policy context:</strong> The Commission's SIU initiative explicitly targets closing these gaps through EuVECA reforms,
            ELTIF 2.0 expansion, and the €5B Scaleup Europe Fund.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
