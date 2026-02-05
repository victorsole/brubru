import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { GOLD_DATA_SOURCES } from '@/data/goldFallback';
import type { GoldDataSource } from '@/types/gold';

interface GoldDataSourcesProps {
  sources?: GoldDataSource[];
  className?: string;
}

export function GoldDataSources({
  sources = GOLD_DATA_SOURCES,
  className = '',
}: GoldDataSourcesProps) {
  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg text-secondary">Data Sources ({sources.length})</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-4 md:grid-cols-8 gap-3">
          {sources.map((source) => (
            <a
              key={source.name}
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="p-3 text-center bg-muted/30 rounded-lg hover:border-primary/30 border border-transparent transition-colors group"
            >
              <div className="text-xs font-medium text-secondary group-hover:text-primary transition-colors">
                {source.name}
              </div>
              <div className="text-[10px] text-muted-foreground">{source.description}</div>
            </a>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
