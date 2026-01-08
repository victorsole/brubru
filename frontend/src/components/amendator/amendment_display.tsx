// Amendment Display Component with EP-compliant formatting
import type { Amendment } from '../../pages/amendator_page';
import { formatOriginalColumn, formatAmendmentColumn } from '../../utils/amendment_formatter';
import './amendment_display.css';

interface AmendmentDisplayProps {
  amendment: Amendment;
}

export const AmendmentDisplay = ({ amendment }: AmendmentDisplayProps) => {
  // Format text according to amendment type
  const formattedOriginal = formatOriginalColumn(
    amendment.originalText,
    amendment.type,
    amendment.changedWords,
    amendment.isCompleteSupression
  );

  const formattedProposed = formatAmendmentColumn(
    amendment.proposedText,
    amendment.type,
    amendment.changedWords,
    amendment.isCompleteSupression
  );

  return (
    <div className="amendment-display">
      {/* Amendment Header */}
      <div className="amendment-display__header">
        <div className="amendment-display__header-left">
          {amendment.group && (
            <span className="amendment-display__group">{amendment.group}</span>
          )}
          <h3 className="amendment-display__position">{amendment.position}</h3>
        </div>
        <span className={`amendment-display__status amendment-display__status--${amendment.status}`}>
          {amendment.status}
        </span>
      </div>

      {/* Two-Column Amendment Table */}
      <div className="amendment-display__table">
        {/* Column Headers */}
        <div className="amendment-display__table-header">
          <div className="amendment-display__table-cell amendment-display__table-cell--header">
            Original Text
          </div>
          <div className="amendment-display__table-cell amendment-display__table-cell--header">
            Proposed Amendment
          </div>
        </div>

        {/* Amendment Content */}
        <div className="amendment-display__table-row">
          <div className="amendment-display__table-cell">
            <div
              className="amendment-display__text"
              dangerouslySetInnerHTML={{ __html: formattedOriginal }}
            />
          </div>
          <div className="amendment-display__table-cell">
            <div
              className="amendment-display__text"
              dangerouslySetInnerHTML={{ __html: formattedProposed }}
            />
          </div>
        </div>
      </div>

      {/* Justification (if provided) */}
      {amendment.justification && (
        <div className="amendment-display__justification">
          <h4 className="amendment-display__justification-title">Justification</h4>
          <p className="amendment-display__justification-text">{amendment.justification}</p>
        </div>
      )}
    </div>
  );
};
