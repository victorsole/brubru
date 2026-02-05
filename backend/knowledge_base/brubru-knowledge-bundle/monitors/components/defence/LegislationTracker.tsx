import { ExternalLink, Scale, FileText } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { LegislationItem } from '@/types/defence';
import { format } from 'date-fns';

interface LegislationTrackerProps {
  legislation: LegislationItem[];
  isLoading?: boolean;
}

function getStatusColor(status: LegislationItem['status']) {
  switch (status) {
    case 'Adopted':
      return 'bg-primary/10 text-primary border-primary/30';
    case 'In Force':
      return 'bg-primary text-primary-foreground';
    case 'In Progress':
      return 'bg-accent/10 text-accent border-accent/30';
    case 'Proposed':
      return 'bg-muted text-muted-foreground';
    default:
      return 'bg-muted text-muted-foreground';
  }
}

function getTypeIcon(type: LegislationItem['type']) {
  switch (type) {
    case 'Regulation':
      return <Scale className="w-4 h-4" />;
    case 'Directive':
      return <FileText className="w-4 h-4" />;
    default:
      return <FileText className="w-4 h-4" />;
  }
}

export function LegislationTracker({ legislation, isLoading }: LegislationTrackerProps) {
  return (
    <Card className="border-border/50">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Scale className="w-5 h-5 text-secondary" />
          <CardTitle className="text-xl text-secondary">
            EU Defence Legislation
          </CardTitle>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Key regulations and directives shaping European defence policy
        </p>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[100px]">Type</TableHead>
                <TableHead>Title</TableHead>
                <TableHead className="w-[100px]">Date</TableHead>
                <TableHead className="w-[100px]">Status</TableHead>
                <TableHead className="w-[60px] text-right">Link</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {legislation.map((item) => (
                <TableRow key={item.id} className="hover:bg-muted/30">
                  <TableCell>
                    <div className="flex items-center gap-2 text-muted-foreground">
                      {getTypeIcon(item.type)}
                      <span className="text-xs">{item.type}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div>
                      <p className="font-medium text-secondary">{item.title}</p>
                      {item.summary && (
                        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                          {item.summary}
                        </p>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {format(item.date, 'MMM yyyy')}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant="outline"
                      className={`text-xs ${getStatusColor(item.status)}`}
                    >
                      {item.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <a
                      href={item.eurLexUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex p-2 hover:bg-muted rounded-md transition-colors text-primary"
                      title="View on EUR-Lex"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        <p className="text-xs text-muted-foreground text-center mt-4">
          Source: EUR-Lex | Subject codes 3.40.09 (Defence) & 6.10.02 (CSDP)
        </p>
      </CardContent>
    </Card>
  );
}
