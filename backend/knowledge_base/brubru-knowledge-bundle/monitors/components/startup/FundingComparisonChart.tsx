import { BarChart3 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { FUNDING_COMPARISONS } from '@/data/startupFallback';
import type { FundingComparison } from '@/types/startup';

interface FundingComparisonChartProps {
  data?: FundingComparison[];
  className?: string;
}

function ComparisonBar({ item }: { item: FundingComparison }) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between items-baseline">
        <span className="text-sm font-medium text-secondary">{item.metric}</span>
        <span className="text-xs font-bold text-red-500">{item.gap} gap</span>
      </div>
      <div className="flex gap-2 items-center">
        <div className="flex-1">
          <div className="flex justify-between text-xs mb-1">
            <span className="text-muted-foreground">EU</span>
            <span className="font-medium text-primary">{item.euValue}</span>
          </div>
          <div className="h-3 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary rounded-full transition-all duration-500"
              style={{ width: `${item.percentage}%` }}
            />
          </div>
        </div>
        <div className="flex-1">
          <div className="flex justify-between text-xs mb-1">
            <span className="text-muted-foreground">US</span>
            <span className="font-medium text-amber-500">{item.usValue}</span>
          </div>
          <div className="h-3 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-amber-500 rounded-full"
              style={{ width: '100%' }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export function FundingComparisonChart({
  data = FUNDING_COMPARISONS,
  className = '',
}: FundingComparisonChartProps) {
  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-secondary" />
          <CardTitle className="text-xl text-secondary">EU vs US Funding Gap</CardTitle>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          The transatlantic venture capital divide remains substantial
        </p>
      </CardHeader>
      <CardContent>
        <div className="space-y-6">
          {data.map((item) => (
            <ComparisonBar key={item.metric} item={item} />
          ))}
        </div>

        {/* Legend */}
        <div className="flex justify-center gap-8 mt-6 pt-4 border-t border-border/50">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-primary" />
            <span className="text-sm text-muted-foreground">European Union</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-amber-500" />
            <span className="text-sm text-muted-foreground">United States</span>
          </div>
        </div>

        {/* Key insight */}
        <div className="mt-4 p-3 bg-red-50 rounded-lg border border-red-100">
          <p className="text-xs text-red-700">
            <strong>Key insight:</strong> AI funding gap is 10.4x - the largest disparity.
            EU captured just 9.6% of US AI investment in 2024.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
