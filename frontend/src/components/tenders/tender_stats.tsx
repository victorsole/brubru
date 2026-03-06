// frontend/src/components/tenders/tender_stats.tsx
import { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/use_auth';
import type { UserTenderStats } from '../../pages/tenderator_page';
import './tender_stats.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface EcosystemInfo {
  ecosystem: string;
  cpv_categories: string[];
  indicators: string[];
}

interface TenderStatsProps {
  stats: UserTenderStats;
  cpvCode?: string;
}

export const TenderStats = ({ stats, cpvCode }: TenderStatsProps) => {
  const { token } = useAuth();
  const [ecosystems, setEcosystems] = useState<EcosystemInfo[]>([]);

  useEffect(() => {
    if (!cpvCode) return;
    const fetchEcosystems = async () => {
      try {
        const response = await fetch(
          `${API_URL}/api/dg-grow/ecosystems/for-cpv/${encodeURIComponent(cpvCode)}`,
          { headers: { 'Authorization': `Bearer ${token}` } },
        );
        if (response.ok) {
          const data = await response.json();
          if (data.ecosystems && data.ecosystems.length > 0) {
            setEcosystems(data.ecosystems);
          }
        }
      } catch (err) {
        console.error('Failed to fetch ecosystems:', err);
      }
    };
    fetchEcosystems();
  }, [cpvCode, token]);
  return (
    <div className="tender-stats">
      <h3 className="tender-stats__title">
        <span className="mdi mdi-chart-arc"></span>
        Your Statistics
      </h3>

      <div className="tender-stats__cards">
        {/* Total Matches */}
        <div className="tender-stats__card">
          <div className="tender-stats__card-icon tender-stats__card-icon--primary">
            <span className="mdi mdi-target"></span>
          </div>
          <div className="tender-stats__card-content">
            <span className="tender-stats__card-value">{stats.total_matches}</span>
            <span className="tender-stats__card-label">Total Matches</span>
          </div>
        </div>

        {/* Matches This Week */}
        <div className="tender-stats__card">
          <div className="tender-stats__card-icon tender-stats__card-icon--success">
            <span className="mdi mdi-calendar-week"></span>
          </div>
          <div className="tender-stats__card-content">
            <span className="tender-stats__card-value">{stats.matches_this_week}</span>
            <span className="tender-stats__card-label">This Week</span>
          </div>
        </div>

        {/* Saved Tenders */}
        <div className="tender-stats__card">
          <div className="tender-stats__card-icon tender-stats__card-icon--info">
            <span className="mdi mdi-bookmark"></span>
          </div>
          <div className="tender-stats__card-content">
            <span className="tender-stats__card-value">{stats.saved_tenders}</span>
            <span className="tender-stats__card-label">Saved</span>
          </div>
        </div>

        {/* Applied */}
        <div className="tender-stats__card">
          <div className="tender-stats__card-icon tender-stats__card-icon--warning">
            <span className="mdi mdi-send"></span>
          </div>
          <div className="tender-stats__card-content">
            <span className="tender-stats__card-value">{stats.applied_tenders}</span>
            <span className="tender-stats__card-label">Applied</span>
          </div>
        </div>
      </div>

      {/* Average Match Score */}
      <div className="tender-stats__score-section">
        <h4>Average Match Score</h4>
        {stats.average_match_score !== null ? (
          <>
            <div className="tender-stats__score-bar">
              <div
                className="tender-stats__score-fill"
                style={{ width: `${Math.min(stats.average_match_score, 100)}%` }}
              ></div>
            </div>
            <span className="tender-stats__score-value">
              {Math.round(stats.average_match_score)}%
            </span>
          </>
        ) : (
          <p className="tender-stats__no-data">No matches yet</p>
        )}
      </div>

      {/* EU Industrial Ecosystems (DG GROW / EMI) */}
      {ecosystems.length > 0 && (
        <div className="tender-stats__ecosystems">
          <h4>
            <span className="mdi mdi-factory"></span>
            EU Industrial Ecosystems
          </h4>
          <div className="tender-stats__eco-list">
            {ecosystems.map((eco, idx) => (
              <div key={idx} className="tender-stats__eco-card">
                <span className="tender-stats__eco-name">{eco.ecosystem}</span>
                {eco.indicators && eco.indicators.length > 0 && (
                  <div className="tender-stats__eco-dims">
                    {eco.indicators.slice(0, 3).map((ind, i) => (
                      <span key={i} className="tender-stats__eco-dim">{ind}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
          <p className="tender-stats__eco-note">
            Source: European Monitor of Industrial Ecosystems (EMI)
          </p>
        </div>
      )}

      {/* Quick Tips */}
      <div className="tender-stats__tips">
        <h4>
          <span className="mdi mdi-lightbulb-on-outline"></span>
          Quick Tips
        </h4>
        <ul>
          <li>
            <span className="mdi mdi-check-circle"></span>
            Review new matches weekly
          </li>
          <li>
            <span className="mdi mdi-check-circle"></span>
            Save interesting tenders for later
          </li>
          <li>
            <span className="mdi mdi-check-circle"></span>
            Start bid prep at least 30 days before deadline
          </li>
          <li>
            <span className="mdi mdi-check-circle"></span>
            Use the AI assistant for guidance
          </li>
        </ul>
      </div>
    </div>
  );
};
