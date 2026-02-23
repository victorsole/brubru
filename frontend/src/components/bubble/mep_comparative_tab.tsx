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
  <div className="mep-comparative__input-section">
    <label className="mep-comparative__input-label" htmlFor="policy-position">
      Describe your policy position
    </label>
    <p className="mep-comparative__input-hint">
      Summarise your organisation's stance on this legislative file in 2-3 sentences.
      The AI will score each MEP amendment's alignment with your position.
    </p>
    <textarea
      id="policy-position"
      className="mep-comparative__textarea"
      placeholder="e.g. We support strong consumer protection standards and mandatory transparency requirements, but oppose provisions that would create disproportionate compliance burdens for SMEs..."
      value={value}
      onChange={(e) => onChange(e.target.value)}
      rows={4}
      disabled={isLoading}
    />
    <div className="mep-comparative__input-footer">
      <span className="mep-comparative__char-count">
        {value.length} / 5,000 characters
      </span>
      <button
        className="mep-comparative__run-btn"
        onClick={onSubmit}
        disabled={disabled || value.length < 10 || isLoading}
        aria-label="Run alignment analysis"
      >
        {isLoading ? (
          <>
            <Icon path={mdiLoading} size={0.7} spin />
            Scoring amendments...
          </>
        ) : (
          <>
            <Icon path={mdiMagnifyScan} size={0.7} />
            Run Analysis
          </>
        )}
      </button>
    </div>
  </div>
);


/** Alignment Summary Cards */
const AlignmentSummary = ({
  distribution,
  total,
}: {
  distribution: Record<string, number>;
  total: number;
}) => {
  const cards = [
    { key: '2', label: 'Strongly Aligned', colour: '#059669' },
    { key: '1', label: 'Partially Aligned', colour: '#0693e3' },
    { key: '0', label: 'Neutral', colour: '#9ca3af' },
    { key: 'negative', label: 'Opposed', colour: '#dc2626' },
  ];

  const negativeCount = (distribution['-1'] || 0) + (distribution['-2'] || 0);

  return (
    <div className="mep-comparative__section">
      <div className="mep-comparative__section-header">
        <Icon path={mdiScaleBalance} size={0.8} />
        <span>Alignment Summary</span>
        <span className="mep-comparative__section-count">{total} amendments scored</span>
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
  if (!allies.length) return null;

  return (
    <div className="mep-comparative__section">
      <div className="mep-comparative__section-header">
        <Icon path={mdiAccountHeartOutline} size={0.8} />
        <span>Best Allies</span>
      </div>
      <p className="mep-comparative__section-desc">
        MEPs whose amendments most closely align with your position, ranked by average score.
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
              <span className="mep-comparative__ally-count">{ally.count} am.</span>
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
  if (!gaps.user_unique.length && !gaps.blind_spots.length) {
    return (
      <div className="mep-comparative__section">
        <div className="mep-comparative__section-header">
          <Icon path={mdiPuzzleOutline} size={0.8} />
          <span>Coverage Gaps</span>
        </div>
        <div className="mep-comparative__info-note">
          <Icon path={mdiInformationOutline} size={0.7} />
          <span>
            Draft amendments in the Amendator for this procedure to see coverage gaps.
            This compares elements you amended against elements MEPs targeted.
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="mep-comparative__section">
      <div className="mep-comparative__section-header">
        <Icon path={mdiPuzzleOutline} size={0.8} />
        <span>Coverage Gaps</span>
      </div>
      <div className="mep-comparative__gaps-grid">
        <div className="mep-comparative__gap-col mep-comparative__gap-col--unique">
          <div className="mep-comparative__gap-header">
            Your Unique Positions ({gaps.user_unique.length})
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
                All your amended elements are also targeted by MEPs.
              </p>
            )}
          </div>
        </div>
        <div className="mep-comparative__gap-col mep-comparative__gap-col--blind">
          <div className="mep-comparative__gap-header">
            Blind Spots ({gaps.blind_spots.length})
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
                No blind spots -- you cover all elements MEPs have targeted.
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
              <span className="mep-comparative__landscape-count">{g.count} am.</span>
            </div>
          );
        }) : (
          <p className="mep-comparative__landscape-empty">None</p>
        )}
      </div>
    </div>
  );

  return (
    <div className="mep-comparative__section">
      <div className="mep-comparative__section-header">
        <Icon path={mdiBankOutline} size={0.8} />
        <span>Political Landscape</span>
      </div>
      <div className="mep-comparative__landscape-grid">
        {renderColumn('Supportive', landscape.supportive, 'mep-comparative__landscape-col--supportive')}
        {renderColumn('Mixed', landscape.mixed, 'mep-comparative__landscape-col--mixed')}
        {renderColumn('Opposed', landscape.opposed, 'mep-comparative__landscape-col--opposed')}
      </div>
    </div>
  );
};


// ============================================================================
// Main Component
// ============================================================================

export const MEPComparativeTab = () => {
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
          <span>Select a procedure from the MEP Amendments tab to run comparative analysis.</span>
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
          <span>Scoring amendments against your position... This may take a moment.</span>
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
