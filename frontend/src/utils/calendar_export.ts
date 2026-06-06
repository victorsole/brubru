// frontend/src/utils/calendar_export.ts
//
// Export My EU Calendar events to the user's own calendar: a "Add to Google
// Calendar" link, an "Add to Outlook" link, and a downloadable .ics file
// (Apple Calendar, Outlook desktop, any client). All times are emitted in UTC
// so no VTIMEZONE block is needed and every client interprets them correctly.
// EU institutional events are published in Europe/Brussels wall-clock time, so
// timed events are converted Brussels -> UTC for the date in question (handles
// the CET/CEST switch).
import type { CalendarEvent } from '../services/eu_calendar_service';

// Minutes that `timeZone` is ahead of UTC at the given instant.
function tzOffsetMinutes(timeZone: string, date: Date): number {
  const dtf = new Intl.DateTimeFormat('en-US', {
    timeZone, hourCycle: 'h23',
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
  const m: Record<string, string> = {};
  for (const p of dtf.formatToParts(date)) m[p.type] = p.value;
  const asUTC = Date.UTC(+m.year, +m.month - 1, +m.day, +m.hour, +m.minute, +m.second);
  return (asUTC - date.getTime()) / 60000;
}

// A Brussels wall-clock date+time -> the real UTC instant.
function brusselsWallToUTC(dateStr: string, timeStr: string): Date {
  const [Y, M, D] = dateStr.split('-').map(Number);
  const [h, mi, s] = (timeStr || '00:00:00').split(':').map(Number);
  const guess = new Date(Date.UTC(Y, M - 1, D, h || 0, mi || 0, s || 0));
  const off = tzOffsetMinutes('Europe/Brussels', guess);
  return new Date(guess.getTime() - off * 60000);
}

export interface EventTime {
  allDay: boolean;
  start: Date;
  end: Date;
}

// Resolve an event's start/end as concrete instants. Falls back gracefully: a
// timed event with no times becomes all-day; a missing end becomes +1h (timed)
// or the start day (all-day).
export function resolveEventTime(ev: CalendarEvent): EventTime {
  const allDay = ev.all_day || !ev.start_time;
  if (allDay) {
    const start = new Date(`${ev.start_date}T00:00:00Z`);
    const endDateStr = ev.end_date || ev.start_date;
    const end = new Date(`${endDateStr}T00:00:00Z`);
    return { allDay: true, start, end };
  }
  const start = brusselsWallToUTC(ev.start_date, ev.start_time as string);
  const end = ev.end_time
    ? brusselsWallToUTC(ev.end_date || ev.start_date, ev.end_time)
    : new Date(start.getTime() + 60 * 60000);
  return { allDay: false, start, end };
}

// ---- date formatting ------------------------------------------------------

const pad = (n: number) => String(n).padStart(2, '0');

// UTC stamp YYYYMMDDTHHMMSSZ (timed) used by Google + .ics.
function utcStamp(d: Date): string {
  return `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}T${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}${pad(d.getUTCSeconds())}Z`;
}

// DATE stamp YYYYMMDD (all-day).
function dateStamp(d: Date): string {
  return `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}`;
}

// All-day DTEND is exclusive: the day after the last day.
function nextDay(d: Date): Date {
  return new Date(d.getTime() + 24 * 60 * 60000);
}

function plainText(ev: CalendarEvent): string {
  const parts = [ev.description || ''];
  if (ev.agenda_url) parts.push(`Agenda: ${ev.agenda_url}`);
  if (ev.source_url) parts.push(`Source: ${ev.source_url}`);
  parts.push('Added from Brubru — My EU Calendar.');
  return parts.filter(Boolean).join('\n\n');
}

function location(ev: CalendarEvent): string {
  return ev.ep_committee_code
    ? `European Parliament — ${ev.ep_committee_code}`
    : (ev.institution || '').toString().replace(/_/g, ' ');
}

// ---- Google -----------------------------------------------------------------

export function googleCalendarUrl(ev: CalendarEvent): string {
  const { allDay, start, end } = resolveEventTime(ev);
  const dates = allDay
    ? `${dateStamp(start)}/${dateStamp(nextDay(end))}`
    : `${utcStamp(start)}/${utcStamp(end)}`;
  const p = new URLSearchParams({
    action: 'TEMPLATE',
    text: ev.title || 'EU event',
    dates,
    details: plainText(ev),
    location: location(ev),
  });
  return `https://calendar.google.com/calendar/render?${p.toString()}`;
}

// ---- Outlook ----------------------------------------------------------------

export function outlookCalendarUrl(ev: CalendarEvent): string {
  const { allDay, start, end } = resolveEventTime(ev);
  const p = new URLSearchParams({
    path: '/calendar/action/compose',
    rru: 'addevent',
    subject: ev.title || 'EU event',
    body: plainText(ev),
    location: location(ev),
    startdt: allDay ? ev.start_date : start.toISOString(),
    enddt: allDay ? (ev.end_date || ev.start_date) : end.toISOString(),
  });
  if (allDay) p.set('allday', 'true');
  return `https://outlook.live.com/calendar/0/deeplink/compose?${p.toString()}`;
}

// ---- ICS (download) ---------------------------------------------------------

function icsEscape(s: string): string {
  return (s || '').replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\n/g, '\\n');
}

// Fold a content line at 75 octets per RFC 5545.
function fold(line: string): string {
  if (line.length <= 75) return line;
  const out: string[] = [];
  let s = line;
  while (s.length > 75) { out.push(s.slice(0, 75)); s = ' ' + s.slice(75); }
  out.push(s);
  return out.join('\r\n');
}

function vevent(ev: CalendarEvent, stamp: string): string {
  const { allDay, start, end } = resolveEventTime(ev);
  const lines = ['BEGIN:VEVENT', `UID:${ev.id}@brubru.beresol.eu`, `DTSTAMP:${stamp}`];
  if (allDay) {
    lines.push(`DTSTART;VALUE=DATE:${dateStamp(start)}`);
    lines.push(`DTEND;VALUE=DATE:${dateStamp(nextDay(end))}`);
  } else {
    lines.push(`DTSTART:${utcStamp(start)}`);
    lines.push(`DTEND:${utcStamp(end)}`);
  }
  lines.push(`SUMMARY:${icsEscape(ev.title || 'EU event')}`);
  const desc = plainText(ev);
  if (desc) lines.push(`DESCRIPTION:${icsEscape(desc)}`);
  const loc = location(ev);
  if (loc) lines.push(`LOCATION:${icsEscape(loc)}`);
  if (ev.source_url) lines.push(`URL:${ev.source_url}`);
  lines.push('END:VEVENT');
  return lines.map(fold).join('\r\n');
}

export function icsForEvents(events: CalendarEvent[]): string {
  // DTSTAMP must be a real UTC instant; the caller has the current time.
  const now = new Date();
  const stamp = utcStamp(now);
  const body = events.map((e) => vevent(e, stamp)).join('\r\n');
  return [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Brubru//My EU Calendar//EN',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    body,
    'END:VCALENDAR',
  ].join('\r\n');
}

export function downloadIcs(events: CalendarEvent[], filename = 'brubru-eu-calendar.ics'): void {
  const blob = new Blob([icsForEvents(events)], { type: 'text/calendar;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
