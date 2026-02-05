import { TrendingUp, BarChart2 } from 'lucide-react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ELTIF_GROWTH_DATA } from '@/data/vcAngelFallback';
import type { ELTIFDataPoint } from '@/types/vcAngel';

interface ELTIFGrowthChartProps {
  data?: ELTIFDataPoint[];
  className?: string;
}

export function ELTIFGrowthChart({
  data = ELTIF_GROWTH_DATA,
  className = '',
}: ELTIFGrowthChartProps) {
  const maxAum = Math.max(...data.map(d => d.aumBillions));
  const maxFunds = Math.max(...data.map(d => d.fundsMarketed));

  // Calculate growth rates
  const aumGrowth = data.length >= 2
    ? (((data[data.length - 1].aumBillions - data[0].aumBillions) / data[0].aumBillions) * 100).toFixed(0)
    : '0';
  const fundsGrowth = data.length >= 2
    ? (((data[data.length - 1].fundsMarketed - data[0].fundsMarketed) / data[0].fundsMarketed) * 100).toFixed(0)
    : '0';

  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart2 className="w-5 h-5 text-primary" />
            <CardTitle className="text-xl text-secondary">ELTIF 2.0 Market Growth</CardTitle>
          </div>
          <div className="flex items-center gap-1 text-green-600 text-sm">
            <TrendingUp className="w-4 h-4" />
            <span className="font-semibold">+{aumGrowth}% AuM since 2023</span>
          </div>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Retail-accessible long-term investment funds growth since ELTIF 2.0
        </p>
      </CardHeader>
      <CardContent>
        <div className="space-y-6">
          {/* Bar Chart */}
          <div className="flex items-end justify-between gap-4 h-40">
            {data.map((point, index) => (
              <motion.div
                key={point.year}
                initial={{ opacity: 0, scaleY: 0 }}
                animate={{ opacity: 1, scaleY: 1 }}
                transition={{ delay: index * 0.2, duration: 0.5 }}
                className="flex-1 flex flex-col items-center"
                style={{ transformOrigin: 'bottom' }}
              >
                {/* AuM Bar */}
                <div className="w-full flex flex-col items-center gap-1">
                  <span className="text-xs font-semibold text-primary">
                    €{point.aumBillions}B
                  </span>
                  <div
                    className="w-full bg-gradient-to-t from-primary to-primary/60 rounded-t-md transition-all"
                    style={{
                      height: `${(point.aumBillions / maxAum) * 100}px`,
                      minHeight: '20px',
                    }}
                  />
                </div>
                {/* Year Label */}
                <div className="mt-2 text-center">
                  <span className="text-sm font-medium text-secondary">{point.year}</span>
                  <div className="text-xs text-muted-foreground">{point.fundsMarketed} funds</div>
                </div>
              </motion.div>
            ))}
          </div>

          {/* Stats Summary */}
          <div className="grid grid-cols-3 gap-4 pt-4 border-t border-border/50">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6 }}
              className="text-center p-3 bg-primary/5 rounded-lg"
            >
              <p className="text-2xl font-bold text-primary">{data[data.length - 1].fundsMarketed}</p>
              <p className="text-xs text-muted-foreground">Funds Marketed</p>
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.7 }}
              className="text-center p-3 bg-green-50 rounded-lg"
            >
              <p className="text-2xl font-bold text-green-600">€{data[data.length - 1].aumBillions}B</p>
              <p className="text-xs text-muted-foreground">Total AuM</p>
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.8 }}
              className="text-center p-3 bg-purple-50 rounded-lg"
            >
              <p className="text-2xl font-bold text-purple-600">+{fundsGrowth}%</p>
              <p className="text-xs text-muted-foreground">Fund Growth</p>
            </motion.div>
          </div>

          {/* Note */}
          <div className="p-3 bg-blue-50 rounded-lg border border-blue-100">
            <p className="text-xs text-blue-700">
              <strong>Key insight:</strong> Luxembourg dominates with 98 of 150 authorised ELTIFs.
              Two-thirds are now accessible to retail investors following ELTIF 2.0 reforms.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
