// frontend/src/components/tenders/tender_calendar.tsx
import { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import type { Tender, TenderMatch, TenderProfile } from '../../pages/tenderator_page';
import { useAuth } from '../../hooks/use_auth';
import './tender_calendar.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface TenderCalendarProps {
  onSelectTender: (tender: Tender, match?: TenderMatch) => void;
  userProfile: TenderProfile | null;
}

export const TenderCalendar = ({ onSelectTender, userProfile: _userProfile }: TenderCalendarProps) => {
  const { token } = useAuth();
  const { t } = useTranslation();
  const [currentDate, setCurrentDate] = useState(new Date());
  const [matches, setMatches] = useState<TenderMatch[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [viewMode, setViewMode] = useState<'month' | 'list'>('month');
  const [selectedDayMatches, setSelectedDayMatches] = useState<TenderMatch[] | null>(null);
  const [selectedDayDate, setSelectedDayDate] = useState<string>('');

  // Phase 2 calendar: pull deadlines from all 3 live sources (TED, F&T
  // calls for proposals, F&T calls for tenders) via the unified endpoint.
  useEffect(() => {
    const fetchDeadlines = async () => {
      setIsLoading(true);
      try {
        const res = await fetch(`${API_URL}/api/tenders/calendar-deadlines?months_ahead=6`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (!res.ok) {
          console.error('[tender-calendar] Failed to fetch deadlines:', res.status);
          setIsLoading(false);
          return;
        }
        const data = await res.json();
        // Map every deadline to a TenderMatch-shaped row so the existing
        // render code keeps working. F&T items synthesise an id of 0 (a
        // sentinel meaning "no persisted match row").
        const mapped: TenderMatch[] = (data.items || []).map((item: any, idx: number) => {
          const idNum = item.source === 'ted' && /^ted:\d+$/.test(item.id)
            ? Number(item.id.split(':')[1])
            : -1 - idx; // negative ids for F&T (won't clash with real tenders.id)
          const pseudoTender: Tender = {
            id: idNum,
            publication_number: item.ref || item.id,
            title: item.title,
            buyer_name: '',
            buyer_country: item.country || '',
            estimated_value: item.budget,
            currency: item.currency || 'EUR',
            cpv_main: '',
            cpv_codes: [],
            procedure_type: '',
            submission_deadline: item.deadline,
            publication_date: '',
            status: 'open',
            sme_suitability_score: null,
            ted_url: item.source_url,
          };
          return {
            id: -1 - idx,
            tender_id: idNum,
            user_id: '',
            match_score: 0,
            match_reasons: [item.source, item.programme].filter(Boolean) as string[],
            match_details: null,
            is_viewed: false,
            is_saved: false,
            is_dismissed: false,
            is_applied: false,
            user_notes: null,
            user_rating: null,
            created_at: '',
            tender: pseudoTender,
          } as TenderMatch;
        });
        setMatches(mapped);
      } catch (err) {
        console.error('[tender-calendar] Failed to fetch deadlines:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchDeadlines();
  }, [token]);

  // Calendar helpers
  const getDaysInMonth = (year: number, month: number) => {
    return new Date(year, month + 1, 0).getDate();
  };

  const getFirstDayOfMonth = (year: number, month: number) => {
    return new Date(year, month, 1).getDay();
  };

  const formatDateKey = (date: Date) => {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  };

  // Group matches by deadline date
  const matchesByDate = useMemo(() => {
    const grouped: Record<string, TenderMatch[]> = {};

    matches.forEach((match) => {
      if (match.tender.submission_deadline) {
        const date = new Date(match.tender.submission_deadline);
        const key = formatDateKey(date);
        if (!grouped[key]) {
          grouped[key] = [];
        }
        grouped[key].push(match);
      }
    });

    return grouped;
  }, [matches]);

  // Get upcoming deadlines for list view
  const upcomingDeadlines = useMemo(() => {
    const now = new Date();
    return matches
      .filter((m) => {
        if (!m.tender.submission_deadline) return false;
        const deadline = new Date(m.tender.submission_deadline);
        return deadline >= now;
      })
      .sort((a, b) => {
        const dateA = new Date(a.tender.submission_deadline!);
        const dateB = new Date(b.tender.submission_deadline!);
        return dateA.getTime() - dateB.getTime();
      })
      .slice(0, 20);
  }, [matches]);

  // Calendar navigation
  const goToPreviousMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1, 1));
  };

  const goToNextMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1));
  };

  const goToToday = () => {
    setCurrentDate(new Date());
  };

  const handleDayClick = (dayMatches: TenderMatch[], dateStr: string) => {
    if (dayMatches.length > 0) {
      setSelectedDayMatches(dayMatches);
      setSelectedDayDate(dateStr);
    }
  };

  const closeDayPopup = () => {
    setSelectedDayMatches(null);
    setSelectedDayDate('');
  };

  // Render calendar
  const renderCalendar = () => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const daysInMonth = getDaysInMonth(year, month);
    const firstDay = getFirstDayOfMonth(year, month);
    const today = new Date();
    const todayKey = formatDateKey(today);

    const days = [];

    // Empty cells for days before the first day of the month
    for (let i = 0; i < firstDay; i++) {
      days.push(<div key={`empty-${i}`} className="tender-calendar__day tender-calendar__day--empty"></div>);
    }

    // Days of the month
    for (let day = 1; day <= daysInMonth; day++) {
      const date = new Date(year, month, day);
      const dateKey = formatDateKey(date);
      const dayMatches = matchesByDate[dateKey] || [];
      const isToday = dateKey === todayKey;
      const isPast = date < today && !isToday;

      days.push(
        <div
          key={`day-${day}`}
          className={`tender-calendar__day ${isToday ? 'tender-calendar__day--today' : ''} ${isPast ? 'tender-calendar__day--past' : ''} ${dayMatches.length > 0 ? 'tender-calendar__day--has-deadlines' : ''}`}
          onClick={() => handleDayClick(dayMatches, date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }))}
        >
          <span className="tender-calendar__day-number">{day}</span>
          {dayMatches.length > 0 && (
            <div className="tender-calendar__day-deadlines">
              {dayMatches.slice(0, 3).map((match) => (
                <button
                  key={match.id}
                  className="tender-calendar__deadline-item"
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectTender(match.tender, match);
                  }}
                  title={match.tender.title}
                >
                  <span className="tender-calendar__deadline-dot"></span>
                  <span className="tender-calendar__deadline-title">
                    {match.tender.title.length > 20
                      ? match.tender.title.substring(0, 20) + '...'
                      : match.tender.title}
                  </span>
                </button>
              ))}
              {dayMatches.length > 3 && (
                <span className="tender-calendar__more-deadlines">
                  +{dayMatches.length - 3} {t('tenderator.calendar.more')}
                </span>
              )}
            </div>
          )}
        </div>
      );
    }

    return <>{days}</>;
  };

  const getDaysUntil = (deadline: string) => {
    const now = new Date();
    const deadlineDate = new Date(deadline);
    const diffTime = deadlineDate.getTime() - now.getTime();
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  };

  const getUrgencyClass = (daysUntil: number) => {
    if (daysUntil <= 7) return 'tender-calendar__list-item--urgent';
    if (daysUntil <= 14) return 'tender-calendar__list-item--soon';
    return '';
  };

  return (
    <div className="tender-calendar">
      {/* Header */}
      <div className="tender-calendar__header">
        <h2>
          <span className="mdi mdi-calendar-clock"></span>
          {t('tenderator.calendar.title')}
        </h2>
        <div className="tender-calendar__view-toggle">
          <button
            className={`tender-calendar__view-btn ${viewMode === 'month' ? 'tender-calendar__view-btn--active' : ''}`}
            onClick={() => setViewMode('month')}
            title={t('tenderator.calendar.monthView')}
          >
            <span className="mdi mdi-calendar-month"></span>
            {t('tenderator.calendar.monthView')}
          </button>
          <button
            className={`tender-calendar__view-btn ${viewMode === 'list' ? 'tender-calendar__view-btn--active' : ''}`}
            onClick={() => setViewMode('list')}
            title={t('tenderator.calendar.listView')}
          >
            <span className="mdi mdi-format-list-bulleted"></span>
            {t('tenderator.calendar.listView')}
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="tender-calendar__loading">
          <span className="mdi mdi-loading mdi-spin"></span>
          {t('tenderator.calendar.loading')}
        </div>
      ) : viewMode === 'month' ? (
        /* Month View */
        <div className="tender-calendar__month-view">
          {/* Navigation */}
          <div className="tender-calendar__nav">
            <button className="tender-calendar__nav-btn" onClick={goToPreviousMonth}>
              <span className="mdi mdi-chevron-left"></span>
            </button>
            <h3 className="tender-calendar__month-title">
              {currentDate.toLocaleDateString('en-EU', { month: 'long', year: 'numeric' })}
            </h3>
            <button className="tender-calendar__nav-btn" onClick={goToNextMonth}>
              <span className="mdi mdi-chevron-right"></span>
            </button>
            <button className="tender-calendar__today-btn" onClick={goToToday}>
              {t('tenderator.calendar.today')}
            </button>
          </div>

          {/* Weekday Headers */}
          <div className="tender-calendar__weekdays">
            {[
              t('common.dayOfWeek.sun'),
              t('common.dayOfWeek.mon'),
              t('common.dayOfWeek.tue'),
              t('common.dayOfWeek.wed'),
              t('common.dayOfWeek.thu'),
              t('common.dayOfWeek.fri'),
              t('common.dayOfWeek.sat'),
            ].map((day, idx) => (
              <div key={idx} className="tender-calendar__weekday">{day}</div>
            ))}
          </div>

          {/* Calendar Grid */}
          <div className="tender-calendar__grid">
            {renderCalendar()}
          </div>

          {/* Legend */}
          <div className="tender-calendar__legend">
            <div className="tender-calendar__legend-item">
              <span className="tender-calendar__legend-dot tender-calendar__legend-dot--deadline"></span>
              <span>{t('tenderator.calendar.submissionDeadline')}</span>
            </div>
            <div className="tender-calendar__legend-item">
              <span className="tender-calendar__legend-dot tender-calendar__legend-dot--today"></span>
              <span>{t('tenderator.calendar.today')}</span>
            </div>
          </div>
        </div>
      ) : (
        /* List View */
        <div className="tender-calendar__list-view">
          {upcomingDeadlines.length === 0 ? (
            <div className="tender-calendar__empty">
              <span className="mdi mdi-calendar-blank"></span>
              <p>{t('tenderator.calendar.noUpcomingDeadlines')}</p>
              <p className="tender-calendar__empty-hint">
                {t('tenderator.calendar.emptyHint')}
              </p>
            </div>
          ) : (
            <div className="tender-calendar__list">
              {upcomingDeadlines.map((match) => {
                const daysUntil = getDaysUntil(match.tender.submission_deadline!);

                return (
                  <div
                    key={match.id}
                    className={`tender-calendar__list-item ${getUrgencyClass(daysUntil)}`}
                    onClick={() => onSelectTender(match.tender, match)}
                  >
                    <div className="tender-calendar__list-date">
                      <span className="tender-calendar__list-day">
                        {new Date(match.tender.submission_deadline!).getDate()}
                      </span>
                      <span className="tender-calendar__list-month">
                        {new Date(match.tender.submission_deadline!).toLocaleDateString('en-EU', { month: 'short' })}
                      </span>
                    </div>
                    <div className="tender-calendar__list-content">
                      <h4 className="tender-calendar__list-title">{match.tender.title}</h4>
                      <div className="tender-calendar__list-meta">
                        <span>
                          <span className="mdi mdi-domain"></span>
                          {match.tender.buyer_name}
                        </span>
                        <span>
                          <span className="mdi mdi-map-marker"></span>
                          {match.tender.buyer_country}
                        </span>
                        {match.match_score && (
                          <span className="tender-calendar__list-score">
                            <span className="mdi mdi-target"></span>
                            {Math.round(match.match_score)}% {t('tenderator.calendar.match')}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="tender-calendar__list-countdown">
                      {daysUntil === 0 ? (
                        <span className="tender-calendar__countdown-urgent">{t('tenderator.calendar.dueToday')}</span>
                      ) : daysUntil === 1 ? (
                        <span className="tender-calendar__countdown-urgent">{t('tenderator.calendar.tomorrow')}</span>
                      ) : daysUntil < 0 ? (
                        <span className="tender-calendar__countdown-expired">{t('tenderator.calendar.expired')}</span>
                      ) : (
                        <>
                          <span className="tender-calendar__countdown-number">{daysUntil}</span>
                          <span className="tender-calendar__countdown-label">{t('tenderator.calendar.daysLeft')}</span>
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Mobile Day Popup */}
      {selectedDayMatches && (
        <div className="tender-calendar__day-popup-overlay" onClick={closeDayPopup}>
          <div className="tender-calendar__day-popup" onClick={(e) => e.stopPropagation()}>
            <div className="tender-calendar__day-popup-header">
              <h3>{t('tenderator.calendar.deadlinesFor')} {selectedDayDate}</h3>
              <button className="tender-calendar__day-popup-close" onClick={closeDayPopup} aria-label={t('common.close')}>
                <span className="mdi mdi-close"></span>
              </button>
            </div>
            <div className="tender-calendar__day-popup-list">
              {selectedDayMatches.map((match) => (
                <div
                  key={match.id}
                  className="tender-calendar__day-popup-item"
                  onClick={() => {
                    closeDayPopup();
                    onSelectTender(match.tender, match);
                  }}
                >
                  <div className="tender-calendar__day-popup-item-dot"></div>
                  <div className="tender-calendar__day-popup-item-content">
                    <h4>{match.tender.title}</h4>
                    <p>{match.tender.buyer_name} • {match.tender.buyer_country}</p>
                  </div>
                  <span className="mdi mdi-chevron-right"></span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
