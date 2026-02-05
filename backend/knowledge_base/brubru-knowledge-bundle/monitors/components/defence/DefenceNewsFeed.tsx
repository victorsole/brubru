import { ExternalLink, Newspaper, RefreshCw } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { DefenceNewsItem } from '@/types/defence';
import { formatDistanceToNow } from 'date-fns';

interface DefenceNewsFeedProps {
  news: DefenceNewsItem[];
  isLoading?: boolean;
  onRefresh?: () => void;
}

function NewsItemCard({ item }: { item: DefenceNewsItem }) {
  return (
    <article className="p-4 border-b border-border/50 hover:bg-muted/30 transition-colors last:border-b-0">
      <div className="flex items-start justify-between gap-2 mb-2">
        <Badge variant="outline" className="text-xs shrink-0">
          {item.source}
        </Badge>
        <time className="text-xs text-muted-foreground whitespace-nowrap">
          {formatDistanceToNow(item.pubDate, { addSuffix: true })}
        </time>
      </div>
      <a
        href={item.link}
        target="_blank"
        rel="noopener noreferrer"
        className="group block"
      >
        <h4 className="font-medium text-secondary line-clamp-2 mb-1 group-hover:text-primary transition-colors">
          {item.title}
        </h4>
        {item.description && (
          <p className="text-sm text-muted-foreground line-clamp-2">
            {item.description}
          </p>
        )}
        <span className="inline-flex items-center gap-1 text-xs text-primary mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
          Read more <ExternalLink className="w-3 h-3" />
        </span>
      </a>
    </article>
  );
}

function NewsItemSkeleton() {
  return (
    <div className="p-4 border-b border-border/50 last:border-b-0">
      <div className="flex items-center justify-between mb-2">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="h-4 w-16" />
      </div>
      <Skeleton className="h-5 w-full mb-1" />
      <Skeleton className="h-5 w-3/4 mb-2" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-2/3 mt-1" />
    </div>
  );
}

export function DefenceNewsFeed({ news, isLoading, onRefresh }: DefenceNewsFeedProps) {
  return (
    <Card className="border-border/50 h-full flex flex-col">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <div className="flex items-center gap-2">
          <Newspaper className="w-5 h-5 text-accent" />
          <CardTitle className="text-lg text-secondary">
            Defence News
          </CardTitle>
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="p-2 hover:bg-muted rounded-md transition-colors"
            title="Refresh news"
          >
            <RefreshCw className="w-4 h-4 text-muted-foreground" />
          </button>
        )}
      </CardHeader>
      <CardContent className="flex-1 overflow-hidden p-0">
        <div className="h-full max-h-[500px] overflow-y-auto">
          {isLoading ? (
            <>
              {Array.from({ length: 5 }).map((_, i) => (
                <NewsItemSkeleton key={i} />
              ))}
            </>
          ) : news.length > 0 ? (
            news.map((item) => <NewsItemCard key={item.id} item={item} />)
          ) : (
            <div className="p-8 text-center text-muted-foreground">
              <Newspaper className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No news available</p>
              <p className="text-sm mt-1">Check back later for updates</p>
            </div>
          )}
        </div>
      </CardContent>
      <div className="px-4 py-2 border-t border-border/50 bg-muted/30">
        <p className="text-xs text-muted-foreground text-center">
          Aggregated from EU Parliament, Euractiv, Defense News & more
        </p>
      </div>
    </Card>
  );
}
