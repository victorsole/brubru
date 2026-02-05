import { PieChart } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { SourceBadges } from './SourceBadge';
import { FALLBACK_QUICK_STATS } from '@/data/cmuFallback';
import type { QuickStat } from '@/types/cmu';

interface QuickStatsProps {
  stats?: QuickStat[];
  isLoading?: boolean;
}

export function QuickStats({ stats = FALLBACK_QUICK_STATS, isLoading = false }: QuickStatsProps) {
  const getValueColor = (color?: QuickStat['color']) => {
    switch (color) {
      case 'destructive':
        return 'text-destructive';
      case 'accent':
        return 'text-accent';
      default:
        return 'text-secondary';
    }
  };

  // Collect all unique sources from stats
  const allSources = [...new Set(stats.flatMap((s) => s.sources))];

  return (
    <Card className="border-border/50 h-[320px] flex flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <PieChart className="w-5 h-5 text-secondary" />
          <CardTitle className="text-lg text-secondary">Quick Stats</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col justify-between">
        <div className="space-y-4">
          {stats.map((stat, index) => (
            <div key={index} className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">{stat.label}</span>
              <span className={`text-sm font-medium ${getValueColor(stat.color)}`}>
                {isLoading ? '...' : stat.value}
              </span>
            </div>
          ))}
        </div>

        <div className="pt-3 border-t border-border/50">
          <SourceBadges sources={allSources} size="sm" />
        </div>
      </CardContent>
    </Card>
  );
}
