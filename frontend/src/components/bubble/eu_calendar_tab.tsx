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
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
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
  mdiCalendarPlus,
  mdiDownloadOutline,
} from '@mdi/js';
import {
  googleCalendarUrl, outlookCalendarUrl, downloadIcs,
} from '../../utils/calendar_export';
import { MeubHeader } from './meub_header';
import { ArchiveToggle, ArchiveButton } from './archive_controls';
import { archiveService } from '../../services/archive_service';
import { toast } from '../shared/feedback_host';
import {
  useEUCalendar,
  groupEventsByDate,
  PHASE1_INSTITUTIONS,
  CORE_INSTITUTIONS,
  FILTERABLE_EVENT_TYPES,
  EP_DELEGATION_OPTIONS,
  EP_GROUP_OPTIONS,
  EP_OTHER_OPTIONS,
  POLICY_AREA_CODES,
} from '../../hooks/use_eu_calendar';
import type { ViewMode } from '../../hooks/use_eu_calendar';
import { useAuth } from '../../hooks/use_auth';
import {
  INSTITUTION_CONFIG,
  POLICY_AREA_CONFIG,
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

// Monday-first weekday keys; labels come from i18n (calendar.wd.*).
const WD_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const MAX_EVENTS_PER_CELL = 4;

// ============================================================================
// My EU Today Digest
// ============================================================================

function MyEUTodayDigest() {
  const { t } = useTranslation();
  const { todayDigest, isLoadingDigest, fetchTodayDigest } = useEUCalendar();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const [isOpen, setIsOpen] = useState(() => {
    const stored = localStorage.getItem('brubru_eu_today_open');
    return stored !== 'false';
  });

  useEffect(() => {
    if (isAuthenticated) fetchTodayDigest();
  }, [fetchTodayDigest, isAuthenticated]);

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
          <h3 className="eu-calendar-tab__digest-title">{t('calendar.myEuToday')}</h3>
          <span className="eu-calendar-tab__digest-badge">
            {t('calendarTab.events', { count: today_count })}
          </span>
        </div>
        <button
          className={`eu-calendar-tab__digest-toggle ${isOpen ? 'eu-calendar-tab__digest-toggle--open' : ''}`}
          aria-label={isOpen ? t('calendarTab.collapseDigest') : t('calendarTab.expandDigest')}
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
              {t('calendarTab.noEventsToday')}
            </div>
          )}

          {tomorrow_count > 0 && (
            <div className="eu-calendar-tab__digest-tomorrow">
              {tomorrow_count === 1 ? t('calendarTab.tomorrow', { count: tomorrow_count }) : t('calendarTab.tomorrowPlural', { count: tomorrow_count })}
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
  const { t, i18n } = useTranslation();
  const {
    viewMode, setViewMode, currentDate, navigateDate,
    searchQuery, setSearchQuery,
  } = useEUCalendar();
  const loc = i18n.language || 'en-GB';

  const viewModes: { mode: ViewMode; label: string; icon: string }[] = [
    { mode: 'month', label: t('calendarTab.month'), icon: mdiCalendarMonth },
    { mode: 'week', label: t('calendarTab.week'), icon: mdiCalendarWeek },
    { mode: 'day', label: t('calendarTab.day'), icon: mdiCalendarToday },
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
        return `${monday.toLocaleDateString(loc, { day: 'numeric', month: 'short' })} \u2013 ${sunday.toLocaleDateString(loc, { day: 'numeric', month: 'short', year: 'numeric' })}`;
      }
      case 'day':
        opts.weekday = 'long';
        opts.day = 'numeric';
        opts.month = 'long';
        opts.year = 'numeric';
        break;
    }
    return currentDate.toLocaleDateString(loc, opts);
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
            aria-label={t('calendarTab.previous')}
          >
            <Icon path={mdiChevronLeft} size={0.8} />
          </button>
          <button
            className="eu-calendar-tab__today-btn"
            onClick={() => navigateDate('today')}
          >
            {t('calendarTab.todayBtn')}
          </button>
          <button
            className="eu-calendar-tab__nav-btn"
            onClick={() => navigateDate('next')}
            aria-label={t('calendarTab.next')}
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
            placeholder={t('calendar.searchEvents')}
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
  const { t } = useTranslation();
  const {
    selectedInstitution, setInstitution,
    selectedDepartment, setDepartment,
    selectedPolicyArea, setPolicyArea,
    selectedEventType, setEventType,
    bodies, fetchBodies,
    myInterests, setMyInterests,
    showArchived, setShowArchived,
    clearFilters,
  } = useEUCalendar();

  useEffect(() => {
    if (Object.keys(bodies).length === 0) fetchBodies();
  }, []);

  const hasFilters = !!selectedInstitution || !!selectedDepartment || !!selectedPolicyArea
    || !!selectedEventType || myInterests;

  // Institution options grouped: core institutions vs agencies & bodies.
  const coreInstitutions = PHASE1_INSTITUTIONS.filter((c) => CORE_INSTITUTIONS.includes(c));
  const bodyInstitutions = PHASE1_INSTITUTIONS.filter((c) => !CORE_INSTITUTIONS.includes(c));
  // Dependent department options for the chosen institution (committees / DGs / configs).
  const departments = (selectedInstitution && bodies[selectedInstitution]) || [];
  // Commission DGs split policy vs functional for tidy optgroups.
  const dgPolicy = departments.filter((d) => d.kind === 'policy');
  const dgFunctional = departments.filter((d) => d.kind === 'functional');
  const isCommission = selectedInstitution === 'COMMISSION';
  const isEP = selectedInstitution === 'EP';
  const deptLabelKey = isEP
    ? t('calendar.epBody', 'Body')
    : isCommission
      ? t('calendar.department', 'Department (DG)')
      : t('calendar.configuration', 'Configuration');

  return (
    <div className="eu-calendar-tab__filters">
      {/* PI lens: My interests | All (shared MEUB pattern). */}
      <div className="eu-calendar-tab__filter-row">
        <span className="eu-calendar-tab__filter-label">{t('calendar.show', 'Show')}</span>
        <div className="eu-calendar-tab__pi-toggle">
          <button className={!myInterests ? 'is-active' : ''} onClick={() => setMyInterests(false)}>
            {t('calendar.allEvents', 'All')}
          </button>
          <button className={myInterests ? 'is-active' : ''} onClick={() => setMyInterests(true)}>
            {t('calendar.myInterests', 'My interests')}
          </button>
        </div>
        {/* Archive lens: active calendar vs the events the user dismissed. */}
        <ArchiveToggle
          value={showArchived ? 'archived' : 'active'}
          onChange={(v) => setShowArchived(v === 'archived')}
        />
      </div>

      {/* Cascading dropdowns: Institution -> Department + Policy area. */}
      <div className="eu-calendar-tab__filter-row eu-calendar-tab__filter-row--dropdowns">
        <label className="eu-calendar-tab__dropdown">
          <span className="eu-calendar-tab__filter-label">{t('calendar.institution', 'Institution')}</span>
          <select value={selectedInstitution} onChange={(e) => setInstitution(e.target.value)}>
            <option value="">{t('calendar.allInstitutions', 'All institutions')}</option>
            <optgroup label={t('calendar.coreInstitutions', 'Core institutions')}>
              {coreInstitutions.map((code) => (
                <option key={code} value={code}>{INSTITUTION_CONFIG[code]?.label || code}</option>
              ))}
            </optgroup>
            <optgroup label={t('calendar.agenciesBodies', 'Agencies & bodies')}>
              {bodyInstitutions.map((code) => (
                <option key={code} value={code}>{INSTITUTION_CONFIG[code]?.label || code}</option>
              ))}
            </optgroup>
          </select>
        </label>

        {(departments.length > 0 || isEP) && (
          <label className="eu-calendar-tab__dropdown">
            <span className="eu-calendar-tab__filter-label">{deptLabelKey}</span>
            <select value={selectedDepartment} onChange={(e) => setDepartment(e.target.value)}>
              <option value="">{t('calendar.allDepartments', 'All')}</option>
              {isEP ? (
                <>
                  <optgroup label={t('calendar.committees', 'Committees')}>
                    {departments.map((d) => <option key={d.code} value={`committee:${d.code}`}>{d.code} — {d.name}</option>)}
                  </optgroup>
                  <optgroup label={t('calendar.delegations', 'Delegations')}>
                    {EP_DELEGATION_OPTIONS.map((o) => <option key={o.value} value={o.value}>{t('calendar.allDelegations', o.label)}</option>)}
                  </optgroup>
                  <optgroup label={t('calendar.politicalGroups', 'Political groups')}>
                    {EP_GROUP_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </optgroup>
                  <optgroup label={t('calendar.epOther', 'Other')}>
                    {EP_OTHER_OPTIONS.map((o) => {
                      const lbl = o.value === 'eventtype:plenary_session'
                        ? t('calendar.eventType.plenary_session', 'Plenary')
                        : t('calendar.eprsEvents', o.label);
                      return <option key={o.value} value={o.value}>{lbl}</option>;
                    })}
                  </optgroup>
                </>
              ) : isCommission ? (
                <>
                  <optgroup label={t('calendar.policyDgs', 'Policy DGs')}>
                    {dgPolicy.map((d) => <option key={d.code} value={d.code}>{d.code} — {d.name}</option>)}
                  </optgroup>
                  <optgroup label={t('calendar.functionalDgs', 'Functional DGs & departments')}>
                    {dgFunctional.map((d) => <option key={d.code} value={d.code}>{d.code} — {d.name}</option>)}
                  </optgroup>
                </>
              ) : (
                departments.map((d) => <option key={d.code} value={d.code}>{d.code} — {d.name}</option>)
              )}
            </select>
          </label>
        )}

        <label className="eu-calendar-tab__dropdown">
          <span className="eu-calendar-tab__filter-label">{t('calendar.policy')}</span>
          <select value={selectedPolicyArea} onChange={(e) => setPolicyArea(e.target.value)}>
            <option value="">{t('calendar.allPolicyAreas', 'All policy areas')}</option>
            {POLICY_AREA_CODES.map((code) => {
              const config = POLICY_AREA_CONFIG[code];
              if (!config) return null;
              return <option key={code} value={code}>{config.label}</option>;
            })}
          </select>
        </label>

        <label className="eu-calendar-tab__dropdown">
          <span className="eu-calendar-tab__filter-label">{t('calendar.eventTypeLabel', 'Type')}</span>
          <select value={selectedEventType} onChange={(e) => setEventType(e.target.value)}>
            <option value="">{t('calendar.allEventTypes', 'All types')}</option>
            {FILTERABLE_EVENT_TYPES.map((code) => (
              <option key={code} value={code}>{t(`calendar.eventType.${code}`, code)}</option>
            ))}
          </select>
        </label>

        {hasFilters && (
          <button className="eu-calendar-tab__clear-filters" onClick={clearFilters}>
            <Icon path={mdiClose} size={0.5} />
            {t('calendarTab.clearAllFilters')}
          </button>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Month View
// ============================================================================

function MonthView() {
  const { t } = useTranslation();
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
        {WD_KEYS.map((wk) => (
          <div key={wk} className="eu-calendar-tab__month-header">{t('calendar.wd.' + wk)}</div>
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
  const { t } = useTranslation();
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
                {t('calendar.wd.' + WD_KEYS[day.date.getDay() === 0 ? 6 : day.date.getDay() - 1])}
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
  const { t } = useTranslation();
  const { events, selectEvent } = useEUCalendar();

  if (events.length === 0) {
    return (
      <div className="eu-calendar-tab__empty">
        <Icon path={mdiCalendarToday} size={2} color="#d1d5db" />
        <div className="eu-calendar-tab__empty-text">{t('calendar.noEventsOnDay')}</div>
        <div className="eu-calendar-tab__empty-hint">{t('calendar.tryAnotherDate')}</div>
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
              {event.all_day ? t('calendar.allDay', 'All day') : formatCalendarTime(event.start_time) || ''}
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
  const { t } = useTranslation();
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
                    {event.all_day ? t('calendar.allDay', 'All day') : formatCalendarTime(event.start_time) || ''}
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
  const { t } = useTranslation();
  const { selectedEvent, selectEvent, showArchived, fetchEvents } = useEUCalendar();
  const navigate = useNavigate();
  const [archiveBusy, setArchiveBusy] = useState(false);

  const handleClose = useCallback(() => {
    selectEvent(null);
  }, [selectEvent]);

  const handleArchiveEvent = useCallback(async () => {
    if (!selectedEvent) return;
    setArchiveBusy(true);
    try {
      if (showArchived) {
        await archiveService.restoreCalendar(selectedEvent.id);
        toast(t('archive.restored', 'Restored'), 'success');
      } else {
        await archiveService.archiveCalendar(selectedEvent.id);
        toast(t('archive.archivedToast', 'Archived'), 'success');
      }
      selectEvent(null);
      await fetchEvents();
    } catch {
      toast(t('archive.failed', 'Action failed. Please try again.'), 'error');
    } finally {
      setArchiveBusy(false);
    }
  }, [selectedEvent, showArchived, selectEvent, fetchEvents, t]);

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
              <h4 className="eu-calendar-tab__modal-procedures-title">{t('calendar.relatedProcedures')}</h4>
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
          <AddToCalendar event={event} />
          <ArchiveButton
            archived={showArchived}
            onClick={handleArchiveEvent}
            busy={archiveBusy}
            variant="full"
            className="eu-calendar-tab__modal-link-btn"
          />
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

// "Add to calendar" control: Google / Outlook deep-links + a downloadable .ics
// (Apple Calendar, Outlook desktop, any client). All client-side.
function AddToCalendar({ event }: { event: CalendarEvent }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <div className="eu-calendar-tab__addcal">
      <button
        type="button"
        className="eu-calendar-tab__modal-link-btn eu-calendar-tab__modal-link-btn--primary"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <Icon path={mdiCalendarPlus} size={0.7} />
        {t('calendar.addToCalendar', 'Add to calendar')}
        <Icon path={mdiChevronDown} size={0.6} />
      </button>
      {open && (
        <div className="eu-calendar-tab__addcal-menu" role="menu">
          <a href={googleCalendarUrl(event)} target="_blank" rel="noopener noreferrer"
            role="menuitem" onClick={() => setOpen(false)}>
            <Icon path={mdiCalendarPlus} size={0.65} /> {t('calendar.addGoogle', 'Google Calendar')}
          </a>
          <a href={outlookCalendarUrl(event)} target="_blank" rel="noopener noreferrer"
            role="menuitem" onClick={() => setOpen(false)}>
            <Icon path={mdiCalendarPlus} size={0.65} /> {t('calendar.addOutlook', 'Outlook')}
          </a>
          <button type="button" role="menuitem"
            onClick={() => { downloadIcs([event], `brubru-${event.id}.ics`); setOpen(false); }}>
            <Icon path={mdiDownloadOutline} size={0.65} /> {t('calendar.downloadIcs', 'Download .ics (Apple, other)')}
          </button>
        </div>
      )}
    </div>
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

// Module-level guard so we only reset filters on the FIRST visit to the
// Calendar tab per page load. Subsequent re-mounts (e.g. the user toggled
// to a different sub-tab and came back) preserve any filters they set.
let _calendarFiltersResetForSession = false;

export const EUCalendarTab = () => {
  const { t } = useTranslation();
  const { viewMode, isLoading, fetchEvents, clearFilters, goToDate } = useEUCalendar();
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const [searchParams, setSearchParams] = useSearchParams();
  const jumpTo = searchParams.get('date');

  useEffect(() => {
    // Wait for auth to hydrate from localStorage before fetching.
    if (!isAuthenticated) return;
    // A pending ?date= jump does its own fetch for the target day. Fetching
    // the default month here as well would resolve second and replace it.
    if (jumpTo) return;
    if (!_calendarFiltersResetForSession) {
      _calendarFiltersResetForSession = true;
      // clearFilters() already triggers fetchEvents internally.
      clearFilters();
    } else {
      fetchEvents();
    }
  }, [fetchEvents, clearFilters, isAuthenticated, jumpTo]);

  // A ?date= deep link (from a file's meeting list) opens that day. The
  // parameter is consumed once so that later navigation inside the calendar
  // is not yanked back to it.
  useEffect(() => {
    if (!jumpTo || !isAuthenticated) return;
    const target = new Date(`${jumpTo}T12:00:00`);
    if (Number.isNaN(target.getTime())) return;
    _calendarFiltersResetForSession = true;
    // goToDate already switches to the day view and refetches; calling
    // setViewMode as well fires a second, racing fetch pinned to today.
    goToDate(target);
    const next = new URLSearchParams(searchParams);
    next.delete('date');
    setSearchParams(next, { replace: true });
  }, [jumpTo, isAuthenticated]);

  const renderView = () => {
    if (isLoading) {
      return (
        <div className="eu-calendar-tab__skeleton">
          <div className="eu-calendar-tab__skeleton-header">
            {WD_KEYS.map((wk) => (
              <div key={wk} className="eu-calendar-tab__skeleton-weekday">{t('calendar.wd.' + wk)}</div>
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
      <MeubHeader
        icon={mdiCalendarMonth}
        title={t('calendar.title', 'My EU Calendar')}
        subtitle={t('calendar.intro', 'Every EU institutional date in one place — plenary sittings, Council meetings, committee hearings and consultation deadlines — filtered to your interests. Click any event for details, or add it to your own calendar.')}
      />
      <MyEUTodayDigest />
      <CalendarToolbar />
      <CalendarFilters />
      {renderView()}
      <EventDetailModal />
    </div>
  );
};

export default EUCalendarTab;
