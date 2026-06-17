// frontend/src/components/tenders/tender_stats.tsx
import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation();
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
        {t('tenderator.stats.yourStatistics')}
      </h3>

      <div className="tender-stats__cards">
        {/* Total Matches */}
        <div className="tender-stats__card">
          <div className="tender-stats__card-icon tender-stats__card-icon--primary">
            <span className="mdi mdi-target"></span>
          </div>
          <div className="tender-stats__card-content">
            <span className="tender-stats__card-value">{stats.total_matches}</span>
            <span className="tender-stats__card-label">{t('tenderator.stats.totalMatches')}</span>
          </div>
        </div>

        {/* Matches This Week */}
        <div className="tender-stats__card">
          <div className="tender-stats__card-icon tender-stats__card-icon--success">
            <span className="mdi mdi-calendar-week"></span>
          </div>
          <div className="tender-stats__card-content">
            <span className="tender-stats__card-value">{stats.matches_this_week}</span>
            <span className="tender-stats__card-label">{t('tenderator.stats.thisWeek')}</span>
          </div>
        </div>

        {/* Saved Tenders */}
        <div className="tender-stats__card">
          <div className="tender-stats__card-icon tender-stats__card-icon--info">
            <span className="mdi mdi-bookmark"></span>
          </div>
          <div className="tender-stats__card-content">
            <span className="tender-stats__card-value">{stats.saved_tenders}</span>
            <span className="tender-stats__card-label">{t('tenderator.stats.saved')}</span>
          </div>
        </div>

        {/* Applied */}
        <div className="tender-stats__card">
          <div className="tender-stats__card-icon tender-stats__card-icon--warning">
            <span className="mdi mdi-send"></span>
          </div>
          <div className="tender-stats__card-content">
            <span className="tender-stats__card-value">{stats.applied_tenders}</span>
            <span className="tender-stats__card-label">{t('tenderator.stats.applied')}</span>
          </div>
        </div>
      </div>

      {/* Average Match Score */}
      <div className="tender-stats__score-section">
        <h4>{t('tenderator.stats.averageMatchScore')}</h4>
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
          <p className="tender-stats__no-data">{t('tenderator.stats.noMatchesYet')}</p>
        )}
      </div>

      {/* EU Industrial Ecosystems (DG GROW / EMI) */}
      {ecosystems.length > 0 && (
        <div className="tender-stats__ecosystems">
          <h4>
            <span className="mdi mdi-factory"></span>
            {t('tenderator.stats.euIndustrialEcosystems')}
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
            {t('tenderator.stats.sourceEmi')}
          </p>
        </div>
      )}

      {/* Quick Tips */}
      <div className="tender-stats__tips">
        <h4>
          <span className="mdi mdi-lightbulb-on-outline"></span>
          {t('tenderator.stats.quickTips')}
        </h4>
        <ul>
          <li>
            <span className="mdi mdi-check-circle"></span>
            {t('tenderator.stats.tipReviewWeekly')}
          </li>
          <li>
            <span className="mdi mdi-check-circle"></span>
            {t('tenderator.stats.tipSaveInteresting')}
          </li>
          <li>
            <span className="mdi mdi-check-circle"></span>
            {t('tenderator.stats.tipBidPrep')}
          </li>
          <li>
            <span className="mdi mdi-check-circle"></span>
            {t('tenderator.stats.tipUseAiAssistant')}
          </li>
        </ul>
      </div>
    </div>
  );
};
