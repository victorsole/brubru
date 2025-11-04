// frontend/src/components/amendator/amendment_grid.tsx
import type { Amendment } from '../../pages/amendator_page';
import './amendment_grid.css';

interface AmendmentGridProps {
  amendments: Amendment[];
  onSelectAmendment: (amendment: Amendment) => void;
  selectedAmendmentId?: string;
}

export const AmendmentGrid = ({
  amendments,
  onSelectAmendment,
  selectedAmendmentId,
}: AmendmentGridProps) => {
  const getStatusClass = (status: Amendment['status']) => {
    switch (status) {
      case 'tabled':
        return 'amendment-grid__status--tabled';
      case 'candidate':
        return 'amendment-grid__status--candidate';
      case 'withdrawn':
        return 'amendment-grid__status--withdrawn';
      default:
        return '';
    }
  };

  const getStatusLabel = (status: Amendment['status']) => {
    switch (status) {
      case 'tabled':
        return 'Tabled';
      case 'candidate':
        return 'Candidate';
      case 'withdrawn':
        return 'Withdrawn';
      default:
        return status;
    }
  };

  const truncateText = (text: string, maxLength: number = 60) => {
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  };

  return (
    <div className="amendment-grid">
      <div className="amendment-grid__header">
        <h3 className="amendment-grid__title">Amendments</h3>
        <span className="amendment-grid__count">{amendments.length}</span>
      </div>

      {amendments.length === 0 ? (
        <div className="amendment-grid__empty">
          <p>No amendments yet</p>
          <p className="amendment-grid__empty-hint">
            Create your first amendment using the editor on the right
          </p>
        </div>
      ) : (
        <div className="amendment-grid__list">
          {amendments.map((amendment) => (
            <div
              key={amendment.id}
              className={`amendment-grid__item ${
                amendment.id === selectedAmendmentId ? 'amendment-grid__item--selected' : ''
              }`}
              onClick={() => onSelectAmendment(amendment)}
            >
              <div className="amendment-grid__item-header">
                <span className="amendment-grid__position">{amendment.position}</span>
                <span className={`amendment-grid__status ${getStatusClass(amendment.status)}`}>
                  {getStatusLabel(amendment.status)}
                </span>
              </div>
              <p className="amendment-grid__preview">
                {truncateText(amendment.proposedText)}
              </p>
              <span className="amendment-grid__date">
                {new Date(amendment.createdAt).toLocaleDateString('en-GB', {
                  day: '2-digit',
                  month: 'short',
                  year: 'numeric',
                })}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="amendment-grid__actions">
        <button className="amendment-grid__export-button button button-secondary button-sm">
          Export All
        </button>
      </div>
    </div>
  );
};
