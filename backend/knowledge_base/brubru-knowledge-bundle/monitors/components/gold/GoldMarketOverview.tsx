import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { GOLD_METRICS } from '@/data/goldFallback';
import type { GoldMetrics } from '@/types/gold';

interface GoldMarketOverviewProps {
  metrics?: GoldMetrics;
  className?: string;
}

export function GoldMarketOverview({
  metrics = GOLD_METRICS,
  className = '',
}: GoldMarketOverviewProps) {
  const stats = [
    { label: 'Global Demand (2024)', value: metrics.globalDemand },
    { label: 'Mine Production', value: metrics.mineProduction },
    { label: 'ETF Holdings', value: metrics.etfHoldings },
    { label: 'Tokenised Gold Cap', value: metrics.tokenisedGoldCap },
    { label: 'COMEX Open Interest', value: metrics.comexOpenInterest },
  ];

  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg text-secondary">Market Overview</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {stats.map((stat) => (
            <div
              key={stat.label}
              className="flex items-center justify-between p-3 rounded-lg bg-muted/30"
            >
              <span className="text-sm text-muted-foreground">{stat.label}</span>
              <span className="text-sm font-semibold text-secondary">{stat.value}</span>
            </div>
          ))}
        </div>
        <div className="mt-4 p-3 bg-amber-50 rounded-lg border border-amber-200">
          <p className="text-xs text-amber-700">
            <strong>Analyst Target:</strong> Morgan Stanley forecasts $2,800/oz by Q4 2025
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
