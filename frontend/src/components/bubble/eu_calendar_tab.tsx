/**
 * EU Calendar Tab Component
 *
 * Main calendar component for My EU Bubble.
 * Month/Week/Day views, institution + policy area filters,
 * My EU Today digest, event detail modal with procedure deep-links.
 *
 * Created: February 2026
 */

import { useEffect, useState, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import Icon from '@mdi/react';
import {
  mdiChevronLeft,
  mdiChevronRight,
  mdiChevronDown,
  mdiMagnify,
  mdiClose,
  mdiCalendarMonth,
  mdiCalendarWeek,
  mdiCalendarToday,
  mdiOpenInNew,
  mdiFileDocumentOutline,
  mdiCrystalBall,
  mdiStarOutline,
  mdiFileEditOutline,
  mdiCalendarClock,
  mdiTagOutline,
} from '@mdi/js';
import {
  useEUCalendar,
  groupEventsByDate,
  PHASE1_INSTITUTIONS,
  POLICY_AREA_CODES,
} from '../../hooks/use_eu_calendar';
import type { ViewMode } from '../../hooks/use_eu_calendar';
import {
  INSTITUTION_CONFIG,
  POLICY_AREA_CONFIG,
  ALL_COMMITTEE_CODES,
  getInstitutionColour,
  getInstitutionLabel,
  getEventTypeLabel,
  getCommitteeLabel,
  formatCalendarDate,
  formatCalendarTime,
  getCountdownText,
} from '../../services/eu_calendar_service';
import type {
  CalendarEvent,
} from '../../services/eu_calendar_service';
import './eu_calendar_tab.css';

// ============================================================================
// Constants
// ============================================================================

const WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const MAX_EVENTS_PER_CELL = 4;

// ============================================================================
// My EU Today Digest
// ============================================================================

function MyEUTodayDigest() {
  const { todayDigest, isLoadingDigest, fetchTodayDigest } = useEUCalendar();
  const [isOpen, setIsOpen] = useState(() => {
    const stored = localStorage.getItem('brubru_eu_today_open');
    return stored !== 'false';
  });

  useEffect(() => {
    fetchTodayDigest();
  }, [fetchTodayDigest]);

  useEffect(() => {
    localStorage.setItem('brubru_eu_today_open', String(isOpen));
  }, [isOpen]);

  if (isLoadingDigest && !todayDigest) return null;
  if (!todayDigest) return null;

  const { today_count, today_events, tomorrow_count, ai_summary } = todayDigest;

  return (
    <div className="eu-calendar-tab__digest">
      <div
        className="eu-calendar-tab__digest-header"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="eu-calendar-tab__digest-title-row">
          <h3 className="eu-calendar-tab__digest-title">My EU Today</h3>
          <span className="eu-calendar-tab__digest-badge">
            {today_count} event{today_count !== 1 ? 's' : ''}
          </span>
        </div>
        <button
          className={`eu-calendar-tab__digest-toggle ${isOpen ? 'eu-calendar-tab__digest-toggle--open' : ''}`}
          aria-label={isOpen ? 'Collapse digest' : 'Expand digest'}
        >
          <Icon path={mdiChevronDown} size={0.8} />
        </button>
      </div>

      {isOpen && (
        <div className="eu-calendar-tab__digest-body">
          {today_events.length > 0 ? (
            <div className="eu-calendar-tab__digest-events">
              {today_events.slice(0, 5).map((event) => (
                <div key={event.id} className="eu-calendar-tab__digest-event">
                  <span
                    className="eu-calendar-tab__digest-event-dot"
                    style={{ background: getInstitutionColour(event.institution) }}
                  />
                  <span>
                    <strong>{getInstitutionLabel(event.institution)}</strong>
                    {' \u2014 '}
                    {event.title}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="eu-calendar-tab__digest-empty">
              No EU institutional events today.
            </div>
          )}

          {tomorrow_count > 0 && (
            <div className="eu-calendar-tab__digest-tomorrow">
              Tomorrow: {tomorrow_count} event{tomorrow_count !== 1 ? 's' : ''}
            </div>
          )}

          {ai_summary && (
            <div className="eu-calendar-tab__digest-summary">
              {ai_summary}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Toolbar
// ============================================================================

function CalendarToolbar() {
  const {
    viewMode, setViewMode, currentDate, navigateDate,
    searchQuery, setSearchQuery,
  } = useEUCalendar();

  const viewModes: { mode: ViewMode; label: string; icon: string }[] = [
    { mode: 'month', label: 'Month', icon: mdiCalendarMonth },
    { mode: 'week', label: 'Week', icon: mdiCalendarWeek },
    { mode: 'day', label: 'Day', icon: mdiCalendarToday },
  ];

  const dateLabel = (() => {
    const opts: Intl.DateTimeFormatOptions = {};
    switch (viewMode) {
      case 'month':
        opts.month = 'long';
        opts.year = 'numeric';
        break;
      case 'week': {
        const d = new Date(currentDate);
        const dow = d.getDay();
        const mondayOffset = dow === 0 ? 6 : dow - 1;
        const monday = new Date(d);
        monday.setDate(d.getDate() - mondayOffset);
        const sunday = new Date(monday);
        sunday.setDate(monday.getDate() + 6);
        return `${monday.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })} \u2013 ${sunday.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}`;
      }
      case 'day':
        opts.weekday = 'long';
        opts.day = 'numeric';
        opts.month = 'long';
        opts.year = 'numeric';
        break;
    }
    return currentDate.toLocaleDateString('en-GB', opts);
  })();

  return (
    <div className="eu-calendar-tab__toolbar">
      <div className="eu-calendar-tab__toolbar-left">
        <div className="eu-calendar-tab__view-toggle">
          {viewModes.map(({ mode, label }) => (
            <button
              key={mode}
              className={`eu-calendar-tab__view-btn ${viewMode === mode ? 'eu-calendar-tab__view-btn--active' : ''}`}
              onClick={() => setViewMode(mode)}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="eu-calendar-tab__nav">
          <button
            className="eu-calendar-tab__nav-btn"
            onClick={() => navigateDate('prev')}
            aria-label="Previous"
          >
            <Icon path={mdiChevronLeft} size={0.8} />
          </button>
          <button
            className="eu-calendar-tab__today-btn"
            onClick={() => navigateDate('today')}
          >
            Today
          </button>
          <button
            className="eu-calendar-tab__nav-btn"
            onClick={() => navigateDate('next')}
            aria-label="Next"
          >
            <Icon path={mdiChevronRight} size={0.8} />
          </button>
        </div>

        <span className="eu-calendar-tab__date-label">{dateLabel}</span>
      </div>

      <div className="eu-calendar-tab__toolbar-right">
        <div className="eu-calendar-tab__search">
          <Icon path={mdiMagnify} size={0.7} className="eu-calendar-tab__search-icon" />
          <input
            type="text"
            className="eu-calendar-tab__search-input"
            placeholder="Search events..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Filter Chips
// ============================================================================

function CalendarFilters() {
  const {
    activeInstitutions, toggleInstitution,
    activePolicyAreas, togglePolicyArea,
    activeCommittees, toggleCommittee,
    clearFilters,
  } = useEUCalendar();

  const hasFilters = activeInstitutions.size > 0 || activePolicyAreas.size > 0 || activeCommittees.size > 0;

  // Show committee filter row when EP is in active institutions
  const showCommitteeFilter = activeInstitutions.has('EP');

  return (
    <div className="eu-calendar-tab__filters">
      {/* Institution chips */}
      <div className="eu-calendar-tab__filter-row">
        <span className="eu-calendar-tab__filter-label">Institutions</span>
        {PHASE1_INSTITUTIONS.map((code) => {
          const config = INSTITUTION_CONFIG[code];
          const isActive = activeInstitutions.has(code);
          return (
            <span
              key={code}
              className={`eu-calendar-tab__chip ${isActive ? 'eu-calendar-tab__chip--active' : 'eu-calendar-tab__chip--inactive'}`}
              style={{
                borderColor: config.colour,
                background: isActive ? config.colour : 'white',
                color: isActive ? 'white' : config.colour,
              }}
              onClick={() => toggleInstitution(code)}
            >
              {config.shortLabel}
            </span>
          );
        })}
      </div>

      {/* Policy area chips */}
      <div className="eu-calendar-tab__filter-row">
        <span className="eu-calendar-tab__filter-label">Policy</span>
        {POLICY_AREA_CODES.map((code) => {
          const config = POLICY_AREA_CONFIG[code];
          if (!config) return null;
          const isActive = activePolicyAreas.has(code);
          return (
            <span
              key={code}
              className={`eu-calendar-tab__chip ${isActive ? 'eu-calendar-tab__chip--active' : 'eu-calendar-tab__chip--inactive'}`}
              style={{
                borderColor: config.colour,
                background: isActive ? config.colour : 'white',
                color: isActive ? 'white' : config.colour,
              }}
              onClick={() => togglePolicyArea(code)}
            >
              {config.label}
            </span>
          );
        })}
      </div>

      {/* Committee chips (visible when EP filter is active) */}
      {showCommitteeFilter && (
        <div className="eu-calendar-tab__filter-row eu-calendar-tab__filter-row--committees">
          <span className="eu-calendar-tab__filter-label">Committee</span>
          {ALL_COMMITTEE_CODES.map((code) => {
            const isActive = activeCommittees.has(code);
            return (
              <span
                key={code}
                className={`eu-calendar-tab__chip eu-calendar-tab__chip--committee ${isActive ? 'eu-calendar-tab__chip--active' : 'eu-calendar-tab__chip--inactive'}`}
                style={{
                  borderColor: '#0693e3',
                  background: isActive ? '#0693e3' : 'white',
                  color: isActive ? 'white' : '#0693e3',
                }}
                onClick={() => toggleCommittee(code)}
                title={getCommitteeLabel(code)}
              >
                {code}
              </span>
            );
          })}
        </div>
      )}

      {/* Clear all - visible when any filter is active */}
      {hasFilters && (
        <div className="eu-calendar-tab__filter-row eu-calendar-tab__filter-row--clear">
          <button className="eu-calendar-tab__clear-filters" onClick={clearFilters}>
            <Icon path={mdiClose} size={0.5} />
            Clear all filters
          </button>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Month View
// ============================================================================

function MonthView() {
  const { events, currentDate, goToDate, selectEvent } = useEUCalendar();
  const eventsByDate = groupEventsByDate(events);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);

  // Calculate grid start (Monday before first day of month)
  const startDow = firstDay.getDay();
  const startOffset = startDow === 0 ? 6 : startDow - 1;
  const gridStart = new Date(year, month, 1 - startOffset);

  // Calculate total cells (fill to complete weeks)
  const totalDays = startOffset + lastDay.getDate();
  const totalCells = Math.ceil(totalDays / 7) * 7;

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const todayStr = formatDateISO(today);

  const cells: { date: Date; dateStr: string; isCurrentMonth: boolean; isToday: boolean }[] = [];
  for (let i = 0; i < totalCells; i++) {
    const d = new Date(gridStart);
    d.setDate(gridStart.getDate() + i);
    const dateStr = formatDateISO(d);
    cells.push({
      date: d,
      dateStr,
      isCurrentMonth: d.getMonth() === month,
      isToday: dateStr === todayStr,
    });
  }

  return (
    <>
      {/* Desktop month grid */}
      <div className="eu-calendar-tab__month-grid">
        {WEEKDAY_LABELS.map((label) => (
          <div key={label} className="eu-calendar-tab__month-header">{label}</div>
        ))}
        {cells.map((cell) => {
          const dayEvents = eventsByDate.get(cell.dateStr) || [];
          return (
            <div
              key={cell.dateStr}
              className={`eu-calendar-tab__month-cell ${cell.isToday ? 'eu-calendar-tab__month-cell--today' : ''} ${!cell.isCurrentMonth ? 'eu-calendar-tab__month-cell--other-month' : ''}`}
              onClick={() => goToDate(cell.date)}
            >
              <div className="eu-calendar-tab__month-day-num">
                {cell.date.getDate()}
              </div>
              <div className="eu-calendar-tab__month-events">
                {dayEvents.slice(0, MAX_EVENTS_PER_CELL).map((event) => {
                  const eventTypeClass =
                    event.event_type === 'committee_meeting' ? 'eu-calendar-tab__month-event--committee'
                    : event.event_type === 'committee_week' || event.event_type === 'group_week' ? 'eu-calendar-tab__month-event--block-week'
                    : event.event_type === 'plenary_session' ? 'eu-calendar-tab__month-event--plenary'
                    : '';
                  // Committee meetings: show just the 4-char code (compact)
                  const pillLabel = event.event_type === 'committee_meeting' && event.ep_committee_code
                    ? event.ep_committee_code
                    : event.title;
                  return (
                    <div
                      key={event.id}
                      className={`eu-calendar-tab__month-event ${eventTypeClass}`}
                      style={{ background: getInstitutionColour(event.institution) }}
                      onClick={(e) => { e.stopPropagation(); selectEvent(event); }}
                      title={event.title}
                    >
                      {pillLabel}
                    </div>
                  );
                })}
                {dayEvents.length > MAX_EVENTS_PER_CELL && (
                  <div className="eu-calendar-tab__month-more">
                    +{dayEvents.length - MAX_EVENTS_PER_CELL} more
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Mobile: list of events for current month */}
      <MobileEventList events={events} />
    </>
  );
}

// ============================================================================
// Week View
// ============================================================================

function WeekView() {
  const { events, currentDate, selectEvent } = useEUCalendar();
  const eventsByDate = groupEventsByDate(events);

  const dow = currentDate.getDay();
  const mondayOffset = dow === 0 ? 6 : dow - 1;
  const monday = new Date(currentDate);
  monday.setDate(currentDate.getDate() - mondayOffset);

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const todayStr = formatDateISO(today);

  const days: { date: Date; dateStr: string; isToday: boolean }[] = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    const dateStr = formatDateISO(d);
    days.push({ date: d, dateStr, isToday: dateStr === todayStr });
  }

  return (
    <div className="eu-calendar-tab__week-view">
      {days.map((day) => {
        const dayEvents = eventsByDate.get(day.dateStr) || [];
        return (
          <div
            key={day.dateStr}
            className={`eu-calendar-tab__week-day ${day.isToday ? 'eu-calendar-tab__week-day--today' : ''}`}
          >
            <div className="eu-calendar-tab__week-day-header">
              <div className="eu-calendar-tab__week-day-name">
                {WEEKDAY_LABELS[day.date.getDay() === 0 ? 6 : day.date.getDay() - 1]}
              </div>
              <div className="eu-calendar-tab__week-day-number">
                {day.date.getDate()}
              </div>
            </div>
            <div className="eu-calendar-tab__week-events">
              {dayEvents.map((event) => (
                <div
                  key={event.id}
                  className={`eu-calendar-tab__week-event ${event.event_type === 'committee_meeting' ? 'eu-calendar-tab__week-event--committee' : ''}`}
                  style={{ borderLeftColor: getInstitutionColour(event.institution) }}
                  onClick={() => selectEvent(event)}
                >
                  <div className="eu-calendar-tab__week-event-title">
                    {event.event_type === 'committee_meeting' && event.ep_committee_code && (
                      <span className="eu-calendar-tab__week-event-code">{event.ep_committee_code}</span>
                    )}
                    {event.event_type === 'committee_meeting' && event.ep_committee_code
                      ? getCommitteeLabel(event.ep_committee_code)
                      : event.title}
                  </div>
                  {event.start_time && (
                    <div className="eu-calendar-tab__week-event-time">
                      {formatCalendarTime(event.start_time)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ============================================================================
// Day View
// ============================================================================

function DayView() {
  const { events, selectEvent } = useEUCalendar();

  if (events.length === 0) {
    return (
      <div className="eu-calendar-tab__empty">
        <Icon path={mdiCalendarToday} size={2} color="#d1d5db" />
        <div className="eu-calendar-tab__empty-text">No events on this day</div>
        <div className="eu-calendar-tab__empty-hint">Try navigating to another date or adjusting your filters.</div>
      </div>
    );
  }

  return (
    <div className="eu-calendar-tab__day-view">
      {events.map((event) => {
        const countdown = getCountdownText(event.start_date);
        return (
          <div
            key={event.id}
            className="eu-calendar-tab__day-event-card"
            style={{ borderLeftColor: getInstitutionColour(event.institution) }}
            onClick={() => selectEvent(event)}
          >
            <div className="eu-calendar-tab__day-event-time">
              {event.all_day ? 'All day' : formatCalendarTime(event.start_time) || ''}
            </div>
            <div className="eu-calendar-tab__day-event-content">
              <h4 className="eu-calendar-tab__day-event-title">{event.title}</h4>
              <div className="eu-calendar-tab__day-event-meta">
                <span
                  className="eu-calendar-tab__institution-badge"
                  style={{ background: getInstitutionColour(event.institution) }}
                >
                  {getInstitutionLabel(event.institution)}
                </span>
                {event.ep_committee_code && (
                  <span className="eu-calendar-tab__committee-badge">
                    {event.ep_committee_code}
                  </span>
                )}
                <span className="eu-calendar-tab__event-type-label">
                  {getEventTypeLabel(event.event_type)}
                </span>
                {countdown && (
                  <span className="eu-calendar-tab__countdown-badge">{countdown}</span>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ============================================================================
// Mobile Event List (for month view on small screens)
// ============================================================================

function MobileEventList({ events }: { events: CalendarEvent[] }) {
  const { selectEvent } = useEUCalendar();

  if (events.length === 0) return null;

  // Group and sort by date
  const eventsByDate = groupEventsByDate(events);
  const sortedDates = Array.from(eventsByDate.keys()).sort();

  return (
    <div className="eu-calendar-tab__month-mobile-list">
      {sortedDates.map((dateStr) => {
        const dayEvents = eventsByDate.get(dateStr) || [];
        if (dayEvents.length === 0) return null;
        return (
          <div key={dateStr}>
            <div className="eu-calendar-tab__mobile-date-header">
              {formatCalendarDate(dateStr)}
              <span className="eu-calendar-tab__mobile-date-count">
                {dayEvents.length} event{dayEvents.length !== 1 ? 's' : ''}
              </span>
            </div>
            {dayEvents.map((event) => {
              const countdown = getCountdownText(event.start_date);
              return (
                <div
                  key={event.id}
                  className="eu-calendar-tab__day-event-card"
                  style={{ borderLeftColor: getInstitutionColour(event.institution) }}
                  onClick={() => selectEvent(event)}
                >
                  <div className="eu-calendar-tab__day-event-time">
                    {event.all_day ? 'All day' : formatCalendarTime(event.start_time) || ''}
                  </div>
                  <div className="eu-calendar-tab__day-event-content">
                    <h4 className="eu-calendar-tab__day-event-title">{event.title}</h4>
                    <div className="eu-calendar-tab__day-event-meta">
                      <span
                        className="eu-calendar-tab__institution-badge"
                        style={{ background: getInstitutionColour(event.institution) }}
                      >
                        {getInstitutionLabel(event.institution)}
                      </span>
                      {event.ep_committee_code && (
                        <span className="eu-calendar-tab__committee-badge">
                          {event.ep_committee_code}
                        </span>
                      )}
                      {countdown && (
                        <span className="eu-calendar-tab__countdown-badge">{countdown}</span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

// ============================================================================
// Event Detail Modal
// ============================================================================

function EventDetailModal() {
  const { selectedEvent, selectEvent } = useEUCalendar();
  const navigate = useNavigate();

  const handleClose = useCallback(() => {
    selectEvent(null);
  }, [selectEvent]);

  // Close on Escape
  useEffect(() => {
    if (!selectedEvent) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [selectedEvent, handleClose]);

  if (!selectedEvent) return null;

  const event = selectedEvent;
  const countdown = getCountdownText(event.start_date);

  const dateDisplay = (() => {
    let s = formatCalendarDate(event.start_date);
    if (event.end_date && event.end_date !== event.start_date) {
      s += ` \u2013 ${formatCalendarDate(event.end_date)}`;
    }
    if (!event.all_day && event.start_time) {
      s += `, ${formatCalendarTime(event.start_time)}`;
      if (event.end_time) {
        s += ` \u2013 ${formatCalendarTime(event.end_time)}`;
      }
    }
    return s;
  })();

  return createPortal(
    <div
      className="eu-calendar-tab__modal-overlay"
      onClick={handleClose}
    >
      <div
        className="eu-calendar-tab__modal"
        style={{ borderTopColor: getInstitutionColour(event.institution) } as React.CSSProperties}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="eu-calendar-tab__modal-header">
          <div>
            <span
              className="eu-calendar-tab__institution-badge"
              style={{ background: getInstitutionColour(event.institution) }}
            >
              {getInstitutionLabel(event.institution)}
            </span>
          </div>
          <button className="eu-calendar-tab__modal-close" onClick={handleClose}>
            <Icon path={mdiClose} size={0.9} />
          </button>
        </div>

        <div className="eu-calendar-tab__modal-body">
          <h2 className="eu-calendar-tab__modal-title">{event.title}</h2>

          <div className="eu-calendar-tab__modal-meta">
            <div className="eu-calendar-tab__modal-meta-row">
              <Icon path={mdiCalendarClock} size={0.75} className="eu-calendar-tab__modal-meta-icon" />
              <span>{dateDisplay}</span>
              {countdown && (
                <span className="eu-calendar-tab__countdown-badge">{countdown}</span>
              )}
            </div>
            <div className="eu-calendar-tab__modal-meta-row">
              <Icon path={mdiTagOutline} size={0.75} className="eu-calendar-tab__modal-meta-icon" />
              <span>{getEventTypeLabel(event.event_type)}</span>
              {event.council_configuration && (
                <span> &mdash; {event.council_configuration}</span>
              )}
            </div>
            {event.ep_committee_code && (
              <div className="eu-calendar-tab__modal-meta-row">
                <span className="eu-calendar-tab__committee-badge">
                  {event.ep_committee_code}
                </span>
                <span>{getCommitteeLabel(event.ep_committee_code)}</span>
              </div>
            )}
          </div>

          {event.description && (
            <div className="eu-calendar-tab__modal-description">
              {event.description}
            </div>
          )}

          {/* Procedure deep-links */}
          {event.procedure_refs && event.procedure_refs.length > 0 && (
            <div className="eu-calendar-tab__modal-procedures">
              <h4 className="eu-calendar-tab__modal-procedures-title">Related Procedures</h4>
              {event.procedure_refs.map((ref) => (
                <div key={ref} className="eu-calendar-tab__procedure-item">
                  <span className="eu-calendar-tab__procedure-ref">{ref}</span>
                  <div className="eu-calendar-tab__procedure-links">
                    <button
                      className="eu-calendar-tab__procedure-link eu-calendar-tab__procedure-link--predictions"
                      onClick={() => { handleClose(); navigate(`/my-eu-bubble?tab=predictions&ref=${encodeURIComponent(ref)}`); }}
                    >
                      <Icon path={mdiCrystalBall} size={0.55} /> Predictions
                    </button>
                    <button
                      className="eu-calendar-tab__procedure-link eu-calendar-tab__procedure-link--tracked"
                      onClick={() => { handleClose(); navigate('/my-eu-bubble?tab=my_files'); }}
                    >
                      <Icon path={mdiStarOutline} size={0.55} /> My Files
                    </button>
                    <button
                      className="eu-calendar-tab__procedure-link eu-calendar-tab__procedure-link--amendator"
                      onClick={() => { handleClose(); navigate('/amendator'); }}
                    >
                      <Icon path={mdiFileEditOutline} size={0.55} /> Amendator
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="eu-calendar-tab__modal-footer">
          {event.agenda_url && (
            <a
              href={event.agenda_url}
              target="_blank"
              rel="noopener noreferrer"
              className="eu-calendar-tab__modal-link-btn eu-calendar-tab__modal-link-btn--primary"
            >
              <Icon path={mdiFileDocumentOutline} size={0.7} />
              {event.event_type === 'committee_meeting' ? 'View Draft Agenda (PDF)' : 'View agenda'}
            </a>
          )}
          {event.source_url && (
            <a
              href={event.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="eu-calendar-tab__modal-link-btn"
            >
              <Icon path={mdiOpenInNew} size={0.7} />
              {event.event_type === 'committee_meeting'
                ? 'View committee documents'
                : event.event_type === 'committee_week'
                  ? 'View draft agendas'
                  : event.event_type === 'commission_college_meeting'
                    ? 'View agendas (OJ documents)'
                    : `Open on ${getInstitutionLabel(event.institution)} website`}
            </a>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}

// ============================================================================
// Helper
// ============================================================================

function formatDateISO(d: Date): string {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

// ============================================================================
// Main Component
// ============================================================================

export const EUCalendarTab = () => {
  const { viewMode, isLoading, fetchEvents } = useEUCalendar();

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const renderView = () => {
    if (isLoading) {
      return (
        <div className="eu-calendar-tab__skeleton">
          <div className="eu-calendar-tab__skeleton-header">
            {WEEKDAY_LABELS.map((label) => (
              <div key={label} className="eu-calendar-tab__skeleton-weekday">{label}</div>
            ))}
          </div>
          <div className="eu-calendar-tab__skeleton-grid">
            {Array.from({ length: 35 }).map((_, i) => (
              <div key={i} className="eu-calendar-tab__skeleton-cell">
                <div className="eu-calendar-tab__skeleton-day" />
                {i % 3 === 0 && <div className="eu-calendar-tab__skeleton-pill" />}
                {i % 5 === 0 && <div className="eu-calendar-tab__skeleton-pill eu-calendar-tab__skeleton-pill--short" />}
              </div>
            ))}
          </div>
        </div>
      );
    }

    switch (viewMode) {
      case 'month':
        return <MonthView />;
      case 'week':
        return <WeekView />;
      case 'day':
        return <DayView />;
      default:
        return <MonthView />;
    }
  };

  return (
    <div className="eu-calendar-tab">
      <MyEUTodayDigest />
      <CalendarToolbar />
      <CalendarFilters />
      {renderView()}
      <EventDetailModal />
    </div>
  );
};

export default EUCalendarTab;
