// frontend/src/components/bubble/tenderator_widget.tsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/use_auth';
import './tenderator_widget.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface TenderMatch {
  id: number;
  tender: {
    id: number;
    title: string;
    buyer_country: string;
    estimated_value: number | null;
    currency: string;
    submission_deadline: string | null;
  };
  match_score: number;
}

interface TenderStats {
  total_matches: number;
  saved_tenders: number;
  matches_this_week: number;
}

export const TenderatorWidget = () => {
  const navigate = useNavigate();
  const { token, isAuthenticated } = useAuth();
  const [matches, setMatches] = useState<TenderMatch[]>([]);
  const [stats, setStats] = useState<TenderStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [hasAccess, setHasAccess] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // If not authenticated, don't make requests
        if (!isAuthenticated || !token) {
          setHasAccess(false);
          setIsLoading(false);
          return;
        }

        const headers = { 'Authorization': `Bearer ${token}` };

        // Fetch recent matches
        const matchesRes = await fetch(`${API_URL}/api/tenders/matches?page_size=3`, { headers });
        if (matchesRes.status === 401 || matchesRes.status === 403) {
          setHasAccess(false);
          setIsLoading(false);
          return;
        }
        if (matchesRes.ok) {
          const data = await matchesRes.json();
          setMatches(data.matches || []);
        }

        // Fetch stats
        const statsRes = await fetch(`${API_URL}/api/tenders/statistics/me`, { headers });
        if (statsRes.ok) {
          const data = await statsRes.json();
          setStats(data);
        }
      } catch (err) {
        console.error('Failed to fetch tenderator data:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [token, isAuthenticated]);

  const formatValue = (value: number | null, currency: string): string => {
    if (!value) return '-';
    return new Intl.NumberFormat('en-EU', {
      style: 'currency',
      currency: currency || 'EUR',
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(value);
  };

  const getDaysUntil = (deadline: string | null): string => {
    if (!deadline) return '-';
    const now = new Date();
    const deadlineDate = new Date(deadline);
    const days = Math.ceil((deadlineDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    if (days < 0) return 'Expired';
    if (days === 0) return 'Today';
    if (days === 1) return 'Tomorrow';
    return `${days}d`;
  };

  // No access - show upgrade prompt
  if (!hasAccess) {
    return (
      <div className="tenderator-widget tenderator-widget--locked">
        <div className="tenderator-widget__header">
          <span className="mdi mdi-gavel"></span>
          <h4>Tenderator</h4>
          <span className="tenderator-widget__badge tenderator-widget__badge--blue">Blue</span>
        </div>
        <div className="tenderator-widget__locked-content">
          <span className="mdi mdi-lock-outline"></span>
          <p>EU Tender Monitoring</p>
          <button onClick={() => navigate('/subscription')}>
            Get Professional
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="tenderator-widget">
      <div className="tenderator-widget__header">
        <span className="mdi mdi-gavel"></span>
        <h4>Tenderator</h4>
        <button
          className="tenderator-widget__view-all"
          onClick={() => navigate('/tenderator')}
        >
          View All
          <span className="mdi mdi-arrow-right"></span>
        </button>
      </div>

      {isLoading ? (
        <div className="tenderator-widget__loading">
          <span className="mdi mdi-loading mdi-spin"></span>
        </div>
      ) : (
        <>
          {/* Quick Stats */}
          {stats && (
            <div className="tenderator-widget__stats">
              <div className="tenderator-widget__stat">
                <span className="tenderator-widget__stat-value">{stats.total_matches}</span>
                <span className="tenderator-widget__stat-label">Matches</span>
              </div>
              <div className="tenderator-widget__stat">
                <span className="tenderator-widget__stat-value">{stats.matches_this_week}</span>
                <span className="tenderator-widget__stat-label">This Week</span>
              </div>
              <div className="tenderator-widget__stat">
                <span className="tenderator-widget__stat-value">{stats.saved_tenders}</span>
                <span className="tenderator-widget__stat-label">Saved</span>
              </div>
            </div>
          )}

          {/* Recent Matches */}
          <div className="tenderator-widget__matches">
            {matches.length === 0 ? (
              <div className="tenderator-widget__empty">
                <p>No matches yet</p>
                <button onClick={() => navigate('/tenderator')}>
                  Set up profile
                </button>
              </div>
            ) : (
              matches.map((match) => (
                <div
                  key={match.id}
                  className="tenderator-widget__match"
                  onClick={() => navigate('/tenderator')}
                >
                  <div className="tenderator-widget__match-header">
                    <span className="tenderator-widget__match-country">{match.tender.buyer_country}</span>
                    <span className="tenderator-widget__match-score">{Math.round(match.match_score)}%</span>
                  </div>
                  <p className="tenderator-widget__match-title">{match.tender.title}</p>
                  <div className="tenderator-widget__match-meta">
                    <span>{formatValue(match.tender.estimated_value, match.tender.currency)}</span>
                    <span className={getDaysUntil(match.tender.submission_deadline) === 'Expired' ? 'expired' : ''}>
                      {getDaysUntil(match.tender.submission_deadline)}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
};
