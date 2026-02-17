/**
 * Commission Document Card Component
 *
 * Displays a single Commission document in a card format.
 * Used in the Commission Docs sub-tab of My Tracked Files.
 *
 * Created: February 2026
 */

import Icon from '@mdi/react';
import {
  mdiOpenInNew,
  mdiCalendarOutline,
  mdiDomain,
} from '@mdi/js';
import type { CommissionDocItem } from '../../hooks/use_commission_documents';
import { DOC_TYPE_INFO } from '../../hooks/use_commission_documents';
import './commission_document_card.css';

interface CommissionDocumentCardProps {
  item: CommissionDocItem;
}

export const CommissionDocumentCard = ({ item }: CommissionDocumentCardProps) => {
  const typeInfo = DOC_TYPE_INFO[item.doc_type] || { name: item.doc_type, color: '#6b7280' };

  const oeilUrl = item.procedure_ref
    ? `https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=${encodeURIComponent(item.procedure_ref)}`
    : null;

  return (
    <div className="commission-document-card">
      <div className="commission-document-card__header">
        <span
          className="commission-document-card__type"
          style={{ backgroundColor: typeInfo.color }}
        >
          {typeInfo.name}
        </span>
        {item.dg_responsible && (
          <span className="commission-document-card__dg">
            <Icon path={mdiDomain} size={0.5} />
            {item.dg_responsible}
          </span>
        )}
      </div>

      <h4 className="commission-document-card__title">
        {item.title}
      </h4>

      <div className="commission-document-card__meta">
        <span className="commission-document-card__ref">
          {item.reference}
        </span>
        {item.publication_date && (
          <span className="commission-document-card__date">
            <Icon path={mdiCalendarOutline} size={0.55} />
            {new Date(item.publication_date).toLocaleDateString('en-GB', {
              day: 'numeric',
              month: 'short',
              year: 'numeric',
            })}
          </span>
        )}
        {item.procedure_ref && (
          <span className="commission-document-card__procedure">
            {item.procedure_ref}
          </span>
        )}
      </div>

      <div className="commission-document-card__actions">
        {item.portal_url && (
          <a
            href={item.portal_url}
            target="_blank"
            rel="noopener noreferrer"
            className="commission-document-card__action-btn"
          >
            <Icon path={mdiOpenInNew} size={0.7} />
            View in EUR-Lex
          </a>
        )}
        {oeilUrl && (
          <a
            href={oeilUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="commission-document-card__action-btn"
          >
            <Icon path={mdiOpenInNew} size={0.7} />
            OEIL
          </a>
        )}
      </div>
    </div>
  );
};
