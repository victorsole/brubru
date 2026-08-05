// Amendment Display Component with EP-compliant formatting
import { useTranslation } from 'react-i18next';
import type { Amendment } from '../../pages/amendator_page';
import { formatOriginalColumn, formatAmendmentColumn } from '../../utils/amendment_formatter';
import './amendment_display.css';

interface AmendmentDisplayProps {
  amendment: Amendment;
}

export const AmendmentDisplay = ({ amendment }: AmendmentDisplayProps) => {
  const { t } = useTranslation();

  const getStatusLabel = (status: Amendment['status']) => {
    switch (status) {
      case 'tabled':
        return t('amendments.tabled', 'Tabled');
      case 'candidate':
        return t('amendments.candidate', 'Candidate');
      case 'withdrawn':
        return t('amendments.withdrawn', 'Withdrawn');
      default:
        return status;
    }
  };

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
          {getStatusLabel(amendment.status)}
        </span>
      </div>

      {/* Two-Column Amendment Table */}
      <div className="amendment-display__table">
        {/* Column Headers */}
        <div className="amendment-display__table-header">
          <div className="amendment-display__table-cell amendment-display__table-cell--header">
            {t('amendator.editor.originalLabel', 'Original Text')}
          </div>
          <div className="amendment-display__table-cell amendment-display__table-cell--header">
            {t('amendator.editor.proposedLabel', 'Proposed Amendment')}
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
          <h4 className="amendment-display__justification-title">{t('amendatorExtras.justification', 'Justification')}</h4>
          <p className="amendment-display__justification-text">{amendment.justification}</p>
        </div>
      )}
    </div>
  );
};
