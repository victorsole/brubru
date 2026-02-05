import { Gauge, Users, TrendingUp, Globe, Shield } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { SourceBadges } from './SourceBadge';
import { FALLBACK_SIU_PILLARS, FALLBACK_METRICS } from '@/data/cmuFallback';
import type { SIUPillar } from '@/types/cmu';

interface CMUProgressIndexProps {
  progress?: number;
  pillars?: SIUPillar[];
  isLoading?: boolean;
}

const PILLAR_ICONS = {
  citizens_savings: Users,
  investment_financing: TrendingUp,
  integration_scale: Globe,
  supervision: Shield,
};

function PillarCard({ pillar }: { pillar: SIUPillar }) {
  const Icon = PILLAR_ICONS[pillar.id];
  const colorClasses =
    pillar.color === 'primary'
      ? 'bg-primary/5 border-primary/20 text-primary'
      : 'bg-accent/5 border-accent/20 text-accent';

  const barColor = pillar.color === 'primary' ? 'bg-primary' : 'bg-accent';
  const textColor = pillar.color === 'primary' ? 'text-primary' : 'text-accent';

  return (
    <div className={`p-4 rounded-lg border ${colorClasses}`}>
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-4 h-4" />
        <span className="text-sm font-medium text-secondary">{pillar.name}</span>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex-1 h-2 rounded-full bg-border">
          <div
            className={`h-full rounded-full ${barColor}`}
            style={{ width: `${pillar.progress}%` }}
          />
        </div>
        <span className={`text-sm font-medium ${textColor}`}>{pillar.progress}%</span>
      </div>
    </div>
  );
}

export function CMUProgressIndex({
  progress = FALLBACK_METRICS.overallProgress,
  pillars = FALLBACK_SIU_PILLARS,
  isLoading = false,
}: CMUProgressIndexProps) {
  // Calculate stroke offset for the progress ring
  const circumference = 2 * Math.PI * 40; // r=40
  const strokeOffset = circumference - (progress / 100) * circumference;

  return (
    <Card className="border-border/50 h-[320px]">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Gauge className="w-5 h-5 text-secondary" />
            <CardTitle className="text-xl text-secondary">CMU/SIU Progress Index</CardTitle>
          </div>
          <SourceBadges sources={['european_commission', 'ecb', 'eur_lex']} size="sm" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-8">
          {/* Main Gauge */}
          <div className="relative flex-shrink-0">
            <svg className="w-44 h-44" viewBox="0 0 100 100">
              {/* Background circle */}
              <circle
                cx="50"
                cy="50"
                r="40"
                fill="none"
                stroke="hsl(120 20% 88%)"
                strokeWidth="8"
              />
              {/* Progress circle */}
              <circle
                cx="50"
                cy="50"
                r="40"
                fill="none"
                stroke="url(#beresol-gradient)"
                strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={circumference}
                strokeDashoffset={strokeOffset}
                className="transition-all duration-1000 ease-out"
                style={{ transform: 'rotate(-90deg)', transformOrigin: 'center' }}
              />
              <defs>
                <linearGradient id="beresol-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="hsl(120 65% 45%)" />
                  <stop offset="100%" stopColor="hsl(45 85% 50%)" />
                </linearGradient>
              </defs>
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-4xl font-bold text-secondary">
                {isLoading ? '...' : `${progress}%`}
              </span>
              <span className="text-xs text-muted-foreground">Overall Progress</span>
            </div>
          </div>

          {/* Pillar breakdown */}
          <div className="flex-1 grid grid-cols-2 gap-4">
            {pillars.map((pillar) => (
              <PillarCard key={pillar.id} pillar={pillar} />
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
