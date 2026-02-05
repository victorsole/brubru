import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  DATA_SOURCE_FULL_NAMES,
  DATA_SOURCE_TYPES,
  type DataSource,
} from '@/types/cmu';

interface DataSourcesGridProps {
  className?: string;
}

const ALL_SOURCES: DataSource[] = [
  'european_commission',
  'eur_lex',
  'ecb',
  'esma',
  'eba',
  'eiopa',
  'eprs',
  'jrc',
  'eib',
  'eca',
  'bruegel',
  'letta_report',
  'draghi_report',
  'web_search',
];

function SourceCard({ source }: { source: DataSource }) {
  const name = DATA_SOURCE_FULL_NAMES[source];
  const type = DATA_SOURCE_TYPES[source];

  return (
    <div className="bg-muted/30 rounded-lg p-3 text-center hover:border-primary/30 border border-transparent transition cursor-pointer">
      <div className="text-xs font-medium text-secondary mb-1">{name}</div>
      <div className="text-[10px] text-muted-foreground">{type}</div>
    </div>
  );
}

export function DataSourcesGrid({ className = '' }: DataSourcesGridProps) {
  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg text-secondary">
          Data Sources ({ALL_SOURCES.length})
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-7 gap-3">
          {ALL_SOURCES.map((source) => (
            <SourceCard key={source} source={source} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
