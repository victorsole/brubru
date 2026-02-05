import { LucideIcon } from 'lucide-react';

interface StartupMetricCardProps {
  icon: LucideIcon;
  value: string;
  label: string;
  trend?: string;
  trendPositive?: boolean;
  sources?: string[];
  color?: 'primary' | 'accent' | 'blue' | 'purple';
}

const colorClasses = {
  primary: 'bg-primary/10 text-primary',
  accent: 'bg-amber-500/10 text-amber-500',
  blue: 'bg-blue-500/10 text-blue-500',
  purple: 'bg-purple-500/10 text-purple-500',
};

export function StartupMetricCard({
  icon: Icon,
  value,
  label,
  trend,
  trendPositive = true,
  sources = [],
  color = 'primary',
}: StartupMetricCardProps) {
  return (
    <div className="bg-white rounded-xl p-6 border border-border/50 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 h-full flex flex-col">
      <div className="flex items-center gap-3 mb-3 flex-1">
        <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${colorClasses[color]}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <p className="text-3xl font-bold text-secondary">{value}</p>
          <p className="text-sm text-muted-foreground">{label}</p>
        </div>
      </div>
      <div className="min-h-[16px]">
        {trend && (
          <p className={`text-xs font-medium ${trendPositive ? 'text-green-600' : 'text-red-500'}`}>
            {trend}
          </p>
        )}
      </div>
      <div className="flex gap-1 flex-wrap mt-2 min-h-[20px]">
        {sources.map((source) => (
          <span
            key={source}
            className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground"
          >
            {source}
          </span>
        ))}
      </div>
    </div>
  );
}
