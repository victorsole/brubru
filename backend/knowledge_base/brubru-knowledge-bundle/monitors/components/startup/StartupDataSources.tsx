import { ExternalLink } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { DATA_SOURCES } from '@/data/startupFallback';
import type { DataSource } from '@/types/startup';

interface StartupDataSourcesProps {
  sources?: DataSource[];
  className?: string;
}

function SourceCard({ source }: { source: DataSource }) {
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className="bg-muted/30 rounded-lg p-3 text-center hover:border-primary/30 border border-transparent transition-colors group"
    >
      <div className="text-xs font-medium text-secondary mb-1 group-hover:text-primary transition-colors">
        {source.name}
      </div>
      <div className="text-[10px] text-muted-foreground">{source.description}</div>
    </a>
  );
}

export function StartupDataSources({
  sources = DATA_SOURCES,
  className = '',
}: StartupDataSourcesProps) {
  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg text-secondary">
          Data Sources ({sources.length})
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-4 sm:grid-cols-6 gap-3">
          {sources.map((source) => (
            <SourceCard key={source.name} source={source} />
          ))}
        </div>
        <div className="mt-6 pt-4 border-t border-border/50 flex items-center justify-between text-xs text-muted-foreground">
          <div>
            <span className="font-medium text-secondary">beresol</span> EU Advocacy Hub -
            Startup Monitor
          </div>
          <div className="flex items-center gap-1">
            Last updated: January 2026
            <ExternalLink className="w-3 h-3" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
