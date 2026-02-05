import { Wallet, ExternalLink, TrendingUp } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { EU_FUNDING_PROGRAMS } from '@/data/startupFallback';
import type { EUFundingProgram } from '@/types/startup';

interface EUFundingProgramsProps {
  programs?: EUFundingProgram[];
  className?: string;
}

function ProgramCard({ program }: { program: EUFundingProgram }) {
  return (
    <div className="bg-muted/30 rounded-lg p-4 border border-border/50 hover:border-primary/30 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-secondary">{program.name}</h3>
          <p className="text-xs text-muted-foreground">{program.description}</p>
        </div>
        <div className="text-right">
          <div className="text-lg font-bold text-primary">{program.totalBudget}</div>
          <div className="text-[10px] text-muted-foreground">Total Budget</div>
        </div>
      </div>

      {program.subPrograms && (
        <div className="space-y-2 mb-3">
          {program.subPrograms.map((sub) => (
            <div key={sub.name} className="flex justify-between items-center text-sm">
              <span className="text-muted-foreground">{sub.name}</span>
              <span className="font-medium text-secondary">{sub.budget}</span>
            </div>
          ))}
        </div>
      )}

      {program.stats && (
        <div className="grid grid-cols-3 gap-2 pt-3 border-t border-border/50">
          {program.stats.map((stat) => (
            <div key={stat.label} className="text-center">
              <div className="text-sm font-bold text-primary">{stat.value}</div>
              <div className="text-[10px] text-muted-foreground">{stat.label}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function EUFundingPrograms({
  programs = EU_FUNDING_PROGRAMS,
  className = '',
}: EUFundingProgramsProps) {
  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Wallet className="w-5 h-5 text-secondary" />
            <CardTitle className="text-xl text-secondary">EU Public Funding Landscape</CardTitle>
          </div>
          <a
            href="https://eic.ec.europa.eu/"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-primary hover:underline"
          >
            EIC Portal <ExternalLink className="w-3 h-3" />
          </a>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Major EU instruments supporting startups and scale-ups
        </p>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {programs.map((program) => (
            <ProgramCard key={program.name} program={program} />
          ))}
        </div>

        {/* Summary stats */}
        <div className="mt-6 p-4 bg-primary/5 rounded-lg border border-primary/20">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-primary" />
            <span className="font-medium text-secondary">TechEU 2025-2027 Target</span>
          </div>
          <p className="text-sm text-muted-foreground">
            The EIB Group aims to mobilise <strong className="text-primary">$250B</strong> in
            tech financing over 3 years through direct lending, equity investment, and
            guarantees across the European tech ecosystem.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
