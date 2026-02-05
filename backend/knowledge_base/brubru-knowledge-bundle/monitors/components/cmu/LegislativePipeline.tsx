import { useState } from 'react';
import { Scale, ExternalLink, X } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { SourceBadges } from './SourceBadge';
import { FALLBACK_LEGISLATION } from '@/data/cmuFallback';
import { CMU_CATEGORY_LABELS, type CMULegislativeItem, type LegislativeStatus, type CMUCategory } from '@/types/cmu';

interface LegislativePipelineProps {
  legislation?: CMULegislativeItem[];
  isLoading?: boolean;
}

interface ColumnConfig {
  status: LegislativeStatus;
  label: string;
  borderColor: string;
  dotColor: string;
  textColor: string;
}

const COLUMNS: ColumnConfig[] = [
  {
    status: 'proposed',
    label: 'Proposed',
    borderColor: 'border-muted-foreground/30',
    dotColor: 'bg-muted-foreground',
    textColor: 'text-muted-foreground',
  },
  {
    status: 'ep_reading',
    label: 'EP Reading',
    borderColor: 'border-accent/50',
    dotColor: 'bg-accent',
    textColor: 'text-accent',
  },
  {
    status: 'council',
    label: 'Council',
    borderColor: 'border-purple-500/50',
    dotColor: 'bg-purple-500',
    textColor: 'text-purple-600',
  },
  {
    status: 'adopted',
    label: 'Adopted',
    borderColor: 'border-primary/50',
    dotColor: 'bg-primary',
    textColor: 'text-primary',
  },
  {
    status: 'in_force',
    label: 'In Force',
    borderColor: 'border-primary',
    dotColor: 'bg-primary',
    textColor: 'text-primary',
  },
];

function LegislationCard({ item }: { item: CMULegislativeItem }) {
  const categoryLabel = CMU_CATEGORY_LABELS[item.category] || item.category;
  const isInForce = item.status === 'in_force';

  return (
    <a
      href={item.eurLexUrl}
      target="_blank"
      rel="noopener noreferrer"
      className={`block rounded-lg p-3 cursor-pointer border transition-colors hover:border-primary/30 ${
        isInForce ? 'bg-primary/5 border-primary/20' : 'bg-muted/30 border-border/50'
      }`}
    >
      <div className="text-xs text-muted-foreground mb-1">{item.celexNumber}</div>
      <div className="text-sm font-medium text-secondary mb-2">{item.shortTitle}</div>
      <span
        className={`text-[10px] px-2 py-0.5 rounded ${
          isInForce ? 'bg-primary text-white' : 'bg-primary/10 text-primary'
        }`}
      >
        {categoryLabel}
      </span>
    </a>
  );
}

function PipelineColumn({
  config,
  items,
  onViewAll,
}: {
  config: ColumnConfig;
  items: CMULegislativeItem[];
  onViewAll: () => void;
}) {
  const isInForce = config.status === 'in_force';
  const displayItems = isInForce ? items.slice(0, 2) : items;
  const showViewAll = isInForce && items.length > 2;

  return (
    <div className="flex flex-col">
      <div className={`flex items-center gap-2 mb-3 pb-2 border-b-2 ${config.borderColor}`}>
        <div className={`w-2 h-2 rounded-full ${config.dotColor}`} />
        <span className={`text-sm font-medium ${config.textColor}`}>{config.label}</span>
        <span
          className={`ml-auto text-xs px-2 py-0.5 rounded-full ${
            isInForce
              ? 'bg-primary text-white'
              : 'text-muted-foreground bg-muted'
          }`}
        >
          {isInForce ? `${items.length}+` : items.length}
        </span>
      </div>
      <div className="space-y-2 overflow-y-auto flex-1">
        {displayItems.map((item) => (
          <LegislationCard key={item.id} item={item} />
        ))}
        {showViewAll && (
          <div className="text-center py-2">
            <button
              onClick={onViewAll}
              className="text-xs text-primary hover:underline font-medium"
            >
              View all {items.length}+ →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function LegislationModal({
  isOpen,
  onClose,
  items,
  title,
}: {
  isOpen: boolean;
  onClose: () => void;
  items: CMULegislativeItem[];
  title: string;
}) {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-secondary">{title}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 mt-4">
          {items.map((item) => (
            <a
              key={item.id}
              href={item.eurLexUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="block p-4 rounded-lg border border-border/50 hover:border-primary/30 transition-colors"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="text-xs text-muted-foreground mb-1">{item.celexNumber}</div>
                  <div className="font-medium text-secondary mb-2">{item.title}</div>
                  {item.summary && (
                    <p className="text-sm text-muted-foreground">{item.summary}</p>
                  )}
                  <div className="flex gap-2 mt-2">
                    <span className="text-[10px] px-2 py-0.5 rounded bg-primary/10 text-primary">
                      {CMU_CATEGORY_LABELS[item.category]}
                    </span>
                    {item.dateInForce && (
                      <span className="text-[10px] text-muted-foreground">
                        In force: {item.dateInForce}
                      </span>
                    )}
                  </div>
                </div>
                <ExternalLink className="w-4 h-4 text-muted-foreground shrink-0" />
              </div>
            </a>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function LegislativePipeline({
  legislation = FALLBACK_LEGISLATION,
  isLoading = false,
}: LegislativePipelineProps) {
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [modalOpen, setModalOpen] = useState(false);
  const [modalItems, setModalItems] = useState<CMULegislativeItem[]>([]);
  const [modalTitle, setModalTitle] = useState('');

  const filteredLegislation = categoryFilter === 'all'
    ? legislation
    : legislation.filter((item) => item.category === categoryFilter);

  const getItemsByStatus = (status: LegislativeStatus) =>
    filteredLegislation.filter((item) => item.status === status);

  const handleViewAll = (status: LegislativeStatus, label: string) => {
    const items = legislation.filter((item) => item.status === status);
    setModalItems(items);
    setModalTitle(`${label} Legislation (${items.length})`);
    setModalOpen(true);
  };

  return (
    <>
      <Card className="border-border/50 h-[420px]">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Scale className="w-5 h-5 text-secondary" />
              <CardTitle className="text-xl text-secondary">Legislative Pipeline</CardTitle>
            </div>
            <div className="flex items-center gap-3">
              <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                <SelectTrigger className="w-[160px] h-8 text-sm">
                  <SelectValue placeholder="All Categories" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Categories</SelectItem>
                  <SelectItem value="market_infrastructure">Infrastructure</SelectItem>
                  <SelectItem value="retail">Retail</SelectItem>
                  <SelectItem value="securitization">Securitization</SelectItem>
                  <SelectItem value="investment_funds">Funds</SelectItem>
                  <SelectItem value="taxation">Taxation</SelectItem>
                  <SelectItem value="company_law">Company Law</SelectItem>
                </SelectContent>
              </Select>
              <SourceBadges sources={['eur_lex', 'eprs']} size="sm" />
            </div>
          </div>
        </CardHeader>
        <CardContent className="h-[calc(100%-80px)]">
          <div className="grid grid-cols-5 gap-3 h-full overflow-hidden">
            {COLUMNS.map((config) => (
              <PipelineColumn
                key={config.status}
                config={config}
                items={getItemsByStatus(config.status)}
                onViewAll={() => handleViewAll(config.status, config.label)}
              />
            ))}
          </div>
        </CardContent>
      </Card>

      <LegislationModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        items={modalItems}
        title={modalTitle}
      />
    </>
  );
}
