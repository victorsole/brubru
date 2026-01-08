// frontend/src/components/tenders/tender_calendar.tsx
import { useState, useEffect, useMemo } from 'react';
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
  const [currentDate, setCurrentDate] = useState(new Date());
  const [matches, setMatches] = useState<TenderMatch[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [viewMode, setViewMode] = useState<'month' | 'list'>('month');
  const [selectedDayMatches, setSelectedDayMatches] = useState<TenderMatch[] | null>(null);
  const [selectedDayDate, setSelectedDayDate] = useState<string>('');

  // Fetch user matches with deadlines, or all tenders if no profile
  useEffect(() => {
    const fetchTenders = async () => {
      setIsLoading(true);
      try {
        // First try to get matched tenders
        const matchResponse = await fetch(`${API_URL}/api/tenders/matches?page_size=100`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });

        if (matchResponse.ok) {
          const data = await matchResponse.json();
          const matchesWithDeadlines = data.matches.filter(
            (m: TenderMatch) => m.tender.submission_deadline
          );

          if (matchesWithDeadlines.length > 0) {
            setMatches(matchesWithDeadlines);
            setIsLoading(false);
            return;
          }
        }

        // If no matches or no profile, fetch all tenders
        const allTendersResponse = await fetch(`${API_URL}/api/tenders/?page=1&page_size=100`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });

        if (allTendersResponse.ok) {
          const data = await allTendersResponse.json();
          // Convert tenders to match format for calendar display
          const pseudoMatches = data.tenders
            .filter((t: Tender) => t.submission_deadline)
            .map((t: Tender) => ({
              tender: t,
              match_score: 0,
              score_breakdown: {},
            }));
          setMatches(pseudoMatches);
        }
      } catch (err) {
        console.error('Failed to fetch tenders:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchTenders();
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
                  +{dayMatches.length - 3} more
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
          Tender Deadlines
        </h2>
        <div className="tender-calendar__view-toggle">
          <button
            className={`tender-calendar__view-btn ${viewMode === 'month' ? 'tender-calendar__view-btn--active' : ''}`}
            onClick={() => setViewMode('month')}
          >
            <span className="mdi mdi-calendar-month"></span>
            Month
          </button>
          <button
            className={`tender-calendar__view-btn ${viewMode === 'list' ? 'tender-calendar__view-btn--active' : ''}`}
            onClick={() => setViewMode('list')}
          >
            <span className="mdi mdi-format-list-bulleted"></span>
            List
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="tender-calendar__loading">
          <span className="mdi mdi-loading mdi-spin"></span>
          Loading calendar...
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
              Today
            </button>
          </div>

          {/* Weekday Headers */}
          <div className="tender-calendar__weekdays">
            {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => (
              <div key={day} className="tender-calendar__weekday">{day}</div>
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
              <span>Submission deadline</span>
            </div>
            <div className="tender-calendar__legend-item">
              <span className="tender-calendar__legend-dot tender-calendar__legend-dot--today"></span>
              <span>Today</span>
            </div>
          </div>
        </div>
      ) : (
        /* List View */
        <div className="tender-calendar__list-view">
          {upcomingDeadlines.length === 0 ? (
            <div className="tender-calendar__empty">
              <span className="mdi mdi-calendar-blank"></span>
              <p>No upcoming deadlines found.</p>
              <p className="tender-calendar__empty-hint">
                Tenders matched to your profile will appear here.
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
                            {Math.round(match.match_score)}% match
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="tender-calendar__list-countdown">
                      {daysUntil === 0 ? (
                        <span className="tender-calendar__countdown-urgent">Due today!</span>
                      ) : daysUntil === 1 ? (
                        <span className="tender-calendar__countdown-urgent">Tomorrow</span>
                      ) : daysUntil < 0 ? (
                        <span className="tender-calendar__countdown-expired">Expired</span>
                      ) : (
                        <>
                          <span className="tender-calendar__countdown-number">{daysUntil}</span>
                          <span className="tender-calendar__countdown-label">days left</span>
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
              <h3>Deadlines for {selectedDayDate}</h3>
              <button className="tender-calendar__day-popup-close" onClick={closeDayPopup}>
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
