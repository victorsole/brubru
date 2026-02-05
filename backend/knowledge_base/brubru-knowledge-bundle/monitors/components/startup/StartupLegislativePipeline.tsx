import { useState } from 'react';
import { Scale, ExternalLink, HelpCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  LEGISLATION_IN_FORCE,
  LEGISLATION_PROPOSED,
  LEGISLATION_UPCOMING,
  LEGISLATION_RUMOURED,
} from '@/data/startupFallback';
import type { StartupLegislation, LegislationStatus } from '@/types/startup';

interface ColumnConfig {
  status: LegislationStatus;
  label: string;
  borderColor: string;
  dotColor: string;
  textColor: string;
  bgColor: string;
  items: StartupLegislation[];
}

const getColumns = (): ColumnConfig[] => [
  {
    status: 'in_force',
    label: 'In Force',
    borderColor: 'border-primary',
    dotColor: 'bg-primary',
    textColor: 'text-primary',
    bgColor: 'bg-primary/5',
    items: LEGISLATION_IN_FORCE,
  },
  {
    status: 'proposed',
    label: 'Proposed',
    borderColor: 'border-blue-500/50',
    dotColor: 'bg-blue-500',
    textColor: 'text-blue-600',
    bgColor: 'bg-blue-50',
    items: LEGISLATION_PROPOSED,
  },
  {
    status: 'upcoming',
    label: 'Upcoming',
    borderColor: 'border-amber-500/50',
    dotColor: 'bg-amber-500',
    textColor: 'text-amber-600',
    bgColor: 'bg-amber-50',
    items: LEGISLATION_UPCOMING,
  },
  {
    status: 'rumoured',
    label: 'Rumoured',
    borderColor: 'border-muted-foreground/30',
    dotColor: 'bg-muted-foreground',
    textColor: 'text-muted-foreground',
    bgColor: 'bg-muted/30',
    items: LEGISLATION_RUMOURED,
  },
];

function LegislationCard({ item, config }: { item: StartupLegislation; config: ColumnConfig }) {
  const content = (
    <div className={`rounded-lg p-3 border transition-colors ${config.bgColor} ${
      item.url ? 'cursor-pointer hover:border-primary/30' : ''
    } border-border/50`}>
      <div className="text-sm font-medium text-secondary mb-1">{item.title}</div>
      <div className="text-xs text-muted-foreground mb-2">{item.description}</div>
      <div className="flex items-center justify-between">
        <span className={`text-[10px] px-2 py-0.5 rounded ${config.bgColor} ${config.textColor} font-medium`}>
          {item.timeline}
        </span>
        {item.url && <ExternalLink className="w-3 h-3 text-muted-foreground" />}
      </div>
    </div>
  );

  if (item.url) {
    return (
      <a href={item.url} target="_blank" rel="noopener noreferrer">
        {content}
      </a>
    );
  }

  return content;
}

function PipelineColumn({ config }: { config: ColumnConfig }) {
  return (
    <div className="flex flex-col min-w-[200px]">
      <div className={`flex items-center gap-2 mb-3 pb-2 border-b-2 ${config.borderColor}`}>
        <div className={`w-2 h-2 rounded-full ${config.dotColor}`} />
        <span className={`text-sm font-medium ${config.textColor}`}>{config.label}</span>
        <span className={`ml-auto text-xs px-2 py-0.5 rounded-full ${config.bgColor} ${config.textColor}`}>
          {config.items.length}
        </span>
      </div>
      <div className="space-y-2 flex-1">
        {config.items.map((item) => (
          <LegislationCard key={item.id} item={item} config={config} />
        ))}
      </div>
    </div>
  );
}

interface StartupLegislativePipelineProps {
  className?: string;
}

export function StartupLegislativePipeline({ className = '' }: StartupLegislativePipelineProps) {
  const [helpOpen, setHelpOpen] = useState(false);
  const columns = getColumns();

  return (
    <>
      <Card className={`border-border/50 ${className}`}>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Scale className="w-5 h-5 text-secondary" />
              <CardTitle className="text-xl text-secondary">Startup Legislation Pipeline</CardTitle>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setHelpOpen(true)}
                className="text-muted-foreground hover:text-secondary transition-colors"
              >
                <HelpCircle className="w-4 h-4" />
              </button>
              <a
                href="https://eur-lex.europa.eu/"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-xs text-primary hover:underline"
              >
                EUR-Lex <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {columns.map((config) => (
              <PipelineColumn key={config.status} config={config} />
            ))}
          </div>
        </CardContent>
      </Card>

      <Dialog open={helpOpen} onOpenChange={setHelpOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-secondary">Understanding the Pipeline</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 mt-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <div className="w-2 h-2 rounded-full bg-primary" />
                <span className="font-medium text-secondary">In Force</span>
              </div>
              <p className="text-sm text-muted-foreground">
                Legislation that has been adopted and is currently applicable.
              </p>
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <div className="w-2 h-2 rounded-full bg-blue-500" />
                <span className="font-medium text-secondary">Proposed</span>
              </div>
              <p className="text-sm text-muted-foreground">
                Commission proposals under review by Parliament and Council.
              </p>
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <div className="w-2 h-2 rounded-full bg-amber-500" />
                <span className="font-medium text-secondary">Upcoming</span>
              </div>
              <p className="text-sm text-muted-foreground">
                Announced or expected proposals with tentative timelines.
              </p>
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <div className="w-2 h-2 rounded-full bg-muted-foreground" />
                <span className="font-medium text-secondary">Rumoured</span>
              </div>
              <p className="text-sm text-muted-foreground">
                Potential initiatives mentioned in policy discussions or reports.
              </p>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
