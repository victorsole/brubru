import { LucideIcon, TrendingUp, TrendingDown } from 'lucide-react';

interface GoldMetricCardProps {
  icon: LucideIcon;
  value: string;
  label: string;
  trend?: string;
  trendPositive?: boolean;
  source?: string;
  color?: 'gold' | 'blue' | 'purple' | 'green';
}

const colorClasses = {
  gold: 'bg-gradient-to-br from-amber-400 to-amber-600',
  blue: 'bg-blue-500/10 text-blue-600',
  purple: 'bg-purple-500/10 text-purple-600',
  green: 'bg-green-500/10 text-green-600',
};

const iconColorClasses = {
  gold: 'text-amber-900',
  blue: 'text-blue-600',
  purple: 'text-purple-600',
  green: 'text-green-600',
};

export function GoldMetricCard({
  icon: Icon,
  value,
  label,
  trend,
  trendPositive = true,
  source,
  color = 'gold',
}: GoldMetricCardProps) {
  return (
    <div className="bg-white rounded-xl p-6 border border-border/50 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300">
      <div className="flex items-center gap-3 mb-3">
        <div className={`w-12 h-12 rounded-full flex items-center justify-center ${colorClasses[color]}`}>
          <Icon className={`w-6 h-6 ${color === 'gold' ? iconColorClasses.gold : ''}`} />
        </div>
        <div>
          <p className="text-3xl font-bold text-secondary">{value}</p>
          <p className="text-sm text-muted-foreground">{label}</p>
        </div>
      </div>
      <div className="flex items-center justify-between">
        {trend && (
          <span className={`text-xs font-medium flex items-center gap-1 ${trendPositive ? 'text-green-600' : 'text-red-500'}`}>
            {trendPositive ? (
              <TrendingUp className="w-3 h-3" />
            ) : (
              <TrendingDown className="w-3 h-3" />
            )}
            {trend}
          </span>
        )}
        {source && (
          <span className="text-[10px] px-2 py-0.5 rounded bg-muted text-muted-foreground">
            {source}
          </span>
        )}
      </div>
    </div>
  );
}
