import { Calendar, Download } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { SourceBadges } from './SourceBadge';
import { FALLBACK_CALENDAR } from '@/data/cmuFallback';
import type { CalendarEvent } from '@/types/cmu';

interface KeyDatesProps {
  events?: CalendarEvent[];
  isLoading?: boolean;
}

function getEventStyles(type: CalendarEvent['type']) {
  switch (type) {
    case 'proposal':
      return {
        dotColor: 'hsl(45 85% 50%)',
        textColor: 'text-accent',
        badgeBg: 'bg-accent/10',
        badgeText: 'text-accent',
      };
    case 'deadline':
      return {
        dotColor: 'hsl(120 65% 45%)',
        textColor: 'text-primary',
        badgeBg: 'bg-primary',
        badgeText: 'text-white',
      };
    case 'review':
      return {
        dotColor: 'hsl(280 60% 50%)',
        textColor: 'text-purple-600',
        badgeBg: 'bg-purple-100',
        badgeText: 'text-purple-600',
      };
    case 'strategy':
      return {
        dotColor: 'hsl(120 65% 45%)',
        textColor: 'text-primary',
        badgeBg: 'bg-primary/10',
        badgeText: 'text-primary',
      };
    default:
      return {
        dotColor: 'hsl(120 65% 45%)',
        textColor: 'text-primary',
        badgeBg: 'bg-primary/10',
        badgeText: 'text-primary',
      };
  }
}

function TimelineItem({ event }: { event: CalendarEvent }) {
  const styles = getEventStyles(event.type);
  const typeLabel = event.type.charAt(0).toUpperCase() + event.type.slice(1);

  return (
    <div className="relative pl-4">
      <div
        className="absolute left-0 top-1.5 w-2 h-2 rounded-full"
        style={{ backgroundColor: styles.dotColor }}
      />
      <div className={`text-xs font-medium mb-1 ${styles.textColor}`}>{event.date}</div>
      <div className="text-sm font-medium text-secondary">{event.title}</div>
      <span className={`text-[10px] px-2 py-0.5 rounded ${styles.badgeBg} ${styles.badgeText}`}>
        {typeLabel}
      </span>
    </div>
  );
}

export function KeyDates({ events = FALLBACK_CALENDAR, isLoading = false }: KeyDatesProps) {
  const handleExportCalendar = () => {
    // Generate ICS file content
    const icsContent = [
      'BEGIN:VCALENDAR',
      'VERSION:2.0',
      'PRODID:-//Beresol//CMU Monitor//EN',
      ...events.map((event) => [
        'BEGIN:VEVENT',
        `SUMMARY:${event.title}`,
        `DESCRIPTION:${event.description || event.title}`,
        `DTSTART:${event.date.replace(/\s/g, '')}`,
        'END:VEVENT',
      ]).flat(),
      'END:VCALENDAR',
    ].join('\r\n');

    const blob = new Blob([icsContent], { type: 'text/calendar' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'cmu-key-dates.ics';
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Card className="border-border/50 h-[420px] flex flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Calendar className="w-5 h-5 text-accent" />
            <CardTitle className="text-lg text-secondary">Key Dates</CardTitle>
          </div>
          <SourceBadges sources={['european_commission', 'eprs']} size="sm" />
        </div>
      </CardHeader>
      <CardContent className="flex-1 overflow-hidden flex flex-col">
        <div className="flex-1 overflow-y-auto relative pl-6 space-y-4">
          {/* Timeline line */}
          <div className="absolute left-[3px] top-0 bottom-0 w-px bg-border" />

          {events.map((event) => (
            <TimelineItem key={event.id} event={event} />
          ))}
        </div>

        <Button
          variant="outline"
          size="sm"
          className="w-full mt-4 text-primary border-primary/20 hover:bg-primary/5"
          onClick={handleExportCalendar}
        >
          <Download className="w-4 h-4 mr-2" />
          Export to Calendar
        </Button>
      </CardContent>
    </Card>
  );
}
