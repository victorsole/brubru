/**
 * Predictions Tab
 *
 * Main component for the Predictions tab in My EU Bubble.
 * Displays legislative predictions with confidence gauges, EP group breakdown,
 * timeline projections, and Council risk assessment.
 *
 * Follows the mockup design in docs/mockups/predictions-tab.html
 *
 * Access:
 * - White tier: Locked state (CTA to upgrade)
 * - Yellow tier: 3 predictions per month (quota indicator)
 * - Blue tier: Unlimited predictions
 *
 * Created: February 2026
 */

import React, { useEffect, useCallback, useState, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiCrystalBall,
  mdiCheckCircle,
  mdiCalendarClock,
  mdiVote,
  mdiShieldCheck,
  mdiChevronDown,
  mdiAccountGroup,
  mdiTimeline,
  mdiShieldAccount,
  mdiLightbulbOn,
  mdiCheck,
  mdiAccountVoice,
  mdiHandshake,
  mdiGavel,
  mdiBookOpenPageVariant,
  mdiAlertCircle,
  mdiFileDocumentCheck,
  mdiThumbUp,
  mdiThumbDown,
  mdiMinusCircle,
  mdiCheckDecagram,
  mdiLock,
  mdiStar,
  mdiInfinity,
  mdiOpenInNew,
  mdiScaleBalance,
  mdiInformationOutline,
} from '@mdi/js';

import { useAuth } from '../../hooks/use_auth';
import { MeubHeader } from './meub_header';
import { glossaryFor } from '../../utils/code_glossary';
import {
  usePredictions,
  EP_GROUPS,
} from '../../hooks/use_predictions';
import {
  formatConfidence,
  getConfidenceLevel,
  formatPredictedDate,
  getOutcomeLabel,
  getCouncilRiskLabel,
  calculateGaugeOffset,
  getResolutionLeadingIndicators,
  getCalibration,
  getInterestFiles,
  type PredictionSummary,
  type GroupPosition,
  type ResolutionLeadingIndicatorResponse,
  type ResolutionIndicator,
  type CalibrationResult,
  type PredictionPickerFile,
  type InterestFiles,
} from '../../services/prediction_service';
import './predictions_tab.css';

// ============================================================================
// Types
// ============================================================================

interface PredictionsTabProps {
  className?: string;
}

// ============================================================================
// Sub-components
// ============================================================================

/**
 * SVG Gradient definitions (shared across gauges)
 */
const GaugeSVGDefs: React.FC = () => (
  <svg width="0" height="0" style={{ position: 'absolute' }}>
    <defs>
      <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" style={{ stopColor: '#0693e3' }} />
        <stop offset="100%" style={{ stopColor: '#06b6d4' }} />
      </linearGradient>
    </defs>
  </svg>
);

/**
 * Confidence dots indicator
 */
const ConfidenceDots: React.FC<{ confidence: number }> = ({ confidence }) => {
  const level = getConfidenceLevel(confidence);
  const filledCount = Math.round(confidence * 5);

  return (
    <div className="prediction-card__metric-confidence">
      {[...Array(5)].map((_, i) => (
        <span
          key={i}
          className={`prediction-card__confidence-dot ${
            i < filledCount
              ? level === 'low'
                ? 'prediction-card__confidence-dot--medium'
                : 'prediction-card__confidence-dot--filled'
              : ''
          }`}
        />
      ))}
    </div>
  );
};

/**
 * Circular confidence gauge
 */
const ConfidenceGauge: React.FC<{ confidence: number }> = ({ confidence }) => {
  const offset = calculateGaugeOffset(confidence);

  return (
    <div className="prediction-card__gauge">
      <svg width="80" height="80" viewBox="0 0 100 100">
        <circle className="prediction-card__gauge-bg" cx="50" cy="50" r="45" />
        <circle
          className="prediction-card__gauge-fill"
          cx="50"
          cy="50"
          r="45"
          style={{ '--target-offset': offset } as React.CSSProperties}
        />
      </svg>
      <div className="prediction-card__gauge-value">
        {formatConfidence(confidence)}
      </div>
    </div>
  );
};

/**
 * EP Group breakdown row
 */
const EPGroupRow: React.FC<{
  groupCode: string;
  position: GroupPosition;
  confidence: number;
}> = ({ groupCode, position, confidence }) => {
  const group = EP_GROUPS.find((g) => g.code === groupCode);
  if (!group) return null;

  const percentage = Math.round(confidence * 100);

  return (
    <div className="prediction-card__ep-group">
      <div>
        <span className="prediction-card__ep-group-name">{group.name}</span>
        <span className="prediction-card__ep-group-seats">({group.seats})</span>
      </div>
      <div className="prediction-card__ep-group-bar">
        <div
          className={`prediction-card__ep-group-bar-fill prediction-card__ep-group-bar-fill--${position.toLowerCase()}`}
          style={{ '--target-width': `${percentage}%` } as React.CSSProperties}
        />
      </div>
      <span
        className={`prediction-card__ep-group-position prediction-card__ep-group-position--${position.toLowerCase()}`}
      >
        {position}
      </span>
      <span className="prediction-card__ep-group-percent">{percentage}%</span>
    </div>
  );
};

/**
 * Timeline stage
 */
const TimelineStage: React.FC<{
  label: string;
  date: string;
  icon: string;
  status: 'completed' | 'current' | 'pending';
}> = ({ label, date, icon, status }) => (
  <div
    className={`prediction-card__timeline-stage prediction-card__timeline-stage--${status}`}
  >
    <div className="prediction-card__timeline-node">
      <Icon path={icon} size={0.625} />
    </div>
    <span className="prediction-card__timeline-label">{label}</span>
    <span className="prediction-card__timeline-date">{date}</span>
  </div>
);

/**
 * Resolution Indicator Row
 */
const ResolutionIndicatorRow: React.FC<{
  resolution: ResolutionIndicator;
}> = ({ resolution }) => {
  const getTypeColor = (type: string): string => {
    switch (type) {
      case 'INL':
        return 'var(--color-accent-green)';
      case 'INI':
        return 'var(--color-accent-blue)';
      case 'RSP':
        return 'var(--color-accent-orange)';
      default:
        return 'var(--color-gray-500)';
    }
  };

  return (
    <div className="prediction-card__resolution">
      <div className="prediction-card__resolution-header">
        <span
          className="prediction-card__resolution-type"
          style={{ backgroundColor: getTypeColor(resolution.resolution_type) }}
          title={glossaryFor(resolution.resolution_type) || undefined}
        >
          {resolution.resolution_type}
        </span>
        <span className="prediction-card__resolution-ref">
          {resolution.procedure_ref}
        </span>
        {resolution.adoption_date && (
          <span className="prediction-card__resolution-date">
            {new Date(resolution.adoption_date).toLocaleDateString('en-GB', {
              day: 'numeric',
              month: 'short',
              year: 'numeric',
            })}
          </span>
        )}
      </div>
      <div className="prediction-card__resolution-title">
        {resolution.title}
      </div>
      <div className="prediction-card__resolution-vote">
        <div className="prediction-card__resolution-vote-bars">
          <div
            className="prediction-card__resolution-vote-bar prediction-card__resolution-vote-bar--for"
            style={{
              width: `${resolution.vote_total > 0 ? (resolution.vote_for / resolution.vote_total) * 100 : 0}%`,
            }}
            title={`For: ${resolution.vote_for}`}
          />
          <div
            className="prediction-card__resolution-vote-bar prediction-card__resolution-vote-bar--against"
            style={{
              width: `${resolution.vote_total > 0 ? (resolution.vote_against / resolution.vote_total) * 100 : 0}%`,
            }}
            title={`Against: ${resolution.vote_against}`}
          />
          <div
            className="prediction-card__resolution-vote-bar prediction-card__resolution-vote-bar--abstention"
            style={{
              width: `${resolution.vote_total > 0 ? (resolution.vote_abstention / resolution.vote_total) * 100 : 0}%`,
            }}
            title={`Abstention: ${resolution.vote_abstention}`}
          />
        </div>
        <div className="prediction-card__resolution-vote-stats">
          <span className="prediction-card__resolution-vote-stat prediction-card__resolution-vote-stat--for">
            <Icon path={mdiThumbUp} size={0.5} />
            {resolution.vote_for}
          </span>
          <span className="prediction-card__resolution-vote-stat prediction-card__resolution-vote-stat--against">
            <Icon path={mdiThumbDown} size={0.5} />
            {resolution.vote_against}
          </span>
          <span className="prediction-card__resolution-vote-stat prediction-card__resolution-vote-stat--abstention">
            <Icon path={mdiMinusCircle} size={0.5} />
            {resolution.vote_abstention}
          </span>
          <span className="prediction-card__resolution-support">
            {resolution.support_percentage.toFixed(1)}% support
          </span>
        </div>
      </div>
      <div className="prediction-card__resolution-meta">
        {resolution.lead_committee && (
          <span className="prediction-card__resolution-committee">
            {resolution.lead_committee}
          </span>
        )}
        {resolution.rapporteur && (
          <span className="prediction-card__resolution-rapporteur">
            {resolution.rapporteur}
          </span>
        )}
        <span
          className="prediction-card__resolution-confidence"
          title={`Match method: ${resolution.match_method}`}
        >
          {Math.round(resolution.match_confidence * 100)}% match
        </span>
      </div>
    </div>
  );
};

/**
 * Prediction card component
 */
const PredictionCard: React.FC<{
  prediction: PredictionSummary;
  onToggleExpand: () => void;
}> = ({ prediction, onToggleExpand }) => {
  const { t } = useTranslation();
  const [, setSearchParams] = useSearchParams();
  // Resolution data state
  const [resolutionData, setResolutionData] = useState<ResolutionLeadingIndicatorResponse | null>(null);
  const [isLoadingResolutions, setIsLoadingResolutions] = useState(false);
  const [resolutionError, setResolutionError] = useState<string | null>(null);
  // Calibration: the actual roll-call, for predicted-vs-actual (fetched upfront).
  const [calibration, setCalibration] = useState<CalibrationResult | null>(null);
  useEffect(() => {
    let alive = true;
    getCalibration(prediction.procedure_ref).then((c) => { if (alive) setCalibration(c); }).catch(() => {});
    return () => { alive = false; };
  }, [prediction.procedure_ref]);

  // Cross-link to the file's state-of-play (Position Analysis).
  const seeStateOfPlay = () => setSearchParams({ tab: 'position_analysis', ref: prediction.procedure_ref });

  // Forecast provenance (what the prediction is based on).
  const provenance = prediction.outcome?.model_version
    || prediction.timeline?.model_version
    || 'baseline model';
  const predictedOutcome = prediction.outcome ? getOutcomeLabel(prediction.outcome.predicted_outcome) : null;

  // Fetch resolution data when expanded
  useEffect(() => {
    if (prediction.is_expanded && !resolutionData && !isLoadingResolutions) {
      setIsLoadingResolutions(true);
      setResolutionError(null);

      getResolutionLeadingIndicators(
        prediction.procedure_ref,
        prediction.title,
        true
      )
        .then((data) => {
          setResolutionData(data);
        })
        .catch((error) => {
          console.error('Failed to fetch resolution data:', error);
          setResolutionError('Could not load resolution data');
        })
        .finally(() => {
          setIsLoadingResolutions(false);
        });
    }
  }, [prediction.is_expanded, prediction.procedure_ref, prediction.title, resolutionData, isLoadingResolutions]);

  // Get EP vote margin display
  const epVoteMargin = prediction.ep_vote
    ? prediction.ep_vote.predicted_margin >= 0
      ? `+${prediction.ep_vote.predicted_margin}`
      : prediction.ep_vote.predicted_margin.toString()
    : 'N/A';

  // Format date
  const predictedDate = new Date(prediction.predicted_at).toLocaleDateString(
    'en-GB',
    { day: 'numeric', month: 'short', year: 'numeric' }
  );

  // Get timeline if available
  const timelineDate = prediction.timeline
    ? formatPredictedDate(prediction.timeline.predicted_days_remaining)
    : 'TBD';

  return (
    <div className="prediction-card">
      <div className="prediction-card__header">
        <ConfidenceGauge confidence={prediction.overall_confidence} />
        <div className="prediction-card__info">
          <h3 className="prediction-card__title">{prediction.title}</h3>
          <span className="prediction-card__ref">{prediction.procedure_ref}</span>
          <div className="prediction-card__progress">
            <div className="prediction-card__progress-bar">
              <div
                className="prediction-card__progress-fill"
                style={{
                  '--target-width': `${Math.round(prediction.overall_confidence * 100)}%`,
                } as React.CSSProperties}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Calibration: actual outcome vs forecast (credibility) */}
      {calibration?.has_vote && (
        <div className="prediction-card__actual">
          <Icon path={mdiCheckDecagram} size={0.85} />
          <span>
            {t('predictionsTab.actualOutcome', 'Actual outcome')}: <strong>{(calibration.level || '').toUpperCase()} {calibration.result}</strong>
            {' '}{calibration.votes_for}-{calibration.votes_against}-{calibration.votes_abstention}
            {calibration.vote_date ? ` (${new Date(calibration.vote_date).toLocaleDateString()})` : ''}
            {predictedOutcome ? ` · ${t('predictionsTab.weForecast', 'forecast')}: ${predictedOutcome}` : ''}
          </span>
          {calibration.source_url && <a href={calibration.source_url} target="_blank" rel="noopener noreferrer"><Icon path={mdiOpenInNew} size={0.6} /></a>}
        </div>
      )}

      <div className="prediction-card__metrics">
        <div className="prediction-card__metric">
          <Icon
            path={mdiCheckCircle}
            size={1.5}
            className="prediction-card__metric-icon"
          />
          <div className="prediction-card__metric-label">{t('predictionsTab.outcome')}</div>
          <div className="prediction-card__metric-value">
            {prediction.outcome
              ? getOutcomeLabel(prediction.outcome.predicted_outcome)
              : t('predictionsTab.unknown')}
          </div>
          <ConfidenceDots confidence={prediction.outcome?.confidence || 0.5} />
        </div>

        <div className="prediction-card__metric">
          <Icon
            path={mdiCalendarClock}
            size={1.5}
            className="prediction-card__metric-icon"
          />
          <div className="prediction-card__metric-label">{t('predictionsTab.timeline')}</div>
          <div className="prediction-card__metric-value">{timelineDate}</div>
          <ConfidenceDots confidence={prediction.timeline?.confidence || 0.5} />
        </div>

        <div className="prediction-card__metric">
          <Icon
            path={mdiVote}
            size={1.5}
            className="prediction-card__metric-icon"
          />
          <div className="prediction-card__metric-label">{t('predictionsTab.epVote')}</div>
          <div className="prediction-card__metric-value">{epVoteMargin}</div>
          <ConfidenceDots confidence={prediction.ep_vote?.confidence || 0.5} />
        </div>

        <div className="prediction-card__metric">
          <Icon
            path={mdiShieldCheck}
            size={1.5}
            className="prediction-card__metric-icon"
          />
          <div className="prediction-card__metric-label">{t('predictionsTab.council')}</div>
          <div className="prediction-card__metric-value">
            {prediction.council_risk
              ? getCouncilRiskLabel(prediction.council_risk)
              : t('predictionsTab.unknown')}
          </div>
          <ConfidenceDots
            confidence={prediction.council_risk === 'low' ? 0.9 : 0.6}
          />
        </div>
      </div>

      {/* Provenance: what the forecast is based on */}
      <div className="prediction-card__provenance" title={t('predictionsTab.provenanceTip', 'A forecast, not a fact. This is what the model is based on.') as string}>
        <Icon path={mdiInformationOutline} size={0.6} />
        <span>{t('predictionsTab.forecastBasis', 'Forecast basis')}: {provenance}</span>
      </div>

      <div className="prediction-card__footer">
        <span className="prediction-card__date">{t('predictionsTab.predicted', { date: predictedDate })}</span>
        <div className="prediction-card__footer-actions">
          <button className="prediction-card__crosslink" onClick={seeStateOfPlay}>
            <Icon path={mdiScaleBalance} size={0.7} /> {t('predictionsTab.seeStateOfPlay', 'See state of play')}
          </button>
          <button
            className={`prediction-card__expand-btn ${
              prediction.is_expanded ? 'prediction-card__expand-btn--expanded' : ''
            }`}
            onClick={onToggleExpand}
          >
            <span>{prediction.is_expanded ? t('predictionsTab.collapse') : t('predictionsTab.details')}</span>
            <Icon
              path={mdiChevronDown}
              size={0.75}
              className="prediction-card__expand-icon"
            />
          </button>
        </div>
      </div>

      {/* Expanded Details */}
      <div
        className={`prediction-card__details ${
          prediction.is_expanded ? 'prediction-card__details--visible' : ''
        }`}
      >
        {/* EP Group Breakdown */}
        {prediction.ep_vote && prediction.ep_vote.group_predictions.length > 0 && (
          <div className="prediction-card__detail-section">
            <h4 className="prediction-card__detail-title">
              <Icon
                path={mdiAccountGroup}
                size={1}
                className="prediction-card__detail-title-icon"
              />
              {t('predictionsTab.epGroupBreakdown')}
            </h4>
            <div className="prediction-card__ep-groups">
              {prediction.ep_vote.group_predictions.map((gp) => (
                <EPGroupRow
                  key={gp.group_code}
                  groupCode={gp.group_code}
                  position={gp.predicted_position as GroupPosition}
                  confidence={gp.prob_for}
                />
              ))}
            </div>
          </div>
        )}

        {/* Timeline Projection */}
        {prediction.timeline && (
          <div className="prediction-card__detail-section">
            <h4 className="prediction-card__detail-title">
              <Icon
                path={mdiTimeline}
                size={1}
                className="prediction-card__detail-title-icon"
              />
              {t('predictionsTab.timelineProjection')}
            </h4>
            <div className="prediction-card__timeline">
              <TimelineStage
                label={t('predictionsTab.committee')}
                date={t('predictionsTab.done')}
                icon={mdiCheck}
                status="completed"
              />
              <div className="prediction-card__timeline-connector prediction-card__timeline-connector--active" />
              <TimelineStage
                label={t('predictionsTab.plenary')}
                date={t('predictionsTab.nextUp', 'Next up')}
                icon={mdiAccountVoice}
                status="current"
              />
              <div className="prediction-card__timeline-connector" />
              <TimelineStage
                label={t('predictionsTab.trilogue')}
                date={t('predictionsTab.later', 'Later')}
                icon={mdiHandshake}
                status="pending"
              />
              <div className="prediction-card__timeline-connector" />
              <TimelineStage
                label={t('predictionsTab.councilStage')}
                date={t('predictionsTab.later', 'Later')}
                icon={mdiGavel}
                status="pending"
              />
              <div className="prediction-card__timeline-connector" />
              <TimelineStage
                label={t('predictionsTab.oj')}
                date={timelineDate}
                icon={mdiBookOpenPageVariant}
                status="pending"
              />
            </div>
          </div>
        )}

        {/* Council Risk Assessment */}
        <div className="prediction-card__detail-section">
          <h4 className="prediction-card__detail-title">
            <Icon
              path={mdiShieldAccount}
              size={1}
              className="prediction-card__detail-title-icon"
            />
            {t('predictionsTab.councilRiskAssessment')}
          </h4>
          <div className="prediction-card__council-risk">
            <div className="prediction-card__council-status">
              <span
                title={glossaryFor('QMV') || undefined}
                className={`prediction-card__council-badge ${
                  prediction.council_risk === 'high' ||
                  prediction.council_risk === 'critical'
                    ? 'prediction-card__council-badge--danger'
                    : prediction.council_risk === 'medium'
                    ? 'prediction-card__council-badge--warning'
                    : ''
                }`}
              >
                <Icon path={mdiCheckCircle} size={0.75} />
                QMV:{' '}
                {prediction.council_risk === 'low'
                  ? t('predictionsTab.qmvSufficient')
                  : t('predictionsTab.qmvAtRisk')}
              </span>
            </div>
            <p className="prediction-card__council-note">
              {t('predictionsTab.qmvNote')}
            </p>
          </div>
        </div>

        {/* Resolution Leading Indicator */}
        <div className="prediction-card__detail-section">
          <h4 className="prediction-card__detail-title">
            <Icon
              path={mdiLightbulbOn}
              size={1}
              className="prediction-card__detail-title-icon"
            />
            {t('predictionsTab.resolutionLeading')}
          </h4>
          {isLoadingResolutions ? (
            <div className="prediction-card__resolution-loading">
              <span className="predictions-tab__loading-dot" />
              <span className="predictions-tab__loading-dot" />
              <span className="predictions-tab__loading-dot" />
              <span>{t('predictionsTab.loadingResolutionData')}</span>
            </div>
          ) : resolutionError ? (
            <div className="prediction-card__resolution-error">
              <Icon path={mdiAlertCircle} size={0.75} />
              {resolutionError}
            </div>
          ) : resolutionData && resolutionData.resolutions.length > 0 ? (
            <div className="prediction-card__resolutions">
              {/* Summary */}
              <div className="prediction-card__resolution-summary">
                <span
                  className={`prediction-card__resolution-sentiment prediction-card__resolution-sentiment--${resolutionData.summary.weighted_sentiment.toLowerCase().replace('_', '-')}`}
                >
                  {resolutionData.summary.weighted_sentiment === 'STRONG_SUPPORT'
                    ? t('predictionsTab.strongSupport')
                    : resolutionData.summary.weighted_sentiment === 'MODERATE_SUPPORT'
                    ? t('predictionsTab.moderateSupport')
                    : resolutionData.summary.weighted_sentiment === 'MIXED'
                    ? t('predictionsTab.mixed')
                    : resolutionData.summary.weighted_sentiment === 'LOW_SUPPORT'
                    ? t('predictionsTab.lowSupport')
                    : t('predictionsTab.noData')}
                </span>
                <span className="prediction-card__resolution-count">
                  {t('predictionsTab.relatedResolutions', { count: resolutionData.summary.total_resolutions })}
                </span>
                <span className="prediction-card__resolution-avg-support">
                  {t('predictionsTab.avgSupport', { n: resolutionData.summary.average_support.toFixed(1) })}
                </span>
              </div>

              {/* Resolution list */}
              <div className="prediction-card__resolution-list">
                {resolutionData.resolutions.slice(0, 3).map((resolution) => (
                  <ResolutionIndicatorRow
                    key={resolution.resolution_id}
                    resolution={resolution}
                  />
                ))}
              </div>

              {resolutionData.resolutions.length > 3 && (
                <div className="prediction-card__resolution-more">
                  {t('predictionsTab.moreResolutions', { count: resolutionData.resolutions.length - 3 })}
                </div>
              )}
            </div>
          ) : (
            <div className="prediction-card__resolution-empty">
              <Icon path={mdiFileDocumentCheck} size={1} />
              <p>{t('predictionsTab.noResolutionsFound')}</p>
              <p className="prediction-card__resolution-hint">
                {t('predictionsTab.noResolutionsHint')}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

/**
 * Quota indicator component
 */
const QuotaIndicator: React.FC<{
  used: number;
  total: number;
  resetDate: string;
}> = ({ used, total, resetDate }) => {
  const { t } = useTranslation();
  const remaining = total - used;
  const percentage = ((total - used) / total) * 100;

  return (
    <div className="predictions-tab__quota">
      <div className="predictions-tab__quota-info">
        <div className="predictions-tab__quota-icon">
          <Icon path={mdiCrystalBall} size={1} />
        </div>
        <div className="predictions-tab__quota-text">
          <span className="predictions-tab__quota-count">
            {t('predictionsTab.quotaRemaining', { remaining, total })}
          </span>{' '}
          {t('predictionsTab.predictionsRemaining')}
        </div>
      </div>
      <div className="predictions-tab__quota-bar-container">
        <div className="predictions-tab__quota-bar">
          <div
            className="predictions-tab__quota-bar-fill"
            style={{ '--target-width': `${percentage}%` } as React.CSSProperties}
          />
        </div>
      </div>
      <div className="predictions-tab__quota-reset">{t('predictionsTab.resets', { date: resetDate })}</div>
    </div>
  );
};


/**
 * Locked state component (White tier)
 */
const LockedState: React.FC<{ onUpgrade: () => void }> = ({ onUpgrade }) => {
  const { t } = useTranslation();
  return (
  <div className="predictions-tab__locked">
    <div className="predictions-tab__locked-illustration">
      <div className="predictions-tab__locked-orb" />
      <Icon path={mdiLock} size={2.5} className="predictions-tab__locked-lock" />
    </div>
    <h2 className="predictions-tab__locked-title">
      {t('predictionsTab.lockedTitle')}
    </h2>
    <p className="predictions-tab__locked-text">
      {t('predictionsTab.lockedText')}
    </p>
    <button className="predictions-tab__upgrade-btn" onClick={onUpgrade}>
      <Icon path={mdiStar} size={0.875} />
      {t('predictionsTab.subscribeFrom')}
    </button>
    <p className="predictions-tab__locked-note">
      {t('predictionsTab.lockedNote')}
    </p>
  </div>
  );
};

/**
 * Loading state component
 */
const LoadingState: React.FC<{ message: string }> = ({ message }) => {
  const { t } = useTranslation();
  return (
  <div className="predictions-tab__loading">
    <div className="predictions-tab__loading-spinner">
      <span className="predictions-tab__loading-dot" />
      <span className="predictions-tab__loading-dot" />
      <span className="predictions-tab__loading-dot" />
    </div>
    <p className="predictions-tab__loading-text">{t('predictionsTab.analysingSignals')}</p>
    <p className="predictions-tab__loading-status">{message}</p>
    <div className="predictions-tab__loading-bar">
      <div className="predictions-tab__loading-bar-fill" />
    </div>
  </div>
  );
};

// ============================================================================
// Main Component
// ============================================================================

export const PredictionsTab: React.FC<PredictionsTabProps> = ({ className }) => {
  const { t } = useTranslation();
  const { user } = useAuth();

  const {
    predictions,
    quota,
    loadingState,
    toggleExpanded,
    updateQuota,
    generatePrediction,
  } = usePredictions();

  // PI-bucketed files for the picker (tracked + suggested-by-interests)
  const [files, setFiles] = useState<InterestFiles | null>(null);
  const [filesLoading, setFilesLoading] = useState(false);
  const [myInterests, setMyInterests] = useState(true);

  // Which files are currently forecasting (per-card spinner)
  const [generatingRefs, setGeneratingRefs] = useState<Set<string>>(new Set());

  // Determine user tier
  const userTier = user?.subscription_tier || 'white';
  const isWhiteTier = userTier === 'white';
  const isYellowTier = userTier === 'yellow';
  const isBlueTier = userTier === 'blue';

  // Fetch the PI-bucketed file list (re-fetches when the interests toggle changes)
  useEffect(() => {
    if (isWhiteTier) return;
    setFilesLoading(true);
    getInterestFiles(myInterests)
      .then(setFiles)
      .catch(() => setFiles({ pi_active: false, tracked: [], suggested: [] }))
      .finally(() => setFilesLoading(false));
  }, [isWhiteTier, myInterests]);

  // Initialize quota for Yellow tier users
  useEffect(() => {
    if (isYellowTier && !quota) {
      // Calculate next month reset date
      const now = new Date();
      const nextMonth = new Date(now.getFullYear(), now.getMonth() + 1, 1);
      const resetDate = nextMonth.toLocaleDateString('en-GB', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      });

      // Start with 3 predictions (would come from backend in production)
      updateQuota(1, 3, resetDate);
    }
  }, [isYellowTier, quota, updateQuota]);

  // Auto-load prediction from URL param (calendar deep-link)
  const [searchParams, setSearchParams] = useSearchParams();
  const autoLoadRef = useRef(false);
  useEffect(() => {
    const refParam = searchParams.get('ref');
    if (refParam && !autoLoadRef.current && !isWhiteTier) {
      autoLoadRef.current = true;
      const decodedRef = decodeURIComponent(refParam);
      // Clear param after reading
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.delete('ref');
        return next;
      }, { replace: true });
      // Generate prediction if not already loaded
      if (!predictions.some((p) => p.procedure_ref === decodedRef)) {
        generatePrediction(decodedRef, decodedRef);
      }
    }
  }, [searchParams, predictions, generatePrediction, isWhiteTier, setSearchParams]);

  // Generate the forecast for one file (per-card loading, no modal).
  const generateOne = useCallback(async (file: PredictionPickerFile) => {
    const ref = file.procedure_ref;
    if (!ref) return;
    setGeneratingRefs((s) => new Set(s).add(ref));
    try { await generatePrediction(ref, file.title || ref, file.lead_committee || undefined); }
    catch { /* quota / network - surfaced via store error */ }
    finally { setGeneratingRefs((s) => { const n = new Set(s); n.delete(ref); return n; }); }
  }, [generatePrediction]);

  // Auto-forecast the first few tracked files so the page renders populated (the rest
  // are one-click stubs). Bounded to keep load fast and respect the Yellow quota.
  const autoGenStarted = useRef(false);
  useEffect(() => {
    if (isWhiteTier || !files || autoGenStarted.current) return;
    autoGenStarted.current = true;
    const cap = isBlueTier ? 4 : 2;
    const todo = (files.tracked.length ? files.tracked : files.suggested).slice(0, cap);
    (async () => {
      for (const f of todo) {
        if (!f.procedure_ref) continue;
        await generateOne(f);
      }
    })();
  }, [files, isWhiteTier, isBlueTier, generateOne]);

  // Handle upgrade
  const handleUpgrade = useCallback(() => {
    window.location.href = '/subscription';
  }, []);

  // Render White tier locked state
  if (isWhiteTier) {
    return (
      <div className={`predictions-tab ${className || ''}`}>
        <GaugeSVGDefs />
        <LockedState onUpgrade={handleUpgrade} />
      </div>
    );
  }

  // The PI file list, rendered immediately (tracked + suggested-by-interests). Each file
  // is a card: the generated forecast if available, otherwise a one-click stub.
  const displayFiles: PredictionPickerFile[] = [
    ...(files?.tracked || []),
    ...(myInterests ? (files?.suggested || []) : []),
  ];
  const predByRef = new Map(predictions.map((p) => [p.procedure_ref, p] as const));
  // Predictions for files outside the current list (e.g. a deep-linked ?ref=) go on top.
  const extraPreds = predictions.filter((p) => !displayFiles.some((f) => f.procedure_ref === p.procedure_ref));

  return (
    <div className={`predictions-tab ${className || ''}`}>
      <GaugeSVGDefs />

      <MeubHeader
        icon={mdiCrystalBall}
        title={t('predictionsTab.headerTitle', 'Predictions')}
        subtitle={t('predictionsTab.headerSubtitle', 'AI forecasts for the dossiers you track: likely outcome, timing, the Parliament vote and Council risk, each with a confidence level. Forecasts, not facts.')}
      />

      <div className="predictions-tab__toolbar">
        <div className="predictions-tab__toggle">
          <button className={myInterests ? 'is-active' : ''} onClick={() => setMyInterests(true)}>{t('predictionsTab.mine', 'My interests')}</button>
          <button className={!myInterests ? 'is-active' : ''} onClick={() => setMyInterests(false)}>{t('predictionsTab.allTracked', 'All tracked')}</button>
        </div>
        {isYellowTier && quota && (
          <QuotaIndicator used={quota.used} total={quota.total} resetDate={quota.reset_date} />
        )}
      </div>

      {filesLoading && displayFiles.length === 0 ? (
        <LoadingState message={loadingState.message || t('predictionsTab.loadingYourFiles')} />
      ) : displayFiles.length === 0 && extraPreds.length === 0 ? (
        <div className="predictions-tab__hint">
          <Icon path={mdiCrystalBall} size={1.2} />
          <p>{t('predictionsTab.noneTracked')}</p>
          <p className="predictions-tab__hint-sub">{t('predictionsTab.goToMyFiles')}</p>
        </div>
      ) : (
        <div className="predictions-tab__list">
          {extraPreds.map((p) => (
            <PredictionCard key={p.id} prediction={p} onToggleExpand={() => toggleExpanded(p.id)} />
          ))}
          {displayFiles.map((f) => {
            const pred = f.procedure_ref ? predByRef.get(f.procedure_ref) : undefined;
            if (pred) {
              return <PredictionCard key={pred.id} prediction={pred} onToggleExpand={() => toggleExpanded(pred.id)} />;
            }
            const gen = !!f.procedure_ref && generatingRefs.has(f.procedure_ref);
            return (
              <div key={f.carriage_id} className="prediction-stub">
                <div className="prediction-stub__info">
                  <h3 className="prediction-stub__title">{f.title || f.procedure_ref}</h3>
                  <span className="prediction-stub__ref">
                    {f.procedure_ref}{f.lead_committee ? ` · ${f.lead_committee}` : ''}
                    {f.is_pi_match && !f.is_tracked ? ` · ${t('predictionsTab.suggested', 'Suggested for your interests')}` : ''}
                  </span>
                </div>
                <button className="prediction-stub__btn" disabled={gen} onClick={() => generateOne(f)}>
                  <Icon path={mdiCrystalBall} size={0.8} />
                  {gen ? t('predictionsTab.generating', 'Forecasting...') : t('predictionsTab.generate', 'Forecast')}
                </button>
              </div>
            );
          })}
        </div>
      )}

      {isBlueTier && (
        <p className="predictions-tab__unlimited">
          <Icon path={mdiInfinity} size={0.75} className="predictions-tab__unlimited-icon" />
          {t('predictionsTab.unlimited', 'Professional: Unlimited predictions')}
        </p>
      )}
    </div>
  );
};

export default PredictionsTab;
