// frontend/src/components/eu_comply/usage_history.tsx
import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../../hooks/use_auth';
import './usage_history.css';
import { uiDateLocale } from '../../i18n/config';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface ComplianceAnalysis {
  id: number;
  analysis_name: string;
  cluster_id: number;
  cluster_name?: string;
  compliance_score?: number;
  status: 'processing' | 'completed' | 'failed';
  started_at: string;
  completed_at?: string;
  requirements_met?: number;
  requirements_gap?: number;
  total_requirements?: number;
}

interface UsageHistoryProps {
  onSelectAnalysis: (analysisId: number) => void;
  selectedAnalysisId?: number;
}

export const UsageHistory = ({
  onSelectAnalysis,
  selectedAnalysisId,
}: UsageHistoryProps) => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [analyses, setAnalyses] = useState<ComplianceAnalysis[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/eu-law-comply/history`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        credentials: 'include',
      });

      if (!response.ok) {
        if (response.status === 401) {
          setError('Please log in to view your analysis history');
        } else {
          setError('Failed to fetch history');
        }
        setAnalyses([]); // Ensure it's an empty array, not undefined
        return;
      }

      const data = await response.json();
      setAnalyses(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Error fetching history:', err);
      setError('Failed to load history');
      setAnalyses([]); // Ensure it's always an array
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusClass = (status: ComplianceAnalysis['status']) => {
    switch (status) {
      case 'completed':
        return 'usage-history__status--completed';
      case 'processing':
        return 'usage-history__status--processing';
      case 'failed':
        return 'usage-history__status--failed';
      default:
        return '';
    }
  };

  const getStatusLabel = (status: ComplianceAnalysis['status']) => {
    switch (status) {
      case 'completed':
        return t('euLawComply.completed');
      case 'processing':
        return t('euLawComply.processing');
      case 'failed':
        return t('euLawComply.failed');
      default:
        return status;
    }
  };

  const getScoreClass = (score?: number) => {
    if (!score) return '';
    if (score >= 90) return 'usage-history__score--excellent';
    if (score >= 70) return 'usage-history__score--good';
    if (score >= 50) return 'usage-history__score--fair';
    return 'usage-history__score--poor';
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString(uiDateLocale(), {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  };

  const truncateText = (text: string, maxLength: number = 40) => {
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  };

  return (
    <div className="usage-history">
      <div className="usage-history__header">
        <h3 className="usage-history__title">{t('euLawComply.history')}</h3>
        <span className="usage-history__count">{analyses.length}</span>
      </div>

      {/* Brubru EU Law Comply Mascot */}
      <div className="usage-history__mascot">
        <img
          src="/assets/brubru_eulawcomply.png"
          alt="Brubru EU Law Comply"
          className="usage-history__mascot-image breathe"
        />
      </div>

      {isLoading ? (
        <div className="usage-history__loading">
          <div className="spinner"></div>
          <p>{t('euLawComply.loadingHistory')}</p>
        </div>
      ) : error ? (
        <div className="usage-history__error">
          <p>{error}</p>
          <button className="button button-sm" onClick={fetchHistory}>
            {t('euLawComply.retry')}
          </button>
        </div>
      ) : analyses.length === 0 ? (
        <div className="usage-history__empty">
          <p>{t('euLawComply.noAnalyses')}</p>
          <p className="usage-history__empty-hint">
            {t('euLawComply.runFirstAnalysis')}
          </p>
        </div>
      ) : (
        <div className="usage-history__list">
          {analyses.map((analysis) => (
            <div
              key={analysis.id}
              className={`usage-history__item ${
                analysis.id === selectedAnalysisId ? 'usage-history__item--selected' : ''
              }`}
              onClick={() => onSelectAnalysis(analysis.id)}
            >
              <div className="usage-history__item-header">
                <span className="usage-history__name">
                  {truncateText(analysis.analysis_name)}
                </span>
                <span className={`usage-history__status ${getStatusClass(analysis.status)}`}>
                  {getStatusLabel(analysis.status)}
                </span>
              </div>

              {/* Cluster Name */}
              {analysis.cluster_name && (
                <div className="usage-history__cluster">
                  {truncateText(analysis.cluster_name, 50)}
                </div>
              )}

              {/* Compliance Score (only for completed analyses) */}
              {analysis.status === 'completed' && analysis.compliance_score !== undefined && (
                <div className="usage-history__score-container">
                  <div className={`usage-history__score ${getScoreClass(analysis.compliance_score)}`}>
                    {analysis.compliance_score.toFixed(1)}%
                  </div>
                  {analysis.total_requirements && (
                    <div className="usage-history__breakdown">
                      <span className="usage-history__met">✓ {analysis.requirements_met || 0}</span>
                      <span className="usage-history__gap">✗ {analysis.requirements_gap || 0}</span>
                      <span className="usage-history__total">/ {analysis.total_requirements}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Date */}
              <span className="usage-history__date">
                {formatDate(analysis.started_at)}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="usage-history__actions">
        <button
          className="usage-history__refresh-button button button-sm button-secondary"
          onClick={fetchHistory}
          disabled={isLoading}
        >
          {isLoading ? t('euLawComply.refreshing') : t('euLawComply.refresh')}
        </button>
      </div>
    </div>
  );
};
