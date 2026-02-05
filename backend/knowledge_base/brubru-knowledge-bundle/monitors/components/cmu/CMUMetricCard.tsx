import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { LucideIcon } from 'lucide-react';
import { SourceBadges } from './SourceBadge';
import type { DataSource } from '@/types/cmu';

interface CMUMetricCardProps {
  icon: LucideIcon;
  value: string | number;
  label: string;
  trend?: string;
  sources?: DataSource[];
  color?: 'primary' | 'secondary' | 'accent';
}

export function CMUMetricCard({
  icon: Icon,
  value,
  label,
  trend,
  sources,
  color = 'primary',
}: CMUMetricCardProps) {
  const colorClasses = {
    primary: 'text-primary',
    secondary: 'text-secondary',
    accent: 'text-accent',
  };

  return (
    <Card className="group hover:shadow-strong transition-all duration-300 hover:-translate-y-2 border-border/50 h-full flex flex-col">
      <CardHeader className="text-center pb-2 flex-1 flex flex-col justify-center">
        <div
          className={`mx-auto w-16 h-16 rounded-full bg-muted/50 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform ${colorClasses[color]}`}
        >
          <Icon className="w-8 h-8" />
        </div>
        <CardTitle className="text-3xl font-bold text-secondary">{value}</CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <CardDescription className="text-center text-muted-foreground min-h-[40px] flex items-center justify-center">{label}</CardDescription>
        <div className="min-h-[24px]">
          {trend && (
            <p className="text-center text-sm font-medium text-muted-foreground">{trend}</p>
          )}
        </div>
        <div className="flex justify-center mt-2 min-h-[24px]">
          {sources && sources.length > 0 && (
            <SourceBadges sources={sources} size="sm" />
          )}
        </div>
      </CardContent>
    </Card>
  );
}
