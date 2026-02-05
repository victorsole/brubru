import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { LucideIcon } from "lucide-react";

interface MetricCardProps {
  icon: LucideIcon;
  value: string | number;
  label: string;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  color?: 'primary' | 'secondary' | 'accent';
}

export function MetricCard({ icon: Icon, value, label, trend, color = 'primary' }: MetricCardProps) {
  const colorClasses = {
    primary: 'text-primary',
    secondary: 'text-secondary',
    accent: 'text-accent',
  };

  return (
    <Card className="group hover:shadow-strong transition-all duration-300 hover:-translate-y-2 border-border/50">
      <CardHeader className="text-center pb-2">
        <div className={`mx-auto w-16 h-16 rounded-full bg-muted/50 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform ${colorClasses[color]}`}>
          <Icon className="w-8 h-8" />
        </div>
        <CardTitle className="text-3xl font-bold text-secondary">
          {value}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <CardDescription className="text-center text-muted-foreground">
          {label}
        </CardDescription>
        {trend && (
          <p className={`text-center text-sm mt-2 font-medium ${
            trend.isPositive ? 'text-primary' : 'text-destructive'
          }`}>
            {trend.isPositive ? '+' : ''}{trend.value}% YoY
          </p>
        )}
      </CardContent>
    </Card>
  );
}
