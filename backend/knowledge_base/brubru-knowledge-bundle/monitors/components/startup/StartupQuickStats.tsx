import { TrendingUp, TrendingDown, Rocket, Briefcase, Cpu, Shield, DollarSign } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { STARTUP_METRICS } from '@/data/startupFallback';
import type { StartupMetrics } from '@/types/startup';

interface StartupQuickStatsProps {
  metrics?: StartupMetrics;
  className?: string;
}

interface StatItem {
  label: string;
  value: string;
  change?: string;
  positive?: boolean;
  icon: React.ReactNode;
}

export function StartupQuickStats({
  metrics = STARTUP_METRICS,
  className = '',
}: StartupQuickStatsProps) {
  const stats: StatItem[] = [
    {
      label: 'DeepTech Share of Funding',
      value: metrics.deeptechShare,
      icon: <Cpu className="w-4 h-4 text-purple-500" />,
    },
    {
      label: 'Defence Tech (2025)',
      value: metrics.defenceTech2025,
      change: metrics.defenceTechChange,
      positive: true,
      icon: <Shield className="w-4 h-4 text-blue-500" />,
    },
    {
      label: 'Tech Share of GDP',
      value: metrics.techGdpShare,
      icon: <Briefcase className="w-4 h-4 text-primary" />,
    },
    {
      label: 'New Founders (2025)',
      value: metrics.newFounders2025,
      icon: <Rocket className="w-4 h-4 text-amber-500" />,
    },
    {
      label: 'EU Median IPO',
      value: metrics.euIpoMedian,
      icon: <DollarSign className="w-4 h-4 text-red-500" />,
    },
    {
      label: 'US Median IPO',
      value: metrics.usIpoMedian,
      icon: <DollarSign className="w-4 h-4 text-green-500" />,
    },
  ];

  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg text-secondary">Quick Stats</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {stats.map((stat) => (
            <div
              key={stat.label}
              className="flex items-center justify-between p-2 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors"
            >
              <div className="flex items-center gap-2">
                {stat.icon}
                <span className="text-sm text-muted-foreground">{stat.label}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-secondary">{stat.value}</span>
                {stat.change && (
                  <span className={`text-xs font-medium flex items-center gap-0.5 ${
                    stat.positive ? 'text-green-600' : 'text-red-500'
                  }`}>
                    {stat.positive ? (
                      <TrendingUp className="w-3 h-3" />
                    ) : (
                      <TrendingDown className="w-3 h-3" />
                    )}
                    {stat.change}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* IPO Gap highlight */}
        <div className="mt-4 p-3 bg-red-50 rounded-lg border border-red-100">
          <div className="flex items-center gap-2 mb-1">
            <TrendingDown className="w-4 h-4 text-red-500" />
            <span className="text-sm font-medium text-red-700">IPO Value Gap</span>
          </div>
          <p className="text-xs text-red-600">
            US IPO median is <strong>13.7x larger</strong> than EU median,
            indicating the scale disadvantage European companies face at exit.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
