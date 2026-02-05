import { Scale, ExternalLink } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { GOLD_REGULATIONS } from '@/data/goldFallback';
import type { GoldRegulation } from '@/types/gold';

interface GoldRegulationsSectionProps {
  regulations?: GoldRegulation[];
  className?: string;
}

const statusConfig = {
  in_force: {
    bg: 'bg-primary/5',
    border: 'border-primary/30',
    badge: 'bg-primary text-white',
    badgeText: 'In Force',
    linkColor: 'text-primary',
  },
  upcoming: {
    bg: 'bg-amber-50',
    border: 'border-amber-300',
    badge: 'bg-amber-500 text-white',
    badgeText: 'Upcoming',
    linkColor: 'text-amber-600',
  },
  guidance: {
    bg: 'bg-muted/30',
    border: 'border-border',
    badge: 'bg-muted-foreground text-white',
    badgeText: 'Guidance',
    linkColor: 'text-muted-foreground',
  },
};

export function GoldRegulationsSection({
  regulations = GOLD_REGULATIONS,
  className = '',
}: GoldRegulationsSectionProps) {
  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <Scale className="w-5 h-5 text-secondary" />
          <CardTitle className="text-xl text-secondary">EU Regulatory Landscape</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {regulations.map((reg) => {
            const config = statusConfig[reg.status];
            return (
              <div
                key={reg.id}
                className={`p-4 rounded-lg border ${config.bg} ${config.border}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-semibold text-secondary">{reg.title}</span>
                  <span className={`px-2 py-1 rounded text-xs ${config.badge}`}>
                    {reg.deadline || config.badgeText}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mb-2">{reg.description}</p>
                {reg.url && (
                  <a
                    href={reg.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`text-xs ${config.linkColor} hover:underline flex items-center gap-1`}
                  >
                    {reg.id === 'mifid2' || reg.id === 'mica' ? 'EUR-Lex' : reg.id === 'afm-casp' ? 'AFM Website' : 'ESMA Briefing'}
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
