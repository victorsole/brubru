import { BookOpen, FileText } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { SourceBadges } from './SourceBadge';
import { FALLBACK_RESEARCH } from '@/data/cmuFallback';
import type { ResearchPublication } from '@/types/cmu';

interface ResearchFeedProps {
  publications?: ResearchPublication[];
  isLoading?: boolean;
}

function PublicationCard({ item }: { item: ResearchPublication }) {
  const iconColorClasses = {
    primary: 'bg-primary/10 text-primary',
    accent: 'bg-accent/10 text-accent',
    secondary: 'bg-secondary/10 text-secondary',
    destructive: 'bg-destructive/10 text-destructive',
  };

  return (
    <a
      href={item.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block p-3 rounded-lg bg-muted/30 border border-border/50 hover:border-primary/30 transition-colors"
    >
      <div className="flex items-start gap-3">
        <div className={`p-2 rounded flex-shrink-0 ${iconColorClasses[item.iconColor]}`}>
          <FileText className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[9px] px-1.5 py-0 font-medium bg-primary/5 text-primary border border-primary/20 rounded">
              {item.organizationLabel}
            </span>
            <span className="text-xs text-muted-foreground">{item.publishedAt}</span>
          </div>
          <div className="text-sm font-medium text-secondary line-clamp-2">{item.title}</div>
          {item.abstract && (
            <div className="text-xs text-muted-foreground mt-1 line-clamp-2">
              {item.abstract}
            </div>
          )}
        </div>
      </div>
    </a>
  );
}

export function ResearchFeed({
  publications = FALLBACK_RESEARCH,
  isLoading = false,
}: ResearchFeedProps) {
  return (
    <Card className="border-border/50 h-[420px] flex flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-secondary" />
            <CardTitle className="text-lg text-secondary">Research & Analysis</CardTitle>
          </div>
          <SourceBadges sources={['eprs', 'eca', 'jrc']} size="sm" />
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-hidden">
        <div className="h-full space-y-3 overflow-y-auto">
          {publications.map((item) => (
            <PublicationCard key={item.id} item={item} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
