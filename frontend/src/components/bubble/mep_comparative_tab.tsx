/**
 * Comparative Analysis Sub-tab Component
 *
 * AI-powered alignment scoring: compares user's policy position against
 * MEP amendments. Shows alignment summary, best allies, coverage gaps,
 * and political landscape.
 *
 * Phase 4 of MEP Amendments feature.
 *
 * Part of My EU Bubble > Amendments > Comparative Analysis.
 *
 * Created: February 2026
 */

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import Icon from '@mdi/react';
import {
  mdiScaleBalance,
  mdiAccountHeartOutline,
  mdiPuzzleOutline,
  mdiBankOutline,
  mdiMagnifyScan,
  mdiLoading,
  mdiAlertCircleOutline,
  mdiInformationOutline,
} from '@mdi/js';
import { useAuth } from '../../hooks/use_auth';
import { useMEPAmendments, EP_GROUP_COLOURS, DARK_TEXT_GROUPS } from '../../hooks/use_mep_amendments';
import type { ComparisonAlly, LandscapeGroup } from '../../services/mep_amendment_service';
import './mep_comparative_tab.css';


// ============================================================================
// Sub-Components
// ============================================================================

/** Score colour helpers */
function scoreColour(score: number): string {
  if (score >= 1.5) return '#059669';
  if (score >= 0.5) return '#0693e3';
  if (score >= -0.5) return '#9ca3af';
  if (score >= -1.5) return '#d97706';
  return '#dc2626';
}

/** Policy Position Input */
const PolicyPositionInput = ({
  value,
  onChange,
  onSubmit,
  isLoading,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  isLoading: boolean;
  disabled: boolean;
}) => (
  <PolicyPositionInputInner value={value} onChange={onChange} onSubmit={onSubmit} isLoading={isLoading} disabled={disabled} />
);

const PolicyPositionInputInner = ({ value, onChange, onSubmit, isLoading, disabled }: any) => {
  const { t } = useTranslation();
  return (
  <div className="mep-comparative__input-section">
    <label className="mep-comparative__input-label" htmlFor="policy-position">
      {t('mepComparativeTab.describePosition')}
    </label>
    <p className="mep-comparative__input-hint">
      {t('mepComparativeTab.describeHint')}
    </p>
    <textarea
      id="policy-position"
      className="mep-comparative__textarea"
      placeholder={t('mepComparativeTab.positionPlaceholder')}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      rows={4}
      disabled={isLoading}
    />
    <div className="mep-comparative__input-footer">
      <span className="mep-comparative__char-count">
        {t('mepComparativeTab.charCount', { used: value.length })}
      </span>
      <button
        className="mep-comparative__run-btn"
        onClick={onSubmit}
        disabled={disabled || value.length < 10 || isLoading}
        aria-label={t('mepComparativeTab.runAnalysis')}
      >
        {isLoading ? (
          <>
            <Icon path={mdiLoading} size={0.7} spin />
            {t('mepComparativeTab.scoringAmendments')}
          </>
        ) : (
          <>
            <Icon path={mdiMagnifyScan} size={0.7} />
            {t('mepComparativeTab.runAnalysisBtn')}
          </>
        )}
      </button>
    </div>
  </div>
  );
};


/** Alignment Summary Cards */
const AlignmentSummary = ({
  distribution,
  total,
}: {
  distribution: Record<string, number>;
  total: number;
}) => {
  const { t } = useTranslation();
  const cards = [
    { key: '2', label: t('mepComparativeTab.stronglyAligned'), colour: '#059669' },
    { key: '1', label: t('mepComparativeTab.partiallyAligned'), colour: '#0693e3' },
    { key: '0', label: t('mepComparativeTab.neutral'), colour: '#9ca3af' },
    { key: 'negative', label: t('mepComparativeTab.opposed'), colour: '#dc2626' },
  ];

  const negativeCount = (distribution['-1'] || 0) + (distribution['-2'] || 0);

  return (
    <div className="mep-comparative__section">
      <div className="mep-comparative__section-header">
        <Icon path={mdiScaleBalance} size={0.8} />
        <span>{t('mepComparativeTab.alignmentSummary')}</span>
        <span className="mep-comparative__section-count">{t('mepComparativeTab.amendmentsScored', { n: total })}</span>
      </div>
      <div className="mep-comparative__summary-grid">
        {cards.map((card) => {
          const count = card.key === 'negative' ? negativeCount : (distribution[card.key] || 0);
          const pct = total > 0 ? Math.round((count / total) * 100) : 0;
          return (
            <div
              key={card.key}
              className="mep-comparative__summary-card"
              style={{ borderTopColor: card.colour }}
            >
              <div className="mep-comparative__summary-value">{count}</div>
              <div className="mep-comparative__summary-pct">{pct}%</div>
              <div className="mep-comparative__summary-label">{card.label}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};


/** Best Allies Ranked List */
const BestAllies = ({ allies }: { allies: ComparisonAlly[] }) => {
  const { t } = useTranslation();
  if (!allies.length) return null;

  return (
    <div className="mep-comparative__section">
      <div className="mep-comparative__section-header">
        <Icon path={mdiAccountHeartOutline} size={0.8} />
        <span>{t('mepComparativeTab.bestAllies')}</span>
      </div>
      <p className="mep-comparative__section-desc">
        {t('mepComparativeTab.bestAlliesDesc')}
      </p>
      <div className="mep-comparative__allies-list">
        {allies.map((ally, i) => {
          const bgColour = EP_GROUP_COLOURS[ally.group] || '#9ca3af';
          const textColour = DARK_TEXT_GROUPS.has(ally.group) ? '#333' : '#fff';
          const barWidth = Math.max(0, ((ally.avg_score + 2) / 4) * 100);

          return (
            <div key={ally.name} className="mep-comparative__ally-row">
              <span className="mep-comparative__ally-rank">#{i + 1}</span>
              <span className="mep-comparative__ally-name">{ally.name}</span>
              <span
                className="mep-comparative__ally-group"
                style={{ background: bgColour, color: textColour }}
              >
                {ally.group}
              </span>
              <div className="mep-comparative__ally-bar-container">
                <div
                  className="mep-comparative__ally-bar"
                  style={{
                    width: `${barWidth}%`,
                    background: scoreColour(ally.avg_score),
                  }}
                />
              </div>
              <span
                className="mep-comparative__ally-score"
                style={{ color: scoreColour(ally.avg_score) }}
              >
                {ally.avg_score > 0 ? '+' : ''}{ally.avg_score.toFixed(1)}
              </span>
              <span className="mep-comparative__ally-count">{t('mepComparativeTab.amCount', { n: ally.count })}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};


/** Coverage Gaps */
const CoverageGaps = ({
  gaps,
}: {
  gaps: { user_unique: string[]; blind_spots: string[] };
}) => {
  const { t } = useTranslation();
  if (!gaps.user_unique.length && !gaps.blind_spots.length) {
    return (
      <div className="mep-comparative__section">
        <div className="mep-comparative__section-header">
          <Icon path={mdiPuzzleOutline} size={0.8} />
          <span>{t('mepComparativeTab.coverageGaps')}</span>
        </div>
        <div className="mep-comparative__info-note">
          <Icon path={mdiInformationOutline} size={0.7} />
          <span>
            {t('mepComparativeTab.amendatorDraftHint')}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="mep-comparative__section">
      <div className="mep-comparative__section-header">
        <Icon path={mdiPuzzleOutline} size={0.8} />
        <span>{t('mepComparativeTab.coverageGaps')}</span>
      </div>
      <div className="mep-comparative__gaps-grid">
        <div className="mep-comparative__gap-col mep-comparative__gap-col--unique">
          <div className="mep-comparative__gap-header">
            {t('mepComparativeTab.yourUniquePositions', { n: gaps.user_unique.length })}
          </div>
          <div className="mep-comparative__gap-list">
            {gaps.user_unique.length > 0 ? (
              gaps.user_unique.map((el) => (
                <div key={el} className="mep-comparative__gap-item mep-comparative__gap-item--unique">
                  {el}
                </div>
              ))
            ) : (
              <p className="mep-comparative__gap-empty">
                {t('mepComparativeTab.allCovered')}
              </p>
            )}
          </div>
        </div>
        <div className="mep-comparative__gap-col mep-comparative__gap-col--blind">
          <div className="mep-comparative__gap-header">
            {t('mepComparativeTab.blindSpots', { n: gaps.blind_spots.length })}
          </div>
          <div className="mep-comparative__gap-list">
            {gaps.blind_spots.length > 0 ? (
              gaps.blind_spots.map((el) => (
                <div key={el} className="mep-comparative__gap-item mep-comparative__gap-item--blind">
                  {el}
                </div>
              ))
            ) : (
              <p className="mep-comparative__gap-empty">
                {t('mepComparativeTab.noBlindSpots')}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};


/** Political Landscape */
const PoliticalLandscape = ({
  landscape,
}: {
  landscape: {
    supportive: LandscapeGroup[];
    mixed: LandscapeGroup[];
    opposed: LandscapeGroup[];
  };
}) => {
  const { t } = useTranslation();
  const renderColumn = (
    title: string,
    groups: LandscapeGroup[],
    colClass: string,
  ) => (
    <div className={`mep-comparative__landscape-col ${colClass}`}>
      <div className="mep-comparative__landscape-header">{title}</div>
      <div className="mep-comparative__landscape-groups">
        {groups.length > 0 ? groups.map((g) => {
          const bgColour = EP_GROUP_COLOURS[g.group] || '#9ca3af';
          const textColour = DARK_TEXT_GROUPS.has(g.group) ? '#333' : '#fff';
          return (
            <div key={g.group} className="mep-comparative__landscape-group">
              <span
                className="mep-comparative__landscape-badge"
                style={{ background: bgColour, color: textColour }}
              >
                {g.group}
              </span>
              <span
                className="mep-comparative__landscape-score"
                style={{ color: scoreColour(g.avg_score) }}
              >
                {g.avg_score > 0 ? '+' : ''}{g.avg_score.toFixed(1)}
              </span>
              <span className="mep-comparative__landscape-count">{t('mepComparativeTab.amCount', { n: g.count })}</span>
            </div>
          );
        }) : (
          <p className="mep-comparative__landscape-empty">{t('mepComparativeTab.none')}</p>
        )}
      </div>
    </div>
  );

  return (
    <div className="mep-comparative__section">
      <div className="mep-comparative__section-header">
        <Icon path={mdiBankOutline} size={0.8} />
        <span>{t('mepComparativeTab.politicalLandscape')}</span>
      </div>
      <div className="mep-comparative__landscape-grid">
        {renderColumn(t('mepComparativeTab.supportive'), landscape.supportive, 'mep-comparative__landscape-col--supportive')}
        {renderColumn(t('mepComparativeTab.mixed'), landscape.mixed, 'mep-comparative__landscape-col--mixed')}
        {renderColumn(t('mepComparativeTab.opposed'), landscape.opposed, 'mep-comparative__landscape-col--opposed')}
      </div>
    </div>
  );
};


// ============================================================================
// Main Component
// ============================================================================

export const MEPComparativeTab = () => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const {
    selectedProcedure,
    policyPosition,
    setPolicyPosition,
    runAlignment,
    scoringStatus,
    scoringError,
    alignmentScores,
    scoreDistribution,
    comparison,
  } = useMEPAmendments();

  const [localPosition, setLocalPosition] = useState(policyPosition);

  const handleRun = () => {
    if (!token || !selectedProcedure) return;
    setPolicyPosition(localPosition);
    runAlignment(token);
  };

  const isLoading = scoringStatus === 'loading';
  const hasResults = scoringStatus === 'success' && alignmentScores && comparison;

  if (!selectedProcedure) {
    return (
      <div className="mep-comparative">
        <div className="mep-comparative__info-note">
          <Icon path={mdiInformationOutline} size={0.7} />
          <span>{t('mepComparativeTab.selectProcedure')}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="mep-comparative">
      {/* Policy Position Input */}
      <PolicyPositionInput
        value={localPosition}
        onChange={setLocalPosition}
        onSubmit={handleRun}
        isLoading={isLoading}
        disabled={!selectedProcedure}
      />

      {/* Error */}
      {scoringStatus === 'error' && scoringError && (
        <div className="mep-comparative__error">
          <Icon path={mdiAlertCircleOutline} size={0.7} />
          <span>{scoringError}</span>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="mep-comparative__loading">
          <Icon path={mdiLoading} size={1} spin />
          <span>{t('mepComparativeTab.scoring')}</span>
        </div>
      )}

      {/* Results */}
      {hasResults && (
        <>
          <AlignmentSummary
            distribution={scoreDistribution!}
            total={alignmentScores!.length}
          />
          <BestAllies allies={comparison!.best_allies} />
          <CoverageGaps gaps={comparison!.coverage_gaps} />
          <PoliticalLandscape landscape={comparison!.political_landscape} />
        </>
      )}
    </div>
  );
};
