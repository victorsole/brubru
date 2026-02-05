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

import React, { useEffect, useCallback, useState } from 'react';
import { createPortal } from 'react-dom';
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
  // mdiCheckDecagram,
  mdiLock,
  mdiStar,
  mdiInfinity,
  mdiClose,
  mdiMagnify,
  mdiFileDocument,
} from '@mdi/js';

import { useAuth } from '../../hooks/use_auth';
import { useLegislativeTrains, type TrackedFile } from '../../hooks/use_legislative_trains';
import {
  usePredictions,
  LOADING_MESSAGES,
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
  type PredictionSummary,
  type GroupPosition,
  type ResolutionLeadingIndicatorResponse,
  type ResolutionIndicator,
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
  // Resolution data state
  const [resolutionData, setResolutionData] = useState<ResolutionLeadingIndicatorResponse | null>(null);
  const [isLoadingResolutions, setIsLoadingResolutions] = useState(false);
  const [resolutionError, setResolutionError] = useState<string | null>(null);

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

      <div className="prediction-card__metrics">
        <div className="prediction-card__metric">
          <Icon
            path={mdiCheckCircle}
            size={1.5}
            className="prediction-card__metric-icon"
          />
          <div className="prediction-card__metric-label">Outcome</div>
          <div className="prediction-card__metric-value">
            {prediction.outcome
              ? getOutcomeLabel(prediction.outcome.predicted_outcome)
              : 'Unknown'}
          </div>
          <ConfidenceDots confidence={prediction.outcome?.confidence || 0.5} />
        </div>

        <div className="prediction-card__metric">
          <Icon
            path={mdiCalendarClock}
            size={1.5}
            className="prediction-card__metric-icon"
          />
          <div className="prediction-card__metric-label">Timeline</div>
          <div className="prediction-card__metric-value">{timelineDate}</div>
          <ConfidenceDots confidence={prediction.timeline?.confidence || 0.5} />
        </div>

        <div className="prediction-card__metric">
          <Icon
            path={mdiVote}
            size={1.5}
            className="prediction-card__metric-icon"
          />
          <div className="prediction-card__metric-label">EP Vote</div>
          <div className="prediction-card__metric-value">{epVoteMargin}</div>
          <ConfidenceDots confidence={prediction.ep_vote?.confidence || 0.5} />
        </div>

        <div className="prediction-card__metric">
          <Icon
            path={mdiShieldCheck}
            size={1.5}
            className="prediction-card__metric-icon"
          />
          <div className="prediction-card__metric-label">Council</div>
          <div className="prediction-card__metric-value">
            {prediction.council_risk
              ? getCouncilRiskLabel(prediction.council_risk)
              : 'Unknown'}
          </div>
          <ConfidenceDots
            confidence={prediction.council_risk === 'low' ? 0.9 : 0.6}
          />
        </div>
      </div>

      <div className="prediction-card__footer">
        <span className="prediction-card__date">Predicted {predictedDate}</span>
        <button
          className={`prediction-card__expand-btn ${
            prediction.is_expanded ? 'prediction-card__expand-btn--expanded' : ''
          }`}
          onClick={onToggleExpand}
        >
          <span>{prediction.is_expanded ? 'Collapse' : 'Details'}</span>
          <Icon
            path={mdiChevronDown}
            size={0.75}
            className="prediction-card__expand-icon"
          />
        </button>
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
              EP Political Group Breakdown
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
              Timeline Projection
            </h4>
            <div className="prediction-card__timeline">
              <TimelineStage
                label="Committee"
                date="Done"
                icon={mdiCheck}
                status="completed"
              />
              <div className="prediction-card__timeline-connector prediction-card__timeline-connector--active" />
              <TimelineStage
                label="Plenary"
                date="Mar 2026"
                icon={mdiAccountVoice}
                status="current"
              />
              <div className="prediction-card__timeline-connector" />
              <TimelineStage
                label="Trilogue"
                date="Q2 2026"
                icon={mdiHandshake}
                status="pending"
              />
              <div className="prediction-card__timeline-connector" />
              <TimelineStage
                label="Council"
                date="Q3 2026"
                icon={mdiGavel}
                status="pending"
              />
              <div className="prediction-card__timeline-connector" />
              <TimelineStage
                label="OJ"
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
            Council Risk Assessment
          </h4>
          <div className="prediction-card__council-risk">
            <div className="prediction-card__council-status">
              <span
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
                  ? 'Sufficient support'
                  : 'At risk'}
              </span>
            </div>
            <p className="prediction-card__council-note">
              Detailed QMV analysis requires Council position data.
              Risk level based on policy area and procedure type.
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
            Resolution Leading Indicators
          </h4>
          {isLoadingResolutions ? (
            <div className="prediction-card__resolution-loading">
              <span className="predictions-tab__loading-dot" />
              <span className="predictions-tab__loading-dot" />
              <span className="predictions-tab__loading-dot" />
              <span>Loading resolution data...</span>
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
                    ? 'Strong Support'
                    : resolutionData.summary.weighted_sentiment === 'MODERATE_SUPPORT'
                    ? 'Moderate Support'
                    : resolutionData.summary.weighted_sentiment === 'MIXED'
                    ? 'Mixed'
                    : resolutionData.summary.weighted_sentiment === 'LOW_SUPPORT'
                    ? 'Low Support'
                    : 'No Data'}
                </span>
                <span className="prediction-card__resolution-count">
                  {resolutionData.summary.total_resolutions} related resolution
                  {resolutionData.summary.total_resolutions !== 1 ? 's' : ''}
                </span>
                <span className="prediction-card__resolution-avg-support">
                  Avg: {resolutionData.summary.average_support.toFixed(1)}% support
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
                  +{resolutionData.resolutions.length - 3} more resolution
                  {resolutionData.resolutions.length - 3 !== 1 ? 's' : ''}
                </div>
              )}
            </div>
          ) : (
            <div className="prediction-card__resolution-empty">
              <Icon path={mdiFileDocumentCheck} size={1} />
              <p>No related resolutions found.</p>
              <p className="prediction-card__resolution-hint">
                EP resolutions (INL, INI, RSP) that preceded this legislation
                would appear here as predictive signals.
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
            {remaining} of {total}
          </span>{' '}
          predictions remaining
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
      <div className="predictions-tab__quota-reset">Resets {resetDate}</div>
    </div>
  );
};

/**
 * Empty state component
 */
const EmptyState: React.FC<{ onSelectFile: () => void }> = ({ onSelectFile }) => (
  <div className="predictions-tab__empty">
    <div className="predictions-tab__empty-illustration">
      <div className="predictions-tab__empty-orb" />
      <Icon
        path={mdiCrystalBall}
        size={3}
        className="predictions-tab__empty-icon"
      />
      <div className="predictions-tab__empty-particles">
        <span className="predictions-tab__particle" />
        <span className="predictions-tab__particle" />
        <span className="predictions-tab__particle" />
      </div>
    </div>
    <h2 className="predictions-tab__empty-title">
      Get predictions for your tracked files
    </h2>
    <p className="predictions-tab__empty-text">
      See how likely your legislation is to pass, when it might be adopted, and
      how the EP and Council are expected to vote.
    </p>
    <button className="predictions-tab__select-file" onClick={onSelectFile}>
      Choose a file to predict
      <Icon path={mdiChevronDown} size={0.875} />
    </button>
  </div>
);

/**
 * File Picker Modal component
 */
interface FilePickerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (file: TrackedFile) => void;
  trackedFiles: TrackedFile[];
  isLoading: boolean;
}

const FilePickerModal: React.FC<FilePickerModalProps> = ({
  isOpen,
  onClose,
  onSelect,
  trackedFiles,
  isLoading,
}) => {
  const [searchQuery, setSearchQuery] = useState('');

  if (!isOpen) return null;

  const filteredFiles = trackedFiles.filter((file) =>
    file.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (file.oeil_procedure_ref?.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const getStatusColor = (status: string): string => {
    const statusLower = status.toLowerCase();
    if (statusLower.includes('adopted') || statusLower.includes('completed')) return 'var(--color-accent-green)';
    if (statusLower.includes('rejected') || statusLower.includes('withdrawn')) return 'var(--color-accent-red)';
    if (statusLower.includes('committee') || statusLower.includes('plenary')) return 'var(--color-accent-blue)';
    if (statusLower.includes('council')) return 'var(--color-accent-purple)';
    return 'var(--color-gray-500)';
  };

  return createPortal(
    <div className="predictions-tab__modal-overlay" onClick={onClose}>
      <div
        className="predictions-tab__modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="predictions-tab__modal-header">
          <h2 className="predictions-tab__modal-title">
            <Icon path={mdiFileDocument} size={1} />
            Select a file to predict
          </h2>
          <button
            className="predictions-tab__modal-close"
            onClick={onClose}
            aria-label="Close"
          >
            <Icon path={mdiClose} size={1} />
          </button>
        </div>

        <div className="predictions-tab__modal-search">
          <Icon path={mdiMagnify} size={0.875} className="predictions-tab__modal-search-icon" />
          <input
            type="text"
            placeholder="Search your tracked files..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="predictions-tab__modal-search-input"
            autoFocus
          />
        </div>

        <div className="predictions-tab__modal-content">
          {isLoading ? (
            <div className="predictions-tab__modal-loading">
              Loading your tracked files...
            </div>
          ) : filteredFiles.length === 0 ? (
            <div className="predictions-tab__modal-empty">
              {trackedFiles.length === 0 ? (
                <>
                  <p>You haven't tracked any files yet.</p>
                  <p className="predictions-tab__modal-hint">
                    Go to "My Files" tab to track legislative procedures.
                  </p>
                </>
              ) : (
                <p>No files match your search.</p>
              )}
            </div>
          ) : (
            <div className="predictions-tab__modal-list">
              {filteredFiles.map((file) => (
                <button
                  key={file.id}
                  className="predictions-tab__modal-item"
                  onClick={() => onSelect(file)}
                >
                  <div className="predictions-tab__modal-item-main">
                    <span className="predictions-tab__modal-item-title">
                      {file.title}
                    </span>
                    {file.oeil_procedure_ref && (
                      <span className="predictions-tab__modal-item-ref">
                        {file.oeil_procedure_ref}
                      </span>
                    )}
                  </div>
                  <div className="predictions-tab__modal-item-meta">
                    <span
                      className="predictions-tab__modal-item-status"
                      style={{ color: getStatusColor(file.current_status) }}
                    >
                      {file.current_status}
                    </span>
                    {file.lead_committee && (
                      <span className="predictions-tab__modal-item-committee">
                        {file.lead_committee}
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
};

/**
 * Locked state component (White tier)
 */
const LockedState: React.FC<{ onUpgrade: () => void }> = ({ onUpgrade }) => (
  <div className="predictions-tab__locked">
    <div className="predictions-tab__locked-illustration">
      <div className="predictions-tab__locked-orb" />
      <Icon path={mdiLock} size={2.5} className="predictions-tab__locked-lock" />
    </div>
    <h2 className="predictions-tab__locked-title">
      Predictions are a Yellow feature
    </h2>
    <p className="predictions-tab__locked-text">
      Know the odds of your legislation passing. See how MEPs and member states
      are likely to vote. Plan your advocacy with data-driven insights.
    </p>
    <button className="predictions-tab__upgrade-btn" onClick={onUpgrade}>
      <Icon path={mdiStar} size={0.875} />
      Upgrade to Yellow - EUR 79/month
    </button>
    <p className="predictions-tab__locked-note">
      Yellow subscribers get 3 predictions per month
    </p>
  </div>
);

/**
 * Loading state component
 */
const LoadingState: React.FC<{ message: string }> = ({ message }) => (
  <div className="predictions-tab__loading">
    <div className="predictions-tab__loading-spinner">
      <span className="predictions-tab__loading-dot" />
      <span className="predictions-tab__loading-dot" />
      <span className="predictions-tab__loading-dot" />
    </div>
    <p className="predictions-tab__loading-text">Analysing legislative signals...</p>
    <p className="predictions-tab__loading-status">{message}</p>
    <div className="predictions-tab__loading-bar">
      <div className="predictions-tab__loading-bar-fill" />
    </div>
  </div>
);

// ============================================================================
// Main Component
// ============================================================================

export const PredictionsTab: React.FC<PredictionsTabProps> = ({ className }) => {
  const { user } = useAuth();

  const {
    predictions,
    quota,
    loadingState,
    isGeneratingPrediction,
    toggleExpanded,
    updateQuota,
    generatePrediction,
  } = usePredictions();

  // Get tracked files from Legislative Trains
  const {
    trackedFiles,
    fetchTrackedFiles,
    isLoadingTrackedFiles,
  } = useLegislativeTrains();

  // State for file picker modal
  const [showFilePicker, setShowFilePicker] = useState(false);

  // Determine user tier
  const userTier = user?.subscription_tier || 'white';
  const isWhiteTier = userTier === 'white';
  const isYellowTier = userTier === 'yellow';
  const isBlueTier = userTier === 'blue';

  // Fetch tracked files when component mounts
  useEffect(() => {
    if (!isWhiteTier) {
      fetchTrackedFiles();
    }
  }, [isWhiteTier, fetchTrackedFiles]);

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

  // Handle file selection for prediction
  const handleSelectFile = useCallback(() => {
    setShowFilePicker(true);
  }, []);

  // Handle file selected from picker
  const handleFileSelected = useCallback(async (file: TrackedFile) => {
    setShowFilePicker(false);

    // Generate prediction for the selected file
    if (file.oeil_procedure_ref) {
      await generatePrediction(
        file.oeil_procedure_ref,
        file.title,
        file.lead_committee || undefined
      );
    }
  }, [generatePrediction]);

  // Handle upgrade
  const handleUpgrade = useCallback(() => {
    // Navigate to subscription page
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

  // Render loading state
  if (isGeneratingPrediction) {
    return (
      <div className={`predictions-tab ${className || ''}`}>
        <GaugeSVGDefs />
        {isYellowTier && quota && (
          <QuotaIndicator
            used={quota.used}
            total={quota.total}
            resetDate={quota.reset_date}
          />
        )}
        <LoadingState message={loadingState.message || LOADING_MESSAGES[0]} />
      </div>
    );
  }

  // Render empty state
  if (predictions.length === 0) {
    return (
      <div className={`predictions-tab ${className || ''}`}>
        <GaugeSVGDefs />
        {isYellowTier && quota && (
          <QuotaIndicator
            used={quota.used}
            total={quota.total}
            resetDate={quota.reset_date}
          />
        )}
        <EmptyState onSelectFile={handleSelectFile} />
        <FilePickerModal
          isOpen={showFilePicker}
          onClose={() => setShowFilePicker(false)}
          onSelect={handleFileSelected}
          trackedFiles={trackedFiles}
          isLoading={isLoadingTrackedFiles}
        />
      </div>
    );
  }

  // Render predictions list
  return (
    <div className={`predictions-tab ${className || ''}`}>
      <GaugeSVGDefs />

      {/* Quota indicator (Yellow tier only) */}
      {isYellowTier && quota && (
        <QuotaIndicator
          used={quota.used}
          total={quota.total}
          resetDate={quota.reset_date}
        />
      )}

      {/* Predictions list */}
      <div className="predictions-tab__list">
        {predictions.map((prediction) => (
          <PredictionCard
            key={prediction.id}
            prediction={prediction}
            onToggleExpand={() => toggleExpanded(prediction.id)}
          />
        ))}
      </div>

      {/* Add another prediction button */}
      <button
        className="predictions-tab__add-prediction"
        onClick={handleSelectFile}
      >
        <Icon path={mdiCrystalBall} size={0.875} />
        Add another prediction
      </button>

      {/* Blue tier unlimited note */}
      {isBlueTier && (
        <p className="predictions-tab__unlimited">
          <Icon
            path={mdiInfinity}
            size={0.75}
            className="predictions-tab__unlimited-icon"
          />
          Blue tier: Unlimited predictions
        </p>
      )}

      {/* File picker modal */}
      <FilePickerModal
        isOpen={showFilePicker}
        onClose={() => setShowFilePicker(false)}
        onSelect={handleFileSelected}
        trackedFiles={trackedFiles}
        isLoading={isLoadingTrackedFiles}
      />
    </div>
  );
};

export default PredictionsTab;
